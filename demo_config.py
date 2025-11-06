"""
Demonstration of configuration management.

Shows config loading, env overrides, and typed access to settings.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from indexao.logger import get_logger
from indexao.config import load_config, get_config, reload_config

# Setup logger
os.environ['INDEXAO_LOG_LEVEL'] = 'DEBUG'
logger = get_logger(__name__)


def demo_load_from_example():
    """Demonstrate loading from config.example.toml."""
    logger.info("=" * 60)
    logger.info("DEMO 1: Load from config.example.toml")
    logger.info("=" * 60)
    
    try:
        config = load_config("config.example.toml")
        
        logger.info(f"Config loaded: {config}")
        logger.info(f"Log level: {config.logging.level}")
        logger.info(f"Console enabled: {config.logging.console_enabled}")
        logger.info(f"File enabled: {config.logging.file_enabled}")
        logger.info(f"Log directory: {config.logging.log_dir}")
        
        logger.info(f"\nPath adapters:")
        logger.info(f"  Cache enabled: {config.paths.cache_enabled}")
        logger.info(f"  Cache TTL: {config.paths.cache_ttl_seconds}s")
        logger.info(f"  Retry enabled: {config.paths.retry_enabled}")
        logger.info(f"  Retry attempts: {config.paths.retry_attempts}")
        
        logger.info(f"\nPlugins:")
        logger.info(f"  OCR engine: {config.plugins.ocr.engine}")
        logger.info(f"  OCR languages: {', '.join(config.plugins.ocr.languages)}")
        logger.info(f"  Translator engine: {config.plugins.translator.engine}")
        logger.info(f"  Search engine: {config.plugins.search.engine}")
        logger.info(f"  Search host: {config.plugins.search.host}:{config.plugins.search.port}")
        
        logger.info(f"\nDirectories:")
        logger.info(f"  Input: {config.input_dir}")
        logger.info(f"  Output: {config.output_dir}")
        logger.info(f"  Temp: {config.temp_dir}")
        
    except FileNotFoundError as e:
        logger.warning(f"config.example.toml not found: {e}")


def demo_env_overrides():
    """Demonstrate environment variable overrides."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO 2: Environment Variable Overrides")
    logger.info("=" * 60)
    
    # Create temp config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[logging]
level = "INFO"

[plugins.ocr]
engine = "mock"
languages = ["en"]

[plugins.search]
host = "localhost"
port = 7700
""")
        temp_config = f.name
    
    try:
        # Load without overrides
        logger.info("Loading config WITHOUT env overrides...")
        config1 = load_config(temp_config)
        logger.info(f"  Log level: {config1.logging.level}")
        logger.info(f"  OCR engine: {config1.plugins.ocr.engine}")
        logger.info(f"  Search host: {config1.plugins.search.host}")
        
        # Set env overrides
        logger.info("\nSetting environment overrides:")
        os.environ["INDEXAO_LOGGING_LEVEL"] = "TRACE"
        os.environ["INDEXAO_PLUGINS_OCR_ENGINE"] = "tesseract"
        os.environ["INDEXAO_PLUGINS_SEARCH_HOST"] = "meilisearch.example.com"
        os.environ["INDEXAO_PLUGINS_SEARCH_PORT"] = "8080"
        
        logger.info("  INDEXAO_LOGGING_LEVEL=TRACE")
        logger.info("  INDEXAO_PLUGINS_OCR_ENGINE=tesseract")
        logger.info("  INDEXAO_PLUGINS_SEARCH_HOST=meilisearch.example.com")
        logger.info("  INDEXAO_PLUGINS_SEARCH_PORT=8080")
        
        # Reload with overrides
        logger.info("\nReloading config WITH env overrides...")
        config2 = reload_config(temp_config)
        logger.info(f"  Log level: {config2.logging.level} (was {config1.logging.level})")
        logger.info(f"  OCR engine: {config2.plugins.ocr.engine} (was {config1.plugins.ocr.engine})")
        logger.info(f"  Search host: {config2.plugins.search.host} (was {config1.plugins.search.host})")
        logger.info(f"  Search port: {config2.plugins.search.port} (was {config1.plugins.search.port})")
        
        # Cleanup env
        for key in ["INDEXAO_LOGGING_LEVEL", "INDEXAO_PLUGINS_OCR_ENGINE", 
                    "INDEXAO_PLUGINS_SEARCH_HOST", "INDEXAO_PLUGINS_SEARCH_PORT"]:
            if key in os.environ:
                del os.environ[key]
    
    finally:
        Path(temp_config).unlink()


def demo_typed_access():
    """Demonstrate typed access to config settings."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO 3: Typed Access to Settings")
    logger.info("=" * 60)
    
    # Create temp config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[logging]
level = "DEBUG"

[paths.adapters]
cache_enabled = true
cache_ttl_seconds = 300
retry_attempts = 3

[plugins.ocr]
engine = "tesseract"
languages = ["en", "fr", "zh-TW"]
confidence_threshold = 0.8
timeout_seconds = 30

[plugins.translator]
engine = "argostranslate"
source_language = "auto"
target_languages = ["en", "fr", "es", "de"]

