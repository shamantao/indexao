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
    
    # Auto-discovery (future)
    plugins = manager.discover_plugins()
    manager.load_adapter('ocr', 'chandra')
"""

import logging
import inspect
from pathlib import Path
from typing import Dict, Any, Optional, Type, Protocol, get_type_hints, get_args
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
