"""Unit tests for configuration management."""

import pytest
import os
import tempfile
from pathlib import Path

from indexao.config import (
    load_config,
    get_config,
    reload_config,
    Config,
    LoggingConfig,
    PathAdapterConfig,
    OCRPluginConfig,
    TranslatorPluginConfig,
    SearchPluginConfig,
    PluginsConfig,
    LogLevel,
    _find_config_file,
    _apply_env_overrides,
    _dict_to_config
)


class TestConfigDataclasses:
    """Tests for configuration dataclasses."""
    
    def test_logging_config_defaults(self):
        """Test LoggingConfig with default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.console_enabled is True
        assert config.file_enabled is True
        assert config.json_enabled is False
        assert config.log_dir == "logs"
    
    def test_logging_config_validation(self):
        """Test LoggingConfig validates log level."""
        # Valid levels
        for level in ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level
        
        # Invalid level
        with pytest.raises(ValueError, match="Invalid log level"):
            LoggingConfig(level="INVALID")
    
    def test_logging_config_case_insensitive(self):
        """Test LoggingConfig normalizes log level to uppercase."""
        config = LoggingConfig(level="debug")
        assert config.level == "DEBUG"
    
    def test_path_adapter_config_defaults(self):
        """Test PathAdapterConfig defaults."""
        config = PathAdapterConfig()
        assert config.cache_enabled is True
        assert config.cache_ttl_seconds == 300
        assert config.retry_enabled is True
        assert config.retry_attempts == 3
    
    def test_ocr_plugin_config_defaults(self):
        """Test OCRPluginConfig defaults."""
        config = OCRPluginConfig()
        assert config.engine == "mock"
        assert "en" in config.languages
        assert config.confidence_threshold == 0.7
        assert config.timeout_seconds == 30
    
    def test_translator_plugin_config_defaults(self):
        """Test TranslatorPluginConfig defaults."""
        config = TranslatorPluginConfig()
        assert config.engine == "mock"
        assert config.source_language == "auto"
        assert "en" in config.target_languages
    
    def test_search_plugin_config_defaults(self):
        """Test SearchPluginConfig defaults."""
        config = SearchPluginConfig()
        assert config.engine == "mock"
        assert config.host == "localhost"
        assert config.port == 7700
        assert config.index_name == "documents"
    
    def test_plugins_config_composition(self):
        """Test PluginsConfig contains all plugin configs."""
        config = PluginsConfig()
        assert isinstance(config.ocr, OCRPluginConfig)
        assert isinstance(config.translator, TranslatorPluginConfig)
        assert isinstance(config.search, SearchPluginConfig)
    
    def test_config_main_container(self):
        """Test Config main container."""
        config = Config()
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.paths, PathAdapterConfig)
        assert isinstance(config.plugins, PluginsConfig)
        assert config.input_dir == "input"
        assert config.output_dir == "output"


class TestConfigFileDiscovery:
    """Tests for configuration file discovery."""
    
    def test_find_explicit_path(self, tmp_path):
        """Test finding config with explicit path."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("[logging]\nlevel = 'INFO'\n")
        
        found = _find_config_file(config_file)
        assert found == config_file
    
    def test_find_explicit_path_not_found(self):
        """Test explicit path that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            _find_config_file(Path("/nonexistent/config.toml"))
    
    def test_find_via_env_var(self, tmp_path, monkeypatch):
        """Test finding config via INDEXAO_CONFIG env var."""
        config_file = tmp_path / "custom.toml"
        config_file.write_text("[logging]\nlevel = 'INFO'\n")
        
        monkeypatch.setenv("INDEXAO_CONFIG", str(config_file))
        found = _find_config_file()
        assert found == config_file
    
    def test_find_no_config(self, tmp_path, monkeypatch):
        """Test error when no config file found."""
        # Change to temp dir with no config files
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("INDEXAO_CONFIG", raising=False)
        
        with pytest.raises(FileNotFoundError, match="No configuration file found"):
            _find_config_file()


class TestEnvOverrides:
    """Tests for environment variable overrides."""
    
    def test_apply_string_override(self):
        """Test applying string env override."""
        config = {"logging": {"level": "INFO"}}
        os.environ["INDEXAO_LOGGING_LEVEL"] = "DEBUG"
        
        result = _apply_env_overrides(config)
        assert result["logging"]["level"] == "DEBUG"
        
        del os.environ["INDEXAO_LOGGING_LEVEL"]
    
    def test_apply_bool_override(self):
        """Test applying boolean env override."""
        config = {"logging": {"console": {"enabled": False}}}
        os.environ["INDEXAO_LOGGING_CONSOLE_ENABLED"] = "true"
        
        result = _apply_env_overrides(config)
        assert result["logging"]["console"]["enabled"] is True
        
        del os.environ["INDEXAO_LOGGING_CONSOLE_ENABLED"]
    
    def test_apply_int_override(self):
        """Test applying integer env override."""
        config = {"paths": {"adapters": {"cache_ttl_seconds": 300}}}
        os.environ["INDEXAO_PATHS_ADAPTERS_CACHE_TTL_SECONDS"] = "600"
        
        result = _apply_env_overrides(config)
        assert result["paths"]["adapters"]["cache_ttl_seconds"] == 600
        
        del os.environ["INDEXAO_PATHS_ADAPTERS_CACHE_TTL_SECONDS"]
    
    def test_apply_float_override(self):
        """Test applying float env override."""
        config = {"plugins": {"ocr": {"confidence_threshold": 0.7}}}
        os.environ["INDEXAO_PLUGINS_OCR_CONFIDENCE_THRESHOLD"] = "0.85"
        
        result = _apply_env_overrides(config)
        assert result["plugins"]["ocr"]["confidence_threshold"] == 0.85
        
        del os.environ["INDEXAO_PLUGINS_OCR_CONFIDENCE_THRESHOLD"]
    
    def test_ignore_non_indexao_env_vars(self):
        """Test that non-INDEXAO env vars are ignored."""
        config = {"logging": {"level": "INFO"}}
        os.environ["OTHER_VAR"] = "VALUE"
        
        result = _apply_env_overrides(config)
        assert "other" not in result
        
        del os.environ["OTHER_VAR"]
    
    def test_nested_section_creation(self):
        """Test creating nested sections via env vars."""
        config = {}
        os.environ["INDEXAO_PLUGINS_OCR_ENGINE"] = "tesseract"
        
        result = _apply_env_overrides(config)
        assert result["plugins"]["ocr"]["engine"] == "tesseract"
        
        del os.environ["INDEXAO_PLUGINS_OCR_ENGINE"]


class TestDictToConfig:
    """Tests for dictionary to Config conversion."""
    
    def test_minimal_config(self):
        """Test conversion with minimal config."""
        config_dict = {}
        config = _dict_to_config(config_dict)
        
        assert isinstance(config, Config)
        assert config.logging.level == "INFO"
        assert config.plugins.ocr.engine == "mock"
    
    def test_full_logging_section(self):
        """Test conversion with full logging section."""
        config_dict = {
            "logging": {
                "level": "DEBUG",
                "console": {"enabled": True},
                "file": {
                    "enabled": True,
                    "dir": "custom_logs",
                    "rotation_when": "weekly",
                    "rotation_interval": 2,
                    "backup_count": 14
                },
                "json": {"enabled": True},
                "performance": {"slow_threshold_ms": 500.0}
            }
        }
        
        config = _dict_to_config(config_dict)
        assert config.logging.level == "DEBUG"
        assert config.logging.console_enabled is True
        assert config.logging.log_dir == "custom_logs"
        assert config.logging.rotation_when == "weekly"
        assert config.logging.slow_threshold_ms == 500.0
    
    def test_full_plugins_section(self):
        """Test conversion with full plugins section."""
        config_dict = {
            "plugins": {
                "ocr": {
                    "engine": "tesseract",
                    "languages": ["en", "fr", "de"],
                    "confidence_threshold": 0.8,
                    "timeout_seconds": 60
                },
                "translator": {
                    "engine": "argostranslate",
                    "source_language": "en",
                    "target_languages": ["fr", "es"],
                    "confidence_threshold": 0.9
                },
                "search": {
                    "engine": "meilisearch",
                    "host": "search.example.com",
                    "port": 7700,
                    "index_name": "docs",
                    "api_key": "secret123"
                }
            }
        }
        
        config = _dict_to_config(config_dict)
        assert config.plugins.ocr.engine == "tesseract"
        assert "de" in config.plugins.ocr.languages
        assert config.plugins.translator.engine == "argostranslate"
        assert config.plugins.search.host == "search.example.com"
        assert config.plugins.search.api_key == "secret123"


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_from_file(self, tmp_path, monkeypatch):
        """Test loading config from TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[logging]
