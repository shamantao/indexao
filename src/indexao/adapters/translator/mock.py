"""Mock translator adapter for testing."""

from typing import List, Optional
import time

from indexao.adapters.translator.base import TranslatorAdapter, TranslationResult
from indexao.logger import get_logger

logger = get_logger(__name__)


class MockTranslatorAdapter:
    """
    Mock translator that returns reversed text.
    
    Useful for testing without requiring actual translation engine.
    """
    
    def __init__(self, reverse_text: bool = True):
        """
        Initialize mock translator.
        
        Args:
            reverse_text: If True, returns reversed text. If False, returns original.
        """
        self.reverse_text = reverse_text
        logger.debug(f"Initialized MockTranslatorAdapter (reverse={reverse_text})")
    
    @property
    def name(self) -> str:
        """Engine name."""
        return "mock-translator"
    
    @property
    def supported_languages(self) -> List[str]:
        """Supported languages."""
        return ["en", "fr", "zh", "es", "de", "ja", "ar", "ru"]
    
    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        **kwargs
    ) -> TranslationResult:
        """
        Translate text (returns reversed or original text).
        
        Args:
            text: Text to translate
            target_language: Target language
            source_language: Source language
            **kwargs: Ignored
        
        Returns:
            TranslationResult with mock translation
        """
        if target_language not in self.supported_languages:
            raise ValueError(f"Unsupported target language: {target_language}")
        
        logger.debug(f"Mock translating: '{text[:50]}...' to {target_language}")
        
        # Simulate processing time
        start_time = time.time()
        time.sleep(0.01)  # 10ms
        processing_time = (time.time() - start_time) * 1000
        
        # Mock translation: reverse text or return as-is
        translated = text[::-1] if self.reverse_text else text
        
        return TranslationResult(
            translated_text=translated,
            source_language=source_language or "en",
            target_language=target_language,
            confidence=0.95,
            processing_time_ms=processing_time,
            metadata={
                "engine": "mock-translator",
                "reversed": self.reverse_text,
                "mock": True
            }
        )
    
    def translate_batch(
        self,
        texts: List[str],
        target_language: str,
        source_language: Optional[str] = None,
        **kwargs
    ) -> List[TranslationResult]:
        """Translate multiple texts."""
        return [self.translate(text, target_language, source_language, **kwargs) for text in texts]
    
    def detect_language(self, text: str) -> str:
        """Detect language (always returns 'en')."""
        logger.trace(f"Mock detecting language for: '{text[:50]}...'")
        return "en"
    
    def is_available(self) -> bool:
        """Always available."""
        return True
    
    def get_version(self) -> str:
        """Mock version."""
        return "1.0.0-mock"
