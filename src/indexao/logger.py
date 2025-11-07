"""
Advanced logging system for Indexao.

Features:
- Multiple log levels (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Structured logging (text + JSON formats)
- Automatic log rotation (daily/weekly/size-based)
- Per-module log level configuration
- Context enrichment (timestamps, module, file:line)
- Performance tracking with slow operation detection
- Thread-safe operations
- Colored console output

Usage:
    from indexao.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("Operation started", path="/data/docs")
    
    # With context
    with logger.context(operation="scan"):
        logger.debug("Processing files")
    
    # Performance tracking
    with logger.timer("ocr_processing"):
        result = process_image()
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, TextIO
from contextlib import contextmanager
from threading import Lock
import time
import traceback

# Custom log levels
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")


class ColoredFormatter(logging.Formatter):
    """Formatter with ANSI color codes for console output."""
    
    # ANSI color codes
    COLORS = {
        'TRACE': '\033[36m',      # Cyan
        'DEBUG': '\033[34m',      # Blue
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if hasattr(record, 'no_color') or not sys.stdout.isatty():
            return super().format(record)
        
        level_color = self.COLORS.get(record.levelname, '')
        reset = self.COLORS['RESET']
        
        # Color the level name only
        original_levelname = record.levelname
        record.levelname = f"{level_color}{record.levelname:8}{reset}"
        
        result = super().format(record)
        record.levelname = original_levelname  # Restore original
        
        return result


class JSONFormatter(logging.Formatter):
    """Formatter for structured JSON logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data)


class ContextEnrichedLogger(logging.LoggerAdapter):
    """Logger adapter that enriches logs with context information."""
    
    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        super().__init__(logger, extra or {})
        self._context_stack = []
        self._lock = Lock()
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message with context."""
        # Merge context stack
        if self._context_stack:
            merged_context = {}
            for ctx in self._context_stack:
                merged_context.update(ctx)
            
            # Add to extra
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            kwargs['extra']['context'] = merged_context
        
        return msg, kwargs
    
    @contextmanager
    def context(self, **kwargs):
        """Context manager to add temporary context to logs."""
        with self._lock:
            self._context_stack.append(kwargs)
        try:
            yield
        finally:
            with self._lock:
                self._context_stack.pop()
    
    @contextmanager
    def timer(self, operation: str, slow_threshold_ms: int = 1000):
        """
        Context manager to track operation duration.
        
        Args:
            operation: Name of the operation being timed
            slow_threshold_ms: Log warning if duration exceeds this (milliseconds)
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            if duration_ms >= slow_threshold_ms:
                self.warning(
                    f"Slow operation: {operation}",
                    extra={'duration_ms': duration_ms, 'operation': operation}
                )
            else:
                self.debug(
                    f"Completed: {operation}",
                    extra={'duration_ms': duration_ms, 'operation': operation}
                )
    
    def trace(self, msg: str, *args, **kwargs):
        """Log with TRACE level."""
        self.log(TRACE_LEVEL, msg, *args, **kwargs)