level = "DEBUG"

[plugins.ocr]
engine = "tesseract"
languages = ["en", "fr"]
""")
        
        monkeypatch.chdir(tmp_path)
        config = load_config(str(config_file))
        
        assert config.logging.level == "DEBUG"
        assert config.plugins.ocr.engine == "tesseract"
    
    def test_load_with_env_overrides(self, tmp_path, monkeypatch):
        """Test loading config with env var overrides."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[logging]
level = "INFO"

[plugins.ocr]
engine = "mock"
""")
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("INDEXAO_LOGGING_LEVEL", "TRACE")
        monkeypatch.setenv("INDEXAO_PLUGINS_OCR_ENGINE", "tesseract")
        
        config = load_config(str(config_file))
        
        assert config.logging.level == "TRACE"  # Overridden
        assert config.plugins.ocr.engine == "tesseract"  # Overridden
    
    def test_load_invalid_toml(self, tmp_path):
        """Test loading invalid TOML raises error."""
        config_file = tmp_path / "bad.toml"
        config_file.write_text("invalid toml [[[")
        
        with pytest.raises(ValueError, match="Invalid TOML configuration"):
            load_config(str(config_file))
    
    def test_get_config_before_load(self):
        """Test get_config raises error if not loaded."""
        # Reset global config
        import indexao.config
        indexao.config._config = None
        
        with pytest.raises(RuntimeError, match="Configuration not loaded"):
            get_config()
    
    def test_get_config_after_load(self, tmp_path, monkeypatch):
        """Test get_config returns loaded config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("[logging]\nlevel = 'INFO'\n")
        
        monkeypatch.chdir(tmp_path)
        loaded = load_config(str(config_file))
        retrieved = get_config()
        
        assert retrieved is loaded
        assert retrieved.logging.level == "INFO"
    
    def test_reload_config(self, tmp_path, monkeypatch):
        """Test reload_config reloads from file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("[logging]\nlevel = 'INFO'\n")
        
        monkeypatch.chdir(tmp_path)
        config1 = load_config(str(config_file))
        assert config1.logging.level == "INFO"
        
        # Modify file
        config_file.write_text("[logging]\nlevel = 'DEBUG'\n")
        
        config2 = reload_config(str(config_file))
        assert config2.logging.level == "DEBUG"


class TestConfigIntegration:
    """Integration tests for full configuration workflow."""
    
    def test_full_workflow(self, tmp_path, monkeypatch):
        """Test complete config workflow: load, get, use."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
