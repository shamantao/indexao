"""Mock OCR adapter for testing."""

from pathlib import Path
from typing import List, Optional
import time

from indexao.adapters.ocr.base import OCRAdapter, OCRResult
from indexao.logger import get_logger

logger = get_logger(__name__)


class MockOCRAdapter:
    """
    Mock OCR adapter that returns predefined text.
    
    Useful for testing without requiring actual OCR engine installation.
    """
    
    def __init__(self, mock_text: str = "Mock OCR result", confidence: float = 0.95):
        """
        Initialize mock OCR adapter.
        
        Args:
            mock_text: Text to return for all OCR requests
            confidence: Confidence score to return
        """
        self.mock_text = mock_text
        self.mock_confidence = confidence
        logger.debug(f"Initialized MockOCRAdapter with mock_text: '{mock_text[:50]}...'")
    
    @property
    def name(self) -> str:
        """Engine name."""
        return "mock-ocr"
    
    @property
    def supported_languages(self) -> List[str]:
        """Supported languages."""
        return ["en", "fr", "zh-TW", "es", "de", "ja"]
    
    def process_image(
        self,
        image_path: Path,
        language: Optional[str] = None,
        **kwargs
    ) -> OCRResult:
        """
        Process image (returns mock text).
        
        Args:
            image_path: Path to image (checked for existence)
            language: Language hint
            **kwargs: Ignored
        
        Returns:
            OCRResult with mock text
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        logger.debug(f"Mock processing image: {image_path.name}")
        
        # Simulate processing time
        start_time = time.time()
        time.sleep(0.01)  # 10ms
        processing_time = (time.time() - start_time) * 1000
        
        return OCRResult(
            text=self.mock_text,
            language=language or "en",
            confidence=self.mock_confidence,
            processing_time_ms=processing_time,
            metadata={
                "engine": "mock-ocr",
                "image_path": str(image_path),
                "mock": True
            }
        )
    
    def process_batch(
        self,
        image_paths: List[Path],
        language: Optional[str] = None,
        **kwargs
    ) -> List[OCRResult]:
        """Process multiple images."""
        return [self.process_image(path, language, **kwargs) for path in image_paths]
    
    def is_available(self) -> bool:
        """Always available."""
        return True
    
    def get_version(self) -> str:
        """Mock version."""
        return "1.0.0-mock"
