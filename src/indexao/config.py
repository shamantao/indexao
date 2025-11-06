"""
Configuration management for Indexao.

Loads configuration from TOML files with environment variable overrides.
Validates configuration and provides typed access to settings.

Features:
- TOML-based configuration with path variable expansion
- Environment variable overrides (INDEXAO_*)
- Path variables: ${var} syntax for reusable paths
- Automatic path resolution and validation

Usage:
    from indexao.config import load_config, get_config
    
    # Load from default location
    config = load_config()
    
    # Load from specific file
    config = load_config("custom_config.toml")
    
    # Access settings
    log_level = config.logging.level
    ocr_engine = config.plugins.ocr.engine
    
    # Environment variable override: INDEXAO_LOGGING_LEVEL=TRACE
"""

import os
import re
import tomllib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from indexao.logger import get_logger, reconfigure_logger
from indexao.plugin_manager import PluginManager

logger = get_logger(__name__)

# Global configuration instance
_config: Optional['Config'] = None
_plugin_manager: Optional[PluginManager] = None


# ============================================================================
# PATH VARIABLE EXPANSION
# ============================================================================

def _expand_path_variables(value: Any, variables: Dict[str, str], max_depth: int = 10) -> Any:
    """
    Expand ${var} syntax in configuration values recursively.
    
    Args:
        value: Value to expand (str, dict, list, or other)
        variables: Dictionary of variable names to values
        max_depth: Maximum recursion depth to prevent infinite loops
    
    Returns:
        Expanded value
    
    Examples:
        >>> vars = {"home": "/Users/phil", "workspace": "${home}/projects"}
        >>> _expand_path_variables("${workspace}/data", vars)
        '/Users/phil/projects/data'
    """
    if max_depth <= 0:
        raise ValueError("Maximum recursion depth reached in path variable expansion")
    
    # String: expand ${var} references
    if isinstance(value, str):
        # Pattern: ${variable_name}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_name = match.group(1)
            if var_name not in variables:
                logger.warning(f"Unknown variable: ${{{var_name}}}")
                return match.group(0)  # Return unchanged
            
            var_value = variables[var_name]
            # Recursively expand if variable value contains other variables
            if isinstance(var_value, str) and '${' in var_value:
                return _expand_path_variables(var_value, variables, max_depth - 1)
            return str(var_value)
        
        return re.sub(pattern, replace_var, value)
    
    # Dictionary: expand all values
    elif isinstance(value, dict):
        return {k: _expand_path_variables(v, variables, max_depth) for k, v in value.items()}
    
    # List: expand all items
    elif isinstance(value, list):
        return [_expand_path_variables(item, variables, max_depth) for item in value]
    
    # Other types: return unchanged
    else:
        return value


