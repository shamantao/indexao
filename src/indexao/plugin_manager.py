"""
Plugin Manager - Gestion dynamique des adapters

Architecture:
- Configuration-first: Définir le contrat TOML avant l'implémentation
- Manual registration: Tests avec plugins en dur avant auto-discovery
- Hot-swap: Switch adapters sans restart serveur
- Protocol validation: Vérification interfaces à l'enregistrement

Usage:
    # Configuration
    manager = PluginManager()
    config = manager.get_adapter_config('ocr', 'tesseract')
    
    # Registration (manual - pour tests)
    manager.register('ocr', 'mock', MockOCR)  # Validates protocol
    manager.register('ocr', 'tesseract', TesseractOCR)
    
    # Switching
    manager.switch('ocr', 'tesseract')
    adapter = manager.get_active('ocr')
    
    # Auto-discovery
    plugins = manager.discover_plugins()
    manager.load_adapter('ocr', 'chandra')
"""

import logging
import inspect
import importlib
import pkgutil
import ast
from pathlib import Path
from typing import Dict, Any, Optional, Type, Protocol, get_type_hints, get_args, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Import protocols for validation
try:
    from indexao.adapters.ocr.base import OCRAdapter
    from indexao.adapters.translator.base import TranslatorAdapter
    from indexao.adapters.search.base import SearchAdapter
    PROTOCOLS_AVAILABLE = True
except ImportError:
    logger.warning("Adapter protocols not available, validation disabled")
    PROTOCOLS_AVAILABLE = False
    OCRAdapter = None
    TranslatorAdapter = None
    SearchAdapter = None


@dataclass
class PluginMetadata:
    """Métadonnées d'un plugin"""
    name: str
    type: str  # 'ocr', 'translator', 'search'
    version: str = "0.1.0"
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    enabled: bool = True
    priority: int = 0


class PluginManagerError(Exception):
    """Erreur de gestion de plugin"""
    pass


class PluginLoadError(PluginManagerError):
    """Erreur de chargement de plugin"""
    pass


class PluginValidationError(PluginManagerError):
    """Erreur de validation de plugin"""
    pass


