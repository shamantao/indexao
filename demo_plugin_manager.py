#!/usr/bin/env python3
"""
Démo du Plugin Manager - Sprint 2 Task 2.1

Ce script démontre:
1. Chargement de la config TOML
2. Initialisation du Plugin Manager
3. Enregistrement manuel d'adapters
4. Hot-swap entre adapters
5. Utilisation de l'adapter actif

Usage:
    python demo_plugin_manager.py
"""

from indexao.config import load_config, get_plugin_manager
from indexao.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# MOCK ADAPTERS FOR DEMO
# ============================================================================

class MockOCRAdapter:
    """Mock OCR adapter for testing"""
    def __init__(self, config=None):
        self.config = config or {}
        logger.info(f"MockOCRAdapter initialized with config: {config}")
    
    def extract(self, file_path: str):
        logger.info(f"MockOCR: Extracting text from {file_path}")
        return {
            "text": "This is mock OCR text",
            "confidence": 0.95,
            "engine": "mock"
        }


class TesseractOCRAdapter:
    """Tesseract OCR adapter (mock for demo)"""
    def __init__(self, config=None):
        self.config = config or {}
        self.lang = self.config.get('lang', 'eng')
        logger.info(f"TesseractOCRAdapter initialized - lang={self.lang}")
    
    def extract(self, file_path: str):
        logger.info(f"Tesseract OCR: Extracting text from {file_path} (lang={self.lang})")
        return {
            "text": f"Tesseract extracted text [{self.lang}]",
            "confidence": 0.98,
            "engine": "tesseract",
            "languages": self.lang.split('+')
        }


class MockTranslatorAdapter:
    """Mock Translator adapter"""
    def __init__(self, config=None):
        self.config = config or {}
        logger.info(f"MockTranslatorAdapter initialized")
    
    def translate(self, text: str, target_lang: str):
        logger.info(f"MockTranslator: Translating to {target_lang}")
        return {
            "translated": f"[{target_lang}] {text}",
            "source_lang": "auto",
            "target_lang": target_lang,
            "engine": "mock"
        }


# ============================================================================
# DEMO WORKFLOW
# ============================================================================

def demo_basic_workflow():
    """Démo du workflow de base"""
    print("\n" + "="*70)
    print("DÉMO 1: Workflow de base - Register + Switch + Use")
    print("="*70)
    
    # 1. Load configuration
    print("\n[1] Loading configuration...")
    config = load_config()
    print(f"✓ Config loaded: log_level={config.logging.level}")
    
    # 2. Get Plugin Manager
    print("\n[2] Getting Plugin Manager...")
    manager = get_plugin_manager()
    print("✓ Plugin Manager initialized")
    
    # 3. Register adapters manually (for testing)
    print("\n[3] Registering adapters...")
    manager.register('ocr', 'mock', MockOCRAdapter)
    manager.register('ocr', 'tesseract', TesseractOCRAdapter)
    manager.register('translator', 'mock', MockTranslatorAdapter)
    
    registered_ocr = manager.get_registered('ocr')
    print(f"✓ Registered OCR adapters: {list(registered_ocr.keys())}")
    
    # 4. Check adapter config from TOML
    print("\n[4] Checking adapter config from TOML...")
    tesseract_config = manager.get_adapter_config('ocr', 'tesseract')
    print(f"✓ Tesseract config: {tesseract_config}")
    
    # 5. Switch to mock adapter
    print("\n[5] Switching to mock adapter...")
    manager.switch('ocr', 'mock')
    ocr = manager.get_active('ocr')
    print(f"✓ Active adapter: {type(ocr).__name__}")
    
    # 6. Use adapter
    print("\n[6] Using mock adapter...")
    result = ocr.extract("/fake/document.pdf")
    print(f"✓ Result: {result}")
    
    # 7. Hot-swap to tesseract
    print("\n[7] Hot-swapping to tesseract...")
    manager.switch('ocr', 'tesseract')
    ocr = manager.get_active('ocr')
    print(f"✓ Active adapter: {type(ocr).__name__}")
    
    # 8. Use tesseract (config loaded from TOML)
    print("\n[8] Using tesseract adapter...")
    result = ocr.extract("/fake/document.pdf")
    print(f"✓ Result: {result}")
    print(f"✓ Languages from config: {result.get('languages', [])}")


