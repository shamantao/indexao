"""
Translation adapter interface.

Defines the protocol for translation engines to translate text between languages.
"""

from dataclasses import dataclass
from typing import Protocol, List, Optional, Dict, Any, runtime_checkable


@dataclass
class TranslationResult:
    """
    Result from translation.
    
    Attributes:
        translated_text: Translated text
        source_language: Detected/specified source language code
        target_language: Target language code
        confidence: Confidence score (0.0-1.0)
        processing_time_ms: Time taken to translate (milliseconds)
        metadata: Additional engine-specific metadata
    """
    translated_text: str
    source_language: str
    target_language: str
    confidence: float
    processing_time_ms: float
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate confidence range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
    
    def __repr__(self) -> str:
        """String representation."""
        text_preview = self.translated_text[:50] + "..." if len(self.translated_text) > 50 else self.translated_text
        return (
            f"TranslationResult({self.source_language}→{self.target_language}, "
            f"confidence={self.confidence:.2f}, "
            f"text='{text_preview}')"
        )


@runtime_checkable
class TranslatorAdapter(Protocol):
    """
    Protocol for translation adapters.
    
    All translation engines must implement this interface.
    """
    
    @property
    def name(self) -> str:
        """
        Name of the translation engine.
        
        Returns:
            Engine name (e.g., 'argostranslate', 'google-translate', 'deepl')
        """
        ...
    
    @property
    def supported_languages(self) -> List[str]:
        """
        List of supported language codes.
        
        Returns:
            List of ISO 639-1 language codes (e.g., ['en', 'fr', 'zh'])
        """
        ...
    
    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        **kwargs
    ) -> TranslationResult:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language (None = auto-detect)
            **kwargs: Engine-specific options
        
        Returns:
            TranslationResult with translated text
        
        Raises:
            ValueError: If language not supported
            RuntimeError: If translation fails
        
        Example:
            >>> adapter = ArgosTranslateAdapter()
            >>> result = adapter.translate("Hello world", "fr")
            >>> print(result.translated_text)  # "Bonjour le monde"
        """
        ...
    
    def translate_batch(
        self,
        texts: List[str],
        target_language: str,
        source_language: Optional[str] = None,
        **kwargs
    ) -> List[TranslationResult]:
        """
        Translate multiple texts (batch processing).
        
        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language (None = auto-detect)
            **kwargs: Engine-specific options
        
        Returns:
            List of TranslationResult objects (same order as input)
        
        Note:
            Default implementation processes texts sequentially.
            Subclasses may override for parallel processing.
        """
        ...
    
    def detect_language(self, text: str) -> str:
        """
        Detect language of text.
        
        Args:
            text: Text to analyze
        
        Returns:
            Detected language code (e.g., 'en', 'fr', 'zh')
        
        Example:
            >>> adapter = ArgosTranslateAdapter()
            >>> lang = adapter.detect_language("Bonjour")
            >>> print(lang)  # "fr"
        """
        ...
    
    def is_available(self) -> bool:
        """
        Check if translation engine is available.
        
        Returns:
            True if engine is ready to use, False otherwise
        """
        ...
    
    def get_version(self) -> str:
        """
        Get translation engine version.
        
        Returns:
            Version string
        """
        ...
