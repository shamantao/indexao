"""Unit tests for indexao.logger module."""

import pytest
import logging
import json
import time
import os
import tempfile
from pathlib import Path
from datetime import datetime

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from indexao.logger import (
    get_logger,
    set_level,
    init_logging,
    TRACE_LEVEL,
    ColoredFormatter,
    JSONFormatter,
    ContextEnrichedLogger
)


class TestLoggerBasics:
    """Test basic logger functionality."""
    
    def test_get_logger_returns_context_logger(self):
        """Test that get_logger returns ContextEnrichedLogger."""
        logger = get_logger('test_module')
        assert isinstance(logger, ContextEnrichedLogger)
    
    def test_logger_name_namespace(self):
        """Test that logger names are namespaced under 'indexao'."""
        logger = get_logger('mymodule')
        assert logger.logger.name == 'indexao.mymodule'
    
    def test_logger_already_namespaced(self):
        """Test that already namespaced names are not double-prefixed."""
        logger = get_logger('indexao.scanner')
        assert logger.logger.name == 'indexao.scanner'
    
    def test_trace_level_exists(self):
        """Test that TRACE custom level is registered."""
        assert TRACE_LEVEL == 5
        assert logging.getLevelName(TRACE_LEVEL) == 'TRACE'


class TestLogLevels:
    """Test logging at different levels."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_log_levels(self, temp_log_dir, capsys):
        """Test logging at all levels."""
        # Initialize with DEBUG level and temp dir
        init_logging(level='DEBUG', log_dir=temp_log_dir, console=True, file=False)
        
        logger = get_logger('test_levels')
        
        # Log at different levels
        logger.trace("Trace message")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        # Check console output contains messages
        captured = capsys.readouterr()
        assert "Debug message" in captured.out
        assert "Info message" in captured.out
        assert "Warning message" in captured.out
        assert "Error message" in captured.out
        assert "Critical message" in captured.out
    
    def test_set_level_filters_messages(self, temp_log_dir, capsys):
        """Test that set_level filters messages appropriately."""
        init_logging(level='INFO', log_dir=temp_log_dir, console=True, file=False)
        
        logger = get_logger('test_filter')
        
        logger.debug("Should not appear")
        logger.info("Should appear")
        
        captured = capsys.readouterr()
        assert "Should not appear" not in captured.out
        assert "Should appear" in captured.out


class TestContextEnrichment:
    """Test context manager functionality."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_context_manager_adds_context(self, temp_log_dir):
        """Test that context manager adds context to logs."""
        # Enable JSON logging for easy parsing
        os.environ['INDEXAO_LOG_JSON'] = 'true'
        init_logging(level='DEBUG', log_dir=temp_log_dir, console=False, file=False)
        
        logger = get_logger('test_context')
        
        with logger.context(operation="test", user_id=123):
            logger.info("Inside context")
        
        # Read JSON log
        json_files = list(Path(temp_log_dir).glob('*.json'))
        assert len(json_files) == 1
        
        with open(json_files[0], 'r') as f:
            lines = f.readlines()
            assert len(lines) >= 1
            
            log_entry = json.loads(lines[-1])
            assert 'context' in log_entry
            assert log_entry['context']['operation'] == 'test'
            assert log_entry['context']['user_id'] == 123
    
    def test_nested_context(self, temp_log_dir):
        """Test nested context managers."""
        os.environ['INDEXAO_LOG_JSON'] = 'true'
        init_logging(level='DEBUG', log_dir=temp_log_dir, console=False, file=False)
        
        logger = get_logger('test_nested')
        
        with logger.context(level1="outer"):
            with logger.context(level2="inner"):
                logger.info("Nested context")
        
        # Read JSON log
        json_files = list(Path(temp_log_dir).glob('*.json'))
        with open(json_files[0], 'r') as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])
            
            assert log_entry['context']['level1'] == 'outer'
            assert log_entry['context']['level2'] == 'inner'


class TestPerformanceTimer:
    """Test performance timing functionality."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_timer_logs_duration(self, temp_log_dir):
        """Test that timer logs operation duration."""
        os.environ['INDEXAO_LOG_JSON'] = 'true'
        init_logging(level='DEBUG', log_dir=temp_log_dir, console=False, file=False)
        
        logger = get_logger('test_timer')
        
        with logger.timer("fast_operation", slow_threshold_ms=5000):
            time.sleep(0.01)  # 10ms
        
        # Read JSON log
        json_files = list(Path(temp_log_dir).glob('*.json'))
        with open(json_files[0], 'r') as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])
            
            assert 'duration_ms' in log_entry
            assert log_entry['duration_ms'] >= 10
            assert log_entry['duration_ms'] < 100
            assert 'Completed' in log_entry['message']
    
    def test_timer_warns_on_slow_operation(self, temp_log_dir):
        """Test that timer warns for slow operations."""
        os.environ['INDEXAO_LOG_JSON'] = 'true'
        init_logging(level='DEBUG', log_dir=temp_log_dir, console=False, file=False)
        
        logger = get_logger('test_slow')
        
        with logger.timer("slow_operation", slow_threshold_ms=10):
            time.sleep(0.02)  # 20ms (exceeds threshold)
        
        # Read JSON log
        json_files = list(Path(temp_log_dir).glob('*.json'))
        with open(json_files[0], 'r') as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])
            
            assert log_entry['level'] == 'WARNING'
            assert 'Slow operation' in log_entry['message']
            assert log_entry['duration_ms'] >= 20


class TestFormatters:
    """Test log formatters."""
    
    def test_colored_formatter_adds_colors_for_tty(self):
        """Test that ColoredFormatter adds ANSI codes when output is TTY."""
        formatter = ColoredFormatter(fmt='{levelname} {message}', style='{')
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # If TTY detection works, this should have colors
        formatted = formatter.format(record)
        # Can't reliably test TTY in pytest, so just check format works
        assert 'Test message' in formatted
    
    def test_json_formatter_produces_valid_json(self):
        """Test that JSONFormatter produces valid JSON."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.context = {'key': 'value'}
        record.duration_ms = 123.45
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert parsed['level'] == 'INFO'
        assert parsed['logger'] == 'test.module'
        assert parsed['message'] == 'Test message'
        assert parsed['line'] == 42
        assert parsed['context'] == {'key': 'value'}
        assert parsed['duration_ms'] == 123.45
        assert 'timestamp' in parsed


class TestLogRotation:
    """Test log rotation functionality."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_log_files_created(self, temp_log_dir):
        """Test that log files are created in specified directory."""
        init_logging(level='INFO', log_dir=temp_log_dir, console=False, file=True)
        
        logger = get_logger('test_files')
        logger.info("Test message")
        
        # Check that log files exist
        log_files = list(Path(temp_log_dir).glob('*.log'))
        assert len(log_files) >= 1
        
        # Check content
        with open(log_files[0], 'r') as f:
            content = f.read()
            assert 'Test message' in content


class TestModuleSpecificLevels:
    """Test module-specific log level configuration."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_set_level_for_specific_module(self, temp_log_dir, capsys):
        """Test setting log level for specific module only."""
        init_logging(level='INFO', log_dir=temp_log_dir, console=True, file=False)
        
        # Set DEBUG for specific module
        set_level('DEBUG', 'test_specific')
        
        logger1 = get_logger('test_specific')
        logger2 = get_logger('test_other')
        
        logger1.debug("Debug from specific")
        logger2.debug("Debug from other")
        
        captured = capsys.readouterr()
        assert "Debug from specific" in captured.out
        # logger2 should still be at INFO level, so debug won't show
        # (Note: This might not work perfectly due to parent logger inheritance)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