def demo_adapter_switching():
    """Démo du hot-swap d'adapters"""
    print("\n" + "="*70)
    print("DÉMO 2: Hot-swap d'adapters sans restart")
    print("="*70)
    
    manager = get_plugin_manager()
    
    # Register adapters
    manager.register('ocr', 'mock', MockOCRAdapter)
    manager.register('ocr', 'tesseract', TesseractOCRAdapter)
    
    adapters = ['mock', 'tesseract', 'mock', 'tesseract']
    
    for i, adapter_name in enumerate(adapters, 1):
        print(f"\n[{i}] Switching to {adapter_name}...")
        manager.switch('ocr', adapter_name)
        
        ocr = manager.get_active('ocr')
        result = ocr.extract(f"/document_{i}.pdf")
        
        print(f"  ✓ Active: {type(ocr).__name__}")
        print(f"  ✓ Engine: {result['engine']}")
        print(f"  ✓ Text: {result['text'][:50]}...")


def demo_instance_caching():
    """Démo du caching d'instances (singleton pattern)"""
    print("\n" + "="*70)
    print("DÉMO 3: Instance caching (singleton pattern)")
    print("="*70)
    
    manager = get_plugin_manager()
    
    # Register adapter
    manager.register('ocr', 'mock', MockOCRAdapter)
    
    print("\n[1] First switch to mock...")
    manager.switch('ocr', 'mock')
    instance1 = manager.get_active('ocr')
    print(f"  ✓ Instance ID: {id(instance1)}")
    
    print("\n[2] Switch to None (simulate cleanup)...")
    manager._active['ocr'] = None
    print("  ✓ Active cleared")
    
    print("\n[3] Second switch to mock (should reuse cached instance)...")
    manager.switch('ocr', 'mock')
    instance2 = manager.get_active('ocr')
    print(f"  ✓ Instance ID: {id(instance2)}")
    
    if instance1 is instance2:
        print("\n  ✅ SUCCESS: Same instance (cached)")
    else:
        print("\n  ❌ FAIL: Different instances")


def demo_list_active():
    """Démo de la liste des adapters actifs"""
    print("\n" + "="*70)
    print("DÉMO 4: Liste des adapters actifs")
    print("="*70)
    
    manager = get_plugin_manager()
    
    # Register adapters
    manager.register('ocr', 'mock', MockOCRAdapter)
    manager.register('translator', 'mock', MockTranslatorAdapter)
    
    print("\n[1] Before any switch:")
    active = manager.list_active()
    print(f"  Active adapters: {active}")
    
    print("\n[2] After switching OCR:")
    manager.switch('ocr', 'mock')
    active = manager.list_active()
    print(f"  Active adapters: {active}")
    
    print("\n[3] After switching Translator:")
    manager.switch('translator', 'mock')
    active = manager.list_active()
    print(f"  Active adapters: {active}")


def demo_error_handling():
    """Démo de la gestion d'erreurs"""
    print("\n" + "="*70)
    print("DÉMO 5: Gestion d'erreurs")
    print("="*70)
    
    manager = get_plugin_manager()
    
    # Register only mock
    manager.register('ocr', 'mock', MockOCRAdapter)
    
    print("\n[1] Try to switch to non-existent adapter:")
    try:
        manager.switch('ocr', 'nonexistent')
        print("  ❌ Should have raised PluginLoadError")
    except Exception as e:
        print(f"  ✓ Exception caught: {type(e).__name__}")
        print(f"  ✓ Message: {e}")
    
    print("\n[2] Try to get config for invalid type:")
    try:
        manager.get_adapter_config('invalid_type', 'test')
        print("  ❌ Should have raised PluginManagerError")
    except Exception as e:
        print(f"  ✓ Exception caught: {type(e).__name__}")
        print(f"  ✓ Message: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all demos"""
    print("\n" + "🚀"*35)
    print("🚀  PLUGIN MANAGER DEMO - Sprint 2 Task 2.1  🚀")
    print("🚀"*35)
    
    try:
        demo_basic_workflow()
        demo_adapter_switching()
        demo_instance_caching()
        demo_list_active()
        demo_error_handling()
        
        print("\n" + "="*70)
        print("✅ ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*70)
        print("\nNext steps:")
        print("  - Task 2.2: Interface Validation (Protocol checking)")
        print("  - Task 2.3: Enhanced switching (cleanup hooks)")
        print("  - Task 2.4: Plugin Discovery (auto-detect adapters)")
        print("  - Task 2.5: Dynamic Loading + REST API")
        print()
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()