class LoggerManager:
    """
    Singleton manager for logging configuration.
    Handles log file creation, rotation, and formatter setup.
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._loggers: Dict[str, ContextEnrichedLogger] = {}
        self._config: Dict[str, Any] = {}
        self._log_dir: Optional[Path] = None
        self._suppress_logs = os.getenv('INDEXAO_SUPPRESS_LOGS', '').lower() == '1'
        
        # Load configuration
        self._load_config()
        
        # Setup root logger (only if not suppressed)
        if not self._suppress_logs:
            self._setup_root_logger()
    
    def _load_config(self, log_dir: Optional[str] = None):
        """Load logging configuration from environment or defaults.
        
        Args:
            log_dir: Optional log directory path (overrides env var)
        """
        # Get log level from environment
        log_level = os.getenv('INDEXAO_LOG_LEVEL', 'INFO').upper()
        
        # Get log directory
        # Priority: 1. Parameter, 2. Env var, 3. Default 'logs'
        if log_dir is None:
            log_dir = os.getenv('INDEXAO_LOG_DIR', 'logs')
        
        self._log_dir = Path(log_dir).expanduser().resolve()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Default configuration
        self._config = {
            'level': log_level,
            'handlers': {
                'console': {
                    'enabled': os.getenv('INDEXAO_LOG_CONSOLE', 'true').lower() == 'true',
                    'level': log_level,
                    'colored': os.getenv('INDEXAO_LOG_COLORED', 'true').lower() == 'true',
                },
                'file': {
                    'enabled': os.getenv('INDEXAO_LOG_FILE', 'true').lower() == 'true',
                    'level': 'DEBUG',
                    'rotation': 'daily',
                    'backup_count': 7,
                },
                'debug_file': {
                    'enabled': os.getenv('INDEXAO_LOG_DEBUG', 'true').lower() == 'true',
                    'level': 'TRACE',
                    'rotation': 'daily',
                    'backup_count': 3,
                },
                'json': {
                    'enabled': os.getenv('INDEXAO_LOG_JSON', 'false').lower() == 'true',
                    'level': 'DEBUG',
                },
            },
            'format': {
                'text': '[{asctime}] {levelname:8} {name:30} {message}',
                'date': '%Y-%m-%d %H:%M:%S',
            },
            'performance': {
                'slow_threshold_ms': int(os.getenv('INDEXAO_SLOW_THRESHOLD', '1000')),
            }
        }
    
    def _setup_root_logger(self):
        """Setup root logger with configured handlers."""
        root_logger = logging.getLogger('indexao')
        root_logger.setLevel(TRACE_LEVEL)  # Capture all levels
        root_logger.handlers.clear()
        
        # Console handler
        if self._config['handlers']['console']['enabled']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_level = getattr(
                logging, 
                self._config['handlers']['console']['level']
            )
            console_handler.setLevel(console_level)
            
            if self._config['handlers']['console']['colored']:
                console_formatter = ColoredFormatter(
                    fmt=self._config['format']['text'],
                    datefmt=self._config['format']['date'],
                    style='{'
                )
            else:
                console_formatter = logging.Formatter(
                    fmt=self._config['format']['text'],
                    datefmt=self._config['format']['date'],
                    style='{'
                )
            
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # Main log file handler
        if self._config['handlers']['file']['enabled']:
            log_file = self._log_dir / f"indexao_{datetime.now():%Y%m%d}.log"
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=log_file,
                when='midnight',
                interval=1,
                backupCount=self._config['handlers']['file']['backup_count'],
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                fmt=self._config['format']['text'],
                datefmt=self._config['format']['date'],
                style='{'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        
        # Debug log file handler (TRACE level)
        if self._config['handlers']['debug_file']['enabled']:
            debug_file = self._log_dir / f"indexao_debug_{datetime.now():%Y%m%d}.log"
            debug_handler = logging.handlers.TimedRotatingFileHandler(
                filename=debug_file,
                when='midnight',
                interval=1,
                backupCount=self._config['handlers']['debug_file']['backup_count'],
                encoding='utf-8'
            )
            debug_handler.setLevel(TRACE_LEVEL)
            debug_formatter = logging.Formatter(
                fmt='[{asctime}] {levelname:8} {name:30} {funcName:20} {filename}:{lineno} - {message}',
                datefmt=self._config['format']['date'],
                style='{'
            )
            debug_handler.setFormatter(debug_formatter)
            root_logger.addHandler(debug_handler)
        
        # JSON log file handler
        if self._config['handlers']['json']['enabled']:
            json_file = self._log_dir / f"indexao_{datetime.now():%Y%m%d}.json"
            json_handler = logging.FileHandler(json_file, encoding='utf-8')
            json_handler.setLevel(logging.DEBUG)
            json_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(json_handler)
    
    def get_logger(self, name: str) -> ContextEnrichedLogger:
        """
        Get or create a logger with the given name.
        
        Args:
            name: Logger name (typically __name__ of calling module)
        
        Returns:
            ContextEnrichedLogger instance
        """
        # Ensure name is under 'indexao' namespace
        if not name.startswith('indexao'):
            name = f'indexao.{name}'
        
        if name not in self._loggers:
            base_logger = logging.getLogger(name)
            self._loggers[name] = ContextEnrichedLogger(base_logger)
        
        return self._loggers[name]
    
    def set_level(self, level: str, module: Optional[str] = None):
        """
        Set log level for all loggers or specific module.
        
        Args:
            level: Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
            module: Optional module name to set level for
        """
        level_value = getattr(logging, level.upper(), logging.INFO)
        
        if level_value == TRACE_LEVEL:
            level_value = TRACE_LEVEL
        
        if module:
            logger_name = f'indexao.{module}' if not module.startswith('indexao') else module
            logging.getLogger(logger_name).setLevel(level_value)
        else:
            logging.getLogger('indexao').setLevel(level_value)
    
    def reconfigure(self, log_dir: str):
        """
        Reconfigure logger with new log directory.
        
        This is called after loading config.toml to use the correct paths.
        
        Args:
            log_dir: New log directory path (can contain ${variables})
        """
        # Save current level
        current_level = os.getenv('INDEXAO_LOG_LEVEL', 'INFO')
        
        # Update log directory
        self._log_dir = Path(log_dir).expanduser().resolve()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove all existing handlers
        root_logger = logging.getLogger('indexao')
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        
        # Reload config with new path
        self._load_config(log_dir=str(self._log_dir))
        
        # Recreate handlers only if not suppressed
        if not self._suppress_logs:
            self._setup_root_logger()
        
            # Log the change
            logger = self.get_logger('indexao.logger')
            logger.info(f"Logger reconfigured with log_dir: {self._log_dir}")


# Global logger manager instance
_manager = LoggerManager()


def get_logger(name: str = __name__) -> ContextEnrichedLogger:
    """
    Get a logger instance for the given name.
    
    This is the main entry point for getting loggers in Indexao.
    
    Args:
        name: Logger name (typically __name__ of calling module)
    
    Returns:
        ContextEnrichedLogger instance with context and timing support
    
    Example:
        >>> from indexao.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Started processing")
        >>> with logger.timer("process_file"):
        ...     process_large_file()
    """
    return _manager.get_logger(name)


def set_level(level: str, module: Optional[str] = None):
    """
    Set global or module-specific log level.
    
    Args:
        level: Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
        module: Optional module name
    
    Example:
        >>> from indexao.logger import set_level
        >>> set_level('DEBUG')  # All loggers
        >>> set_level('TRACE', 'indexao.scanner')  # Specific module
    """
    _manager.set_level(level, module)


def reconfigure_logger(log_dir: str):
    """
    Reconfigure logger with new log directory from config.
    
    This should be called after loading config.toml.
    
    Args:
        log_dir: New log directory path (resolved, can be from ${variables})
    
    Example:
        >>> from indexao.logger import reconfigure_logger
        >>> from indexao.config import load_config
        >>> config = load_config()
        >>> reconfigure_logger(config.logging.log_dir)
    """
    _manager.reconfigure(log_dir)


# Convenience function for scripts
def init_logging(
    level: str = 'INFO',
    log_dir: Optional[str] = None,
    console: bool = True,
    file: bool = True
):
    """
    Initialize logging with simple configuration.
    
    Args:
        level: Default log level
        log_dir: Directory for log files
        console: Enable console output
        file: Enable file output
    """
    if log_dir:
        os.environ['INDEXAO_LOG_DIR'] = log_dir
    
    os.environ['INDEXAO_LOG_LEVEL'] = level
    os.environ['INDEXAO_LOG_CONSOLE'] = 'true' if console else 'false'
    os.environ['INDEXAO_LOG_FILE'] = 'true' if file else 'false'
    
    # Force reload
    global _manager
    _manager = LoggerManager()