def _extract_path_variables(config_dict: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract path variables from [paths.variables] section.
    
    Args:
        config_dict: Configuration dictionary from TOML
    
    Returns:
        Dictionary of variable names to expanded values
    
    Example:
        Config TOML:
        [paths.variables]
        home = "/Users/phil"
        workspace = "${home}/projects"
        
        Returns:
        {"home": "/Users/phil", "workspace": "/Users/phil/projects"}
    """
    variables_section = config_dict.get("paths", {}).get("variables", {})
    
    if not variables_section:
        return {}
    
    # First pass: collect raw variables
    variables = dict(variables_section)
    
    # Second pass: expand variables that reference other variables
    # Sort by dependency (variables without ${} first)
    sorted_vars = sorted(variables.items(), key=lambda x: '${' in str(x[1]))
    
    expanded = {}
    for name, value in sorted_vars:
        expanded[name] = _expand_path_variables(value, expanded)
    
    logger.debug(f"Loaded {len(expanded)} path variables")
    return expanded


class LogLevel(str, Enum):
    """Log level enumeration."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    console_enabled: bool = True
    file_enabled: bool = True
    json_enabled: bool = False
    log_dir: str = "logs"
    rotation_when: str = "midnight"  # midnight, weekly, size
    rotation_interval: int = 1
    rotation_backup_count: int = 7
    slow_threshold_ms: float = 1000.0
    
    def __post_init__(self):
        """Validate log level."""
        valid_levels = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {self.level}. Must be one of {valid_levels}")
        self.level = self.level.upper()


@dataclass
class PathAdapterConfig:
    """Path adapter configuration."""
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    retry_enabled: bool = True
    retry_attempts: int = 3
    retry_backoff_ms: int = 100


@dataclass
class OCRPluginConfig:
    """OCR plugin configuration."""
    engine: str = "mock"  # mock, tesseract, chandra, google-vision
    languages: List[str] = field(default_factory=lambda: ["en", "fr", "zh-TW"])
    confidence_threshold: float = 0.7
    timeout_seconds: int = 30
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranslatorPluginConfig:
    """Translator plugin configuration."""
    engine: str = "mock"  # mock, argostranslate, google, deepl
    source_language: str = "auto"
    target_languages: List[str] = field(default_factory=lambda: ["en", "fr"])
    confidence_threshold: float = 0.7
    timeout_seconds: int = 30
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchPluginConfig:
    """Search plugin configuration."""
    engine: str = "mock"  # mock, meilisearch, tantivy, sqlite-fts
    host: str = "localhost"
    port: int = 7700
    index_name: str = "documents"
    api_key: Optional[str] = None
    timeout_seconds: int = 30
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginsConfig:
    """Plugins configuration."""
    ocr: OCRPluginConfig = field(default_factory=OCRPluginConfig)
    translator: TranslatorPluginConfig = field(default_factory=TranslatorPluginConfig)
    search: SearchPluginConfig = field(default_factory=SearchPluginConfig)


@dataclass
class Config:
    """Main configuration container."""
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    paths: PathAdapterConfig = field(default_factory=PathAdapterConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    
    # Root directories for data storage
    index_root: str = "index"  # Where indexed data, cache, logs are stored
    sources_root: str = "_sources"  # Where plugins and models are stored
    volumes_root: str = "_Volumes"  # Where user volumes and test data are located
    
    # Additional sections
    input_dir: str = "input"
    output_dir: str = "output"
    temp_dir: str = "temp"
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Config(log_level={self.logging.level}, "
            f"ocr={self.plugins.ocr.engine}, "
            f"translator={self.plugins.translator.engine}, "
            f"search={self.plugins.search.engine})"
        )


# Global config instance
_config: Optional[Config] = None


def _find_config_file(config_path: Optional[Path] = None) -> Path:
    """
    Find configuration file.
    
    Search order:
    1. Provided path
    2. INDEXAO_CONFIG environment variable
    3. ./config.toml
    4. ./config.example.toml
    5. ~/.indexao/config.toml
    
    Args:
        config_path: Optional explicit path to config file
    
    Returns:
        Path to config file
    
    Raises:
        FileNotFoundError: If no config file found
    """
    # 1. Explicit path
    if config_path:
        if config_path.exists():
            return config_path
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    # 2. Environment variable
    env_path = os.getenv("INDEXAO_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        logger.warning(f"INDEXAO_CONFIG points to non-existent file: {env_path}")
    
    # 3. ./config.toml
    local_config = Path("config.toml")
    if local_config.exists():
        return local_config
    
    # 4. ./config.example.toml
    example_config = Path("config.example.toml")
    if example_config.exists():
        logger.info("Using config.example.toml (no config.toml found)")
        return example_config
    
    # 5. ~/.indexao/config.toml
    home_config = Path.home() / ".indexao" / "config.toml"
    if home_config.exists():
        return home_config
    
    raise FileNotFoundError(
        "No configuration file found. Searched:\n"
        "  - INDEXAO_CONFIG environment variable\n"
        "  - ./config.toml\n"
        "  - ./config.example.toml\n"
        "  - ~/.indexao/config.toml"
    )


def _apply_env_overrides(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment variable overrides to config.
    
    Environment variables format: INDEXAO_<SECTION>_<SUBSECTION>_<KEY>=value
    Note: KEY can contain underscores (e.g., cache_ttl_seconds)
    
    Examples:
        INDEXAO_LOGGING_LEVEL=DEBUG -> logging.level
        INDEXAO_PLUGINS_OCR_ENGINE=tesseract -> plugins.ocr.engine
        INDEXAO_PLUGINS_SEARCH_API_KEY=secret -> plugins.search.api_key
    
    Args:
        config_dict: Configuration dictionary
    
    Returns:
        Updated configuration dictionary
    """
    # Mapping of env var prefixes to config paths
    # Format: (env_prefix, config_path_parts)
    # ORDER MATTERS: more specific prefixes first!
    mappings = [
        # Logging (nested)
        ("INDEXAO_LOGGING_CONSOLE_", ["logging", "console"]),
        ("INDEXAO_LOGGING_FILE_", ["logging", "file"]),
        ("INDEXAO_LOGGING_", ["logging"]),
        # Paths
        ("INDEXAO_PATHS_ADAPTERS_", ["paths", "adapters"]),
        ("INDEXAO_PATHS_", ["paths"]),
        # Plugins
        ("INDEXAO_PLUGINS_OCR_", ["plugins", "ocr"]),
        ("INDEXAO_PLUGINS_TRANSLATOR_", ["plugins", "translator"]),
        ("INDEXAO_PLUGINS_SEARCH_", ["plugins", "search"]),
        ("INDEXAO_PLUGINS_", ["plugins"]),
        # Top-level
        ("INDEXAO_", []),
    ]
    
    for env_key, env_value in os.environ.items():
        if not env_key.startswith("INDEXAO_"):
            continue
        
        # Find matching mapping
        matched = False
        for prefix, path_parts in mappings:
            if env_key.startswith(prefix):
                # Extract field name (rest after prefix, lowercase)
                field_name = env_key[len(prefix):].lower()
                
                # Navigate to target dict
                current = config_dict
                for part in path_parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Parse and set value
                try:
                    # Try boolean
                    if env_value.lower() in ("true", "yes", "1"):
                        value = True
                    elif env_value.lower() in ("false", "no", "0"):
                        value = False
                    # Try int
                    elif env_value.lstrip('-').isdigit():
                        value = int(env_value)
                    # Try float
                    elif '.' in env_value:
                        try:
                            value = float(env_value)
                        except ValueError:
                            value = env_value
                    # String
                    else:
                        value = env_value
                    
                    current[field_name] = value
                    logger.debug(f"Applied env override: {env_key}={env_value} -> {'.'.join(path_parts + [field_name])}")
                    matched = True
                    break
                except Exception as e:
                    logger.warning(f"Failed to parse env var {env_key}: {e}")
                    break
        
        if not matched and env_key.startswith("INDEXAO_"):
            logger.debug(f"Ignored unmapped env var: {env_key}")
    
    return config_dict


def _dict_to_config(config_dict: Dict[str, Any]) -> Config:
    """
    Convert dictionary to Config object.
    
    Args:
        config_dict: Configuration dictionary
    
    Returns:
        Config object
    """
    # Extract sections
    logging_dict = config_dict.get("logging", {})
    paths_dict = config_dict.get("paths", {}).get("adapters", {})
    plugins_dict = config_dict.get("plugins", {})
    
    # Build config objects
    logging_config = LoggingConfig(
        level=logging_dict.get("level", "INFO"),
        console_enabled=logging_dict.get("console", {}).get("enabled", True),
        file_enabled=logging_dict.get("file", {}).get("enabled", True),
        json_enabled=logging_dict.get("json", {}).get("enabled", False),
        log_dir=logging_dict.get("file", {}).get("dir", "logs"),
        rotation_when=logging_dict.get("file", {}).get("rotation_when", "midnight"),
        rotation_interval=logging_dict.get("file", {}).get("rotation_interval", 1),
        rotation_backup_count=logging_dict.get("file", {}).get("backup_count", 7),
        slow_threshold_ms=logging_dict.get("performance", {}).get("slow_threshold_ms", 1000.0)
    )
    
    paths_config = PathAdapterConfig(
        cache_enabled=paths_dict.get("cache_enabled", True),
        cache_ttl_seconds=paths_dict.get("cache_ttl_seconds", 300),
        retry_enabled=paths_dict.get("retry_enabled", True),
        retry_attempts=paths_dict.get("retry_attempts", 3),
        retry_backoff_ms=paths_dict.get("retry_backoff_ms", 100)
    )
    
    ocr_dict = plugins_dict.get("ocr", {})
    ocr_config = OCRPluginConfig(
        engine=ocr_dict.get("engine", "mock"),
        languages=ocr_dict.get("languages", ["en", "fr", "zh-TW"]),
        confidence_threshold=ocr_dict.get("confidence_threshold", 0.7),
        timeout_seconds=ocr_dict.get("timeout_seconds", 30),
        options=ocr_dict.get("options", {})
    )
    
    translator_dict = plugins_dict.get("translator", {})
    translator_config = TranslatorPluginConfig(
        engine=translator_dict.get("engine", "mock"),
        source_language=translator_dict.get("source_language", "auto"),
        target_languages=translator_dict.get("target_languages", ["en", "fr"]),
        confidence_threshold=translator_dict.get("confidence_threshold", 0.7),
        timeout_seconds=translator_dict.get("timeout_seconds", 30),
        options=translator_dict.get("options", {})
    )
    
    search_dict = plugins_dict.get("search", {})
    search_config = SearchPluginConfig(
        engine=search_dict.get("engine", "mock"),
        host=search_dict.get("host", "localhost"),
        port=search_dict.get("port", 7700),
        index_name=search_dict.get("index_name", "documents"),
        api_key=search_dict.get("api_key"),
        timeout_seconds=search_dict.get("timeout_seconds", 30),
        options=search_dict.get("options", {})
    )
    
    plugins_config = PluginsConfig(
        ocr=ocr_config,
        translator=translator_config,
        search=search_config
    )
    
    # Extract paths section for root directories
    paths_section = config_dict.get("paths", {})
    
    return Config(
        logging=logging_config,
        paths=paths_config,
        plugins=plugins_config,
        index_root=paths_section.get("index_root", "index"),
        sources_root=paths_section.get("sources_root", "_sources"),
        volumes_root=paths_section.get("volumes_root", "_Volumes"),
        input_dir=config_dict.get("input_dir", "input"),
        output_dir=config_dict.get("output_dir", "output"),
        temp_dir=config_dict.get("temp_dir", "temp")
    )


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from TOML file with environment overrides.
    
    Args:
        config_path: Optional path to config file. If None, searches default locations.
    
    Returns:
        Config object with validated settings
    
    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config validation fails
    
    Example:
        >>> config = load_config()
        >>> config = load_config("custom_config.toml")
        >>> config = load_config()  # Uses INDEXAO_CONFIG env var
    """
    global _config, _plugin_manager
    
    # Find config file
    path = _find_config_file(Path(config_path) if config_path else None)
    logger.info(f"Loading configuration from: {path}")
    
    # Load TOML
    try:
        with open(path, "rb") as f:
            config_dict = tomllib.load(f)
        logger.debug(f"Loaded {len(config_dict)} top-level sections")
    except Exception as e:
        logger.error(f"Failed to parse TOML: {e}")
        raise ValueError(f"Invalid TOML configuration: {e}")
    
    # Extract and expand path variables
    try:
        path_variables = _extract_path_variables(config_dict)
        if path_variables:
            logger.debug(f"Expanding path variables: {list(path_variables.keys())}")
            config_dict = _expand_path_variables(config_dict, path_variables)
    except Exception as e:
        logger.error(f"Failed to expand path variables: {e}")
        raise ValueError(f"Path variable expansion failed: {e}")
    
    # Apply environment overrides
    config_dict = _apply_env_overrides(config_dict)
    
    # Convert to Config object
    try:
        _config = _dict_to_config(config_dict)
        logger.info(f"Configuration loaded: {_config}")
    except Exception as e:
        logger.error(f"Failed to build config: {e}")
        raise ValueError(f"Configuration validation failed: {e}")
    
    # Reconfigure logger with correct log directory from config
    try:
        reconfigure_logger(_config.logging.log_dir)
        logger.info(f"Logger reconfigured to: {_config.logging.log_dir}")
    except Exception as e:
        logger.warning(f"Failed to reconfigure logger: {e}")
    
    # Initialize Plugin Manager with full config dict (includes plugins section)
    try:
        _plugin_manager = PluginManager(config=config_dict)
        logger.info("Plugin Manager initialized")
    except Exception as e:
        logger.warning(f"Plugin Manager initialization failed: {e}")
        _plugin_manager = None
    
    return _config


def get_config() -> Config:
    """
    Get current configuration.
    
    Returns:
        Current Config object
    
    Raises:
        RuntimeError: If config not yet loaded
    
    Example:
        >>> config = get_config()
        >>> log_level = config.logging.level
    """
    if _config is None:
        raise RuntimeError("Configuration not loaded. Call load_config() first.")
    return _config


def reload_config(config_path: Optional[str] = None) -> Config:
    """
    Reload configuration from file.
    
    Args:
        config_path: Optional path to config file
    
    Returns:
        Reloaded Config object
    """
    global _config, _plugin_manager
    _config = None
    _plugin_manager = None
    return load_config(config_path)


def get_plugin_manager() -> PluginManager:
    """
    Get Plugin Manager instance.
    
    Returns:
        PluginManager instance initialized with config
    
    Raises:
        RuntimeError: If config not yet loaded
    
    Example:
        >>> manager = get_plugin_manager()
        >>> manager.switch('ocr', 'tesseract')
        >>> ocr = manager.get_active('ocr')
    """
    if _plugin_manager is None:
        raise RuntimeError("Plugin Manager not initialized. Call load_config() first.")
    return _plugin_manager