# Top-level directories (must come before sections)
input_dir = "data/input"
output_dir = "data/output"
temp_dir = "/tmp/indexao"

[logging]
level = "DEBUG"
[logging.console]
enabled = true
[logging.file]
enabled = true
dir = "logs"
rotation_when = "midnight"

[paths.adapters]
cache_enabled = true
cache_ttl_seconds = 600
retry_enabled = true
retry_attempts = 5

[plugins.ocr]
engine = "tesseract"
languages = ["en", "fr", "zh-TW"]
confidence_threshold = 0.8

[plugins.translator]
engine = "argostranslate"
source_language = "auto"
target_languages = ["en", "fr", "es"]

[plugins.search]
engine = "meilisearch"
host = "localhost"
port = 7700
index_name = "documents"
""")
        
        monkeypatch.chdir(tmp_path)
        config = load_config(str(config_file))
        
        # Verify all sections loaded correctly
        assert config.logging.level == "DEBUG"
        assert config.logging.console_enabled is True
        assert config.logging.log_dir == "logs"
        
        assert config.paths.cache_enabled is True
        assert config.paths.cache_ttl_seconds == 600
        assert config.paths.retry_attempts == 5
        
        assert config.plugins.ocr.engine == "tesseract"
        assert "zh-TW" in config.plugins.ocr.languages
        assert config.plugins.ocr.confidence_threshold == 0.8
        
        assert config.plugins.translator.engine == "argostranslate"
        assert "es" in config.plugins.translator.target_languages
        
        assert config.plugins.search.engine == "meilisearch"
        assert config.plugins.search.port == 7700
        
        assert config.input_dir == "data/input"
        assert config.output_dir == "data/output"
        assert config.temp_dir == "/tmp/indexao"