class PluginManager:
    """
    Gestionnaire de plugins pour Indexao
    
    Responsabilités:
    - Charger et valider la configuration TOML par adapter
    - Enregistrer et switcher entre adapters (registration manuelle)
    - Valider les interfaces (Protocol compliance)
    - (Future) Auto-découvrir et charger dynamiquement les plugins
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialiser le gestionnaire de plugins
        
        Args:
            config: Configuration complète (from config.toml)
        """
        self._config = config or {}
        self._registry: Dict[str, Dict[str, Any]] = {
            'ocr': {},
            'translator': {},
            'search': {}
        }
        self._active: Dict[str, Optional[Any]] = {
            'ocr': None,
            'translator': None,
            'search': None
        }
        self._instances: Dict[str, Dict[str, Any]] = {
            'ocr': {},
            'translator': {},
            'search': {}
        }
        
        logger.info("Plugin Manager initialized")
    
    def _get_protocol_for_type(self, adapter_type: str) -> Optional[Type]:
        """
        Get Protocol class for adapter type
        
        Args:
            adapter_type: 'ocr', 'translator', 'search'
        
        Returns:
            Protocol class or None if not available
        """
        if not PROTOCOLS_AVAILABLE:
            return None
        
        protocols = {
            'ocr': OCRAdapter,
            'translator': TranslatorAdapter,
            'search': SearchAdapter
        }
        return protocols.get(adapter_type)
    
    def _validate_protocol(self, adapter_class: Type, adapter_type: str) -> bool:
        """
        Validate that adapter implements required protocol
        
        Args:
            adapter_class: Class to validate
            adapter_type: Type of adapter ('ocr', 'translator', 'search')
        
        Returns:
            True if valid
        
        Raises:
            PluginValidationError: If protocol not implemented correctly
        
        Example:
            >>> self._validate_protocol(TesseractOCR, 'ocr')
            True
        """
        protocol = self._get_protocol_for_type(adapter_type)
        
        if protocol is None:
            logger.warning(f"Protocol validation skipped for {adapter_type} (not available)")
            return True
        
        # Get protocol required methods
        protocol_methods = {
            'ocr': ['name', 'supported_languages', 'process_image'],
            'translator': ['name', 'supported_languages', 'translate', 'translate_batch'],
            'search': ['name', 'index_document', 'index_batch', 'search', 'delete_document']
        }
        
        required_methods = protocol_methods.get(adapter_type, [])
        
        # Check each required method/property
        missing_methods = []
        for method_name in required_methods:
            if not hasattr(adapter_class, method_name):
                missing_methods.append(method_name)
        
        if missing_methods:
            raise PluginValidationError(
                f"{adapter_class.__name__} missing required methods: {', '.join(missing_methods)}\n"
                f"Required for {adapter_type}: {', '.join(required_methods)}"
            )
        
        # Validate method signatures (basic check)
        try:
            # Check if class has __init__ that accepts config
            init_sig = inspect.signature(adapter_class.__init__)
            params = list(init_sig.parameters.keys())
            
            # Must have 'self' and optionally 'config' or **kwargs
            if len(params) < 1:
                raise PluginValidationError(
                    f"{adapter_class.__name__}.__init__ must accept parameters"
                )
        except Exception as e:
            logger.warning(f"Could not validate {adapter_class.__name__} signature: {e}")
        
        logger.debug(f"Protocol validation passed for {adapter_class.__name__}")
        return True
    
    def get_adapter_config(self, adapter_type: str, adapter_name: str) -> Dict[str, Any]:
        """
        Récupérer la configuration d'un adapter spécifique
        
        Args:
            adapter_type: Type d'adapter ('ocr', 'translator', 'search')
            adapter_name: Nom de l'adapter ('mock', 'tesseract', 'argos', etc.)
        
        Returns:
            Configuration de l'adapter (merged: global + specific)
        
        Raises:
            PluginManagerError: Si configuration invalide
        
        Example:
            >>> manager = PluginManager(config)
            >>> ocr_config = manager.get_adapter_config('ocr', 'tesseract')
            >>> print(ocr_config['languages'])  # ['en', 'fr']
        """
        if adapter_type not in ['ocr', 'translator', 'search']:
            raise PluginManagerError(f"Invalid adapter type: {adapter_type}")
        
        # Structure attendue dans config.toml:
        # [plugins.ocr.tesseract]
        # enabled = true
        # languages = ["en", "fr"]
        # dpi = 300
        
        plugins_config = self._config.get('plugins', {})
        type_config = plugins_config.get(adapter_type, {})
        adapter_config = type_config.get(adapter_name, {})
        
        if not adapter_config:
            logger.warning(f"No config found for {adapter_type}.{adapter_name}, using defaults")
            return {}
        
        logger.debug(f"Loaded config for {adapter_type}.{adapter_name}: {len(adapter_config)} keys")
        return dict(adapter_config)  # Return copy
    
    def register(self, adapter_type: str, adapter_name: str, adapter_class: Type, validate: bool = True) -> None:
        """
        Enregistrer manuellement un adapter (pour tests/développement)
        
        Args:
            adapter_type: Type d'adapter
            adapter_name: Nom de l'adapter
            adapter_class: Classe de l'adapter (non instanciée)
            validate: Si True, valider le protocol (default: True)
        
        Raises:
            PluginManagerError: Si type invalide
            PluginValidationError: Si protocol non respecté
        
        Example:
            >>> from indexao.adapters.mock_ocr import MockOCR
            >>> manager.register('ocr', 'mock', MockOCR)
        """
        if adapter_type not in self._registry:
            raise PluginManagerError(f"Invalid adapter type: {adapter_type}")
        
        # Validate protocol before registration
        if validate:
            self._validate_protocol(adapter_class, adapter_type)
        
        self._registry[adapter_type][adapter_name] = adapter_class
        logger.info(f"Registered {adapter_type}.{adapter_name} -> {adapter_class.__name__}")
    
    def get_registered(self, adapter_type: str) -> Dict[str, Type]:
        """
        Lister les adapters enregistrés d'un type
        
        Args:
            adapter_type: Type d'adapter
        
        Returns:
            Dictionnaire {name: class}
        
        Example:
            >>> ocr_adapters = manager.get_registered('ocr')
            >>> print(ocr_adapters.keys())  # dict_keys(['mock', 'tesseract'])
        """
        return dict(self._registry.get(adapter_type, {}))
    
    def switch(self, adapter_type: str, adapter_name: str) -> None:
        """
        Switcher vers un autre adapter (hot-swap sans restart)
        
        Gère le cleanup automatique si l'adapter a une méthode close().
        Track l'historique des switches pour debugging.
        
        Args:
            adapter_type: Type d'adapter
            adapter_name: Nom de l'adapter cible
        
        Raises:
            PluginLoadError: Si adapter non enregistré
        
        Example:
            >>> manager.switch('ocr', 'tesseract')  # mock → tesseract
            >>> manager.switch('ocr', 'mock')       # tesseract → mock (calls tesseract.close())
        """
        if adapter_type not in self._registry:
            raise PluginManagerError(f"Invalid adapter type: {adapter_type}")
        
        if adapter_name not in self._registry[adapter_type]:
            available = list(self._registry[adapter_type].keys())
            raise PluginLoadError(
                f"Adapter {adapter_type}.{adapter_name} not registered. "
                f"Available: {available}"
            )
        
        # Cleanup previous adapter with hooks
        previous_adapter = self._active[adapter_type]
        if previous_adapter:
            previous_name = self._find_instance_name(adapter_type, previous_adapter)
            logger.debug(f"Unloading previous {adapter_type} adapter: {previous_name}")
            
            # Call cleanup hook if exists
            if hasattr(previous_adapter, 'close'):
                try:
                    previous_adapter.close()
                    logger.debug(f"Called {previous_name}.close()")
                except Exception as e:
                    logger.warning(f"Cleanup failed for {previous_name}: {e}")
            
            # Track switch history
            if not hasattr(self, '_switch_history'):
                self._switch_history = []
            self._switch_history.append({
                'type': adapter_type,
                'from': previous_name,
                'to': adapter_name,
                'timestamp': __import__('datetime').datetime.now().isoformat()
            })
        
        # Load new adapter
        adapter_class = self._registry[adapter_type][adapter_name]
        
        # Check if already instantiated (singleton pattern)
        if adapter_name in self._instances[adapter_type]:
            instance = self._instances[adapter_type][adapter_name]
            logger.debug(f"Reusing cached instance of {adapter_type}.{adapter_name}")
        else:
            # Get config for this adapter
            config = self.get_adapter_config(adapter_type, adapter_name)
            
            # Instantiate
            try:
                instance = adapter_class(config=config)
                self._instances[adapter_type][adapter_name] = instance
                logger.info(f"Instantiated {adapter_type}.{adapter_name}")
            except Exception as e:
                raise PluginLoadError(
                    f"Failed to instantiate {adapter_type}.{adapter_name}: {e}"
                ) from e
        
        self._active[adapter_type] = instance
        logger.info(f"Switched {adapter_type} to {adapter_name}")
    
    def _find_instance_name(self, adapter_type: str, instance: Any) -> Optional[str]:
        """
        Find the name of an adapter instance
        
        Args:
            adapter_type: Type of adapter
            instance: Adapter instance
        
        Returns:
            Name of adapter or None
        """
        for name, inst in self._instances[adapter_type].items():
            if inst is instance:
                return name
        return None
    
    def get_switch_history(self, adapter_type: Optional[str] = None) -> list:
        """
        Get switch history for debugging
        
        Args:
            adapter_type: Optional filter by type
        
        Returns:
            List of switch events with timestamps
        
        Example:
            >>> history = manager.get_switch_history('ocr')
            >>> print(history[-1])  # Last switch
            {'type': 'ocr', 'from': 'mock', 'to': 'tesseract', 'timestamp': '...'}
        """
        if not hasattr(self, '_switch_history'):
            return []
        
        history = self._switch_history
        if adapter_type:
            history = [h for h in history if h['type'] == adapter_type]
        
        return history
    
    def get_active(self, adapter_type: str) -> Optional[Any]:
        """
        Récupérer l'adapter actif d'un type
        
        Args:
            adapter_type: Type d'adapter
        
        Returns:
            Instance de l'adapter actif ou None
        
        Example:
            >>> ocr = manager.get_active('ocr')
            >>> result = ocr.extract('/path/to/image.jpg')
        """
        return self._active.get(adapter_type)
    
    def list_available(self, adapter_type: str) -> List[str]:
        """
        List available (registered) adapters for a type
        
        Args:
            adapter_type: Type of adapter ('ocr', 'translator', 'search')
        
        Returns:
            List of adapter names
        
        Example:
            >>> manager.list_available('ocr')
            ['mock', 'tesseract', 'chandra']
        """
        if adapter_type not in self._registry:
            return []
        return list(self._registry[adapter_type].keys())
    
    def list_active(self) -> Dict[str, Optional[str]]:
        """
        Lister les adapters actifs
        
        Returns:
            Dictionnaire {type: name} des adapters actifs
        
        Example:
            >>> print(manager.list_active())
            {'ocr': 'tesseract', 'translator': 'mock', 'search': None}
        """
        active = {}
        for adapter_type, instance in self._active.items():
            if instance:
                # Find adapter name from instance
                name = None
                for n, inst in self._instances[adapter_type].items():
                    if inst is instance:
                        name = n
                        break
                active[adapter_type] = name
            else:
                active[adapter_type] = None
        return active
    
    def discover_plugins(
        self, 
        base_path: Optional[Path] = None,
        adapter_types: Optional[List[str]] = None
    ) -> List[PluginMetadata]:
        """
        Auto-discover plugins by scanning adapter directories
        
        Args:
            base_path: Root path to scan (default: src/indexao/adapters)
            adapter_types: Limit to specific types (default: all)
        
        Returns:
            List of discovered plugin metadata
        
        Example:
            >>> plugins = manager.discover_plugins()
            >>> for plugin in plugins:
            ...     print(f"{plugin.type}/{plugin.name}: {plugin.description}")
        """
        if base_path is None:
            # Default: src/indexao/adapters/
            base_path = Path(__file__).parent / "adapters"
        
        if adapter_types is None:
            adapter_types = ['ocr', 'translator', 'search']
        
        discovered = []
        
        for adapter_type in adapter_types:
            type_path = base_path / adapter_type
            if not type_path.exists():
                logger.warning(f"Adapter type path not found: {type_path}")
                continue
            
            # Scan all .py files in this adapter type directory
            for py_file in type_path.glob("*.py"):
                if py_file.name.startswith("_") or py_file.name == "base.py":
                    continue
                
                try:
                    metadata = self._extract_plugin_metadata(py_file, adapter_type)
                    if metadata:
                        discovered.append(metadata)
                        logger.debug(f"Discovered plugin: {adapter_type}/{metadata.name}")
                except Exception as e:
                    logger.warning(f"Failed to parse {py_file}: {e}")
        
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
    
    def _extract_plugin_metadata(self, file_path: Path, adapter_type: str) -> Optional[PluginMetadata]:
        """
        Extract plugin metadata from a Python file
        
        Strategy:
        1. Parse AST to find adapter classes
        2. Look for __plugin__ dict or docstring metadata
        3. Extract class name as plugin name
        
        Args:
            file_path: Path to .py file
            adapter_type: Type of adapter
        
        Returns:
            PluginMetadata if found, None otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None
        
        # Find classes that look like adapters
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class name ends with "Adapter"
                if not node.name.endswith("Adapter"):
                    continue
                
                # Extract metadata
                plugin_dict = None
                description = ast.get_docstring(node) or ""
                
                # Look for __plugin__ class variable
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == "__plugin__":
                                # Found __plugin__ dict
                                try:
                                    plugin_dict = ast.literal_eval(item.value)
                                except:
                                    pass
                
                # Build metadata
                if plugin_dict:
                    # Use explicit metadata
                    name = plugin_dict.get('name', self._class_name_to_plugin_name(node.name))
                    version = plugin_dict.get('version', '0.1.0')
                    deps = plugin_dict.get('dependencies', [])
                    enabled = plugin_dict.get('enabled', True)
                    priority = plugin_dict.get('priority', 0)
                    desc = plugin_dict.get('description', description.split('\n')[0] if description else "")
                else:
                    # Infer from class name and docstring
                    name = self._class_name_to_plugin_name(node.name)
                    version = '0.1.0'
                    deps = []
                    enabled = True
                    priority = 0
                    desc = description.split('\n')[0] if description else ""
                
                return PluginMetadata(
                    name=name,
                    type=adapter_type,
                    version=version,
                    description=desc,
                    dependencies=deps,
                    enabled=enabled,
                    priority=priority
                )
        
        return None
    
    def _class_name_to_plugin_name(self, class_name: str) -> str:
        """
        Convert class name to plugin name
        
        Examples:
            MockOCRAdapter -> mock-ocr
            TesseractAdapter -> tesseract
            ChandraOCR -> chandra
        
        Args:
            class_name: Python class name
        
        Returns:
            Plugin name (lowercase, hyphenated)
        """
        # Remove common suffixes
        for suffix in ['Adapter', 'OCR', 'Translator', 'Search', 'Backend', 'Engine']:
            if class_name.endswith(suffix):
                class_name = class_name[:-len(suffix)]
        
        # Convert CamelCase to kebab-case
        result = []
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0 and class_name[i-1].islower():
                result.append('-')
            result.append(char.lower())
        
        return ''.join(result)
    
    def load_adapter(
        self,
        adapter_type: str,
        adapter_name: str,
        auto_register: bool = True,
        fallback_to_mock: bool = True
    ) -> Optional[Any]:
        """
        Dynamically load adapter from module using importlib
        
        Strategy:
        1. Determine module path from adapter_type and adapter_name
        2. Import module with importlib.import_module()
        3. Find adapter class in module (introspection)
        4. Instantiate with config from TOML
        5. Register and activate
        6. Fallback to mock on failure if enabled
        
        Args:
            adapter_type: Type ('ocr', 'translator', 'search')
            adapter_name: Name of adapter (e.g., 'tesseract', 'mock')
            auto_register: Automatically register after loading
            fallback_to_mock: Load mock adapter on failure
        
        Returns:
            Adapter instance or None
        
        Raises:
            PluginLoadError: If loading fails and fallback disabled
        
        Example:
            >>> manager.load_adapter('ocr', 'tesseract')
            >>> adapter = manager.get_active('ocr')
        """
        if adapter_type not in ['ocr', 'translator', 'search']:
            raise ValueError(f"Invalid adapter_type: {adapter_type}")
        
        # Build module path: indexao.adapters.ocr.tesseract
        module_name = f"indexao.adapters.{adapter_type}.{adapter_name}"
        
        try:
            # Import module dynamically
            logger.debug(f"Importing module: {module_name}")
            module = importlib.import_module(module_name)
            
            # Find adapter class in module
            adapter_class = self._find_adapter_class(module, adapter_type)
            if not adapter_class:
                raise PluginLoadError(f"No adapter class found in {module_name}")
            
            logger.debug(f"Found adapter class: {adapter_class.__name__}")
            
            # Get config for this adapter
            config = self.get_adapter_config(adapter_type, adapter_name)
            
            # Instantiate adapter with config
            try:
                if config:
                    adapter_instance = adapter_class(**config)
                else:
                    adapter_instance = adapter_class()
            except Exception as e:
                raise PluginLoadError(f"Failed to instantiate {adapter_class.__name__}: {e}")
            
            logger.info(f"Loaded adapter: {adapter_type}/{adapter_name}")
            
            # Auto-register if requested
            if auto_register:
                self.register(adapter_type, adapter_name, adapter_class, validate=True)
                self._instances[adapter_type][adapter_name] = adapter_instance
                self._active[adapter_type] = adapter_instance
                logger.info(f"Registered and activated: {adapter_type}/{adapter_name}")
            
            return adapter_instance
            
        except (ImportError, ModuleNotFoundError) as e:
            error_msg = f"Failed to import {module_name}: {e}"
            logger.error(error_msg)
            
            # Fallback to mock if enabled
            if fallback_to_mock and adapter_name != 'mock':
                logger.warning(f"Falling back to mock adapter for {adapter_type}")
                return self.load_adapter(adapter_type, 'mock', auto_register=auto_register, fallback_to_mock=False)
            
            raise PluginLoadError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to load {adapter_type}/{adapter_name}: {e}"
            logger.error(error_msg)
            
            if fallback_to_mock and adapter_name != 'mock':
                logger.warning(f"Falling back to mock adapter for {adapter_type}")
                return self.load_adapter(adapter_type, 'mock', auto_register=auto_register, fallback_to_mock=False)
            
            raise PluginLoadError(error_msg)
    
    def _find_adapter_class(self, module: Any, adapter_type: str) -> Optional[Type]:
        """
        Find adapter class in imported module using introspection
        
        Strategy:
        1. Look for class with name ending in "Adapter"
        2. Check if class has required protocol methods
        3. Prefer classes with exact type match (e.g., OCRAdapter)
        
        Args:
            module: Imported Python module
            adapter_type: Type of adapter
        
        Returns:
            Adapter class or None
        """
        candidates = []
        
        # Get all classes from module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Skip imported classes (must be defined in this module)
            if obj.__module__ != module.__name__:
                continue
            
            # Must end with "Adapter" or be exact type match
            if name.endswith('Adapter') or name.endswith('OCR') or name.endswith('Translator'):
                candidates.append(obj)
        
        if not candidates:
            return None
        
        # Prefer class with protocol methods
        protocol = self._get_protocol_for_type(adapter_type)
        if protocol and PROTOCOLS_AVAILABLE:
            for candidate in candidates:
                # Check if has required methods (basic check)
                if adapter_type == 'ocr' and hasattr(candidate, 'process_image'):
                    return candidate
                elif adapter_type == 'translator' and hasattr(candidate, 'translate'):
                    return candidate
                elif adapter_type == 'search' and hasattr(candidate, 'index_document'):
                    return candidate
        
        # Return first candidate
        return candidates[0] if candidates else None