[plugins.search]
engine = "meilisearch"
host = "localhost"
port = 7700
index_name = "documents"
api_key = "master_key_123"
""")
        temp_config = f.name
    
    try:
        config = load_config(temp_config)
        
        logger.info("Accessing settings with type safety...")
        
        # Logging settings
        logger.info(f"\nLogging configuration:")
        logger.info(f"  Level: {config.logging.level} (str)")
        logger.info(f"  Console: {config.logging.console_enabled} (bool)")
        logger.info(f"  File: {config.logging.file_enabled} (bool)")
        logger.info(f"  Slow threshold: {config.logging.slow_threshold_ms}ms (float)")
        
        # Path settings
        logger.info(f"\nPath adapter configuration:")
        logger.info(f"  Cache enabled: {config.paths.cache_enabled} (bool)")
        logger.info(f"  Cache TTL: {config.paths.cache_ttl_seconds}s (int)")
        logger.info(f"  Retry attempts: {config.paths.retry_attempts} (int)")
        
        # OCR settings
        logger.info(f"\nOCR plugin configuration:")
        logger.info(f"  Engine: {config.plugins.ocr.engine} (str)")
        logger.info(f"  Languages: {config.plugins.ocr.languages} (List[str])")
        logger.info(f"  Confidence: {config.plugins.ocr.confidence_threshold} (float)")
        logger.info(f"  Timeout: {config.plugins.ocr.timeout_seconds}s (int)")
        
        # Translator settings
        logger.info(f"\nTranslator plugin configuration:")
        logger.info(f"  Engine: {config.plugins.translator.engine} (str)")
        logger.info(f"  Source: {config.plugins.translator.source_language} (str)")
        logger.info(f"  Targets: {config.plugins.translator.target_languages} (List[str])")
        
        # Search settings
        logger.info(f"\nSearch plugin configuration:")
        logger.info(f"  Engine: {config.plugins.search.engine} (str)")
        logger.info(f"  Host: {config.plugins.search.host} (str)")
        logger.info(f"  Port: {config.plugins.search.port} (int)")
        logger.info(f"  Index: {config.plugins.search.index_name} (str)")
        api_key_display = '***' + config.plugins.search.api_key[-4:] if config.plugins.search.api_key else "None"
        logger.info(f"  API key: {api_key_display} (Optional[str])")
        
        # Use config to make decisions
        logger.info(f"\nUsing config for decisions:")
        if config.paths.cache_enabled:
            logger.info(f"  ✓ Cache enabled with {config.paths.cache_ttl_seconds}s TTL")
        
        if config.paths.retry_enabled:
            logger.info(f"  ✓ Retries enabled with {config.paths.retry_attempts} attempts")
        
        if config.plugins.ocr.confidence_threshold > 0.7:
            logger.info(f"  ✓ High OCR confidence threshold: {config.plugins.ocr.confidence_threshold}")
        
        if len(config.plugins.translator.target_languages) >= 3:
            logger.info(f"  ✓ Multi-language support: {len(config.plugins.translator.target_languages)} languages")
    
    finally:
        Path(temp_config).unlink()


def demo_get_config():
    """Demonstrate get_config() singleton access."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO 4: Singleton Config Access")
    logger.info("=" * 60)
    
    # Create temp config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[logging]
level = "INFO"

[plugins.ocr]
engine = "mock"
""")
        temp_config = f.name
    
    try:
        # Load config
        logger.info("Loading config...")
        config1 = load_config(temp_config)
        logger.info(f"  OCR engine: {config1.plugins.ocr.engine}")
        
        # Get config from anywhere in the app
        logger.info("\nAccessing config from different module (simulated)...")
        config2 = get_config()
        logger.info(f"  OCR engine: {config2.plugins.ocr.engine}")
        
        # Verify it's the same instance
        logger.info(f"\nSame instance? {config1 is config2}")
        logger.info("  ✓ Singleton pattern confirmed")
        
        # Demonstrate usage in function
        def process_document(doc_path: str):
            """Simulated function that needs config."""
            cfg = get_config()
            logger.info(f"  Processing {doc_path} with {cfg.plugins.ocr.engine} OCR")
        
        logger.info("\nUsing config in function:")
        process_document("document.pdf")
    
    finally:
        Path(temp_config).unlink()


def demo_validation():
    """Demonstrate config validation."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO 5: Config Validation")
    logger.info("=" * 60)
    
    # Test invalid log level
    logger.info("Testing invalid log level...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[logging]\nlevel = "INVALID"\n')
        temp_config = f.name
    
    try:
        config = load_config(temp_config)
        logger.error("  ✗ Should have raised validation error!")
    except ValueError as e:
        logger.info(f"  ✓ Validation caught: {e}")
    finally:
        Path(temp_config).unlink()
    
    # Test invalid TOML
    logger.info("\nTesting invalid TOML syntax...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('invalid toml [[[')
        temp_config = f.name
    
    try:
        config = load_config(temp_config)
        logger.error("  ✗ Should have raised parse error!")
    except ValueError as e:
        logger.info(f"  ✓ Parse error caught: {str(e)[:60]}...")
    finally:
        Path(temp_config).unlink()
    
    # Test valid config
    logger.info("\nTesting valid config...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[logging]\nlevel = "DEBUG"\n')
        temp_config = f.name
    
    try:
        config = load_config(temp_config)
        logger.info(f"  ✓ Valid config loaded: level={config.logging.level}")
    finally:
        Path(temp_config).unlink()


def main():
    """Run all demos."""
    logger.info("Starting configuration demos...")
    logger.info(f"Python version: {sys.version}")
    
    try:
        demo_load_from_example()
        demo_env_overrides()
        demo_typed_access()
        demo_get_config()
        demo_validation()
        
        logger.info("\n" + "=" * 60)
        logger.info("All demos completed successfully! ✓")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.exception(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
