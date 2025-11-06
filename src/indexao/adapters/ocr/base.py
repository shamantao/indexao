"""
OCR (Optical Character Recognition) adapter interface.

Defines the protocol for OCR engines to extract text from images.
"""

from dataclasses import dataclass
from typing import Protocol, List, Optional, Dict, Any, runtime_checkable
from pathlib import Path
from datetime import datetime


@dataclass
class OCRResult:
    """
    Result from OCR processing.
    
    Attributes:
        text: Extracted text content
        language: Detected language code (e.g., 'en', 'fr', 'zh-TW')
        confidence: Confidence score (0.0-1.0)
        processing_time_ms: Time taken to process (milliseconds)
        metadata: Additional engine-specific metadata
        words: Optional list of word-level results with bounding boxes
    """
    text: str
    language: str
    confidence: float
    processing_time_ms: float
    metadata: Dict[str, Any]
    words: Optional[List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        """Validate confidence range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
    
    def __repr__(self) -> str:
        """String representation."""
        text_preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return (
            f"OCRResult(lang={self.language}, "
            f"confidence={self.confidence:.2f}, "
            f"text='{text_preview}')"
        )


@runtime_checkable
class OCRAdapter(Protocol):
    """
    Protocol for OCR adapters.
    
    All OCR engines must implement this interface to be used in Indexao.
    """
    
    @property
    def name(self) -> str:
        """
        Name of the OCR engine.
        
        Returns:
            Engine name (e.g., 'tesseract', 'chandra-ocr', 'google-vision')
        """
        ...
    
    @property
    def supported_languages(self) -> List[str]:
        """
        List of supported language codes.
        
        Returns:
            List of ISO 639-1/639-3 language codes (e.g., ['en', 'fr', 'zh-TW'])
        """
        ...
    
    def process_image(
        self,
        image_path: Path,
        language: Optional[str] = None,
        **kwargs
    ) -> OCRResult:
        """
        Extract text from image.
        
        Args:
            image_path: Path to image file
            language: Language hint (None = auto-detect)
            **kwargs: Engine-specific options
        
        Returns:
            OCRResult with extracted text and metadata
        
        Raises:
            FileNotFoundError: If image file doesn't exist
            ValueError: If language is not supported
            RuntimeError: If OCR processing fails
        
        Example:
            >>> adapter = TesseractAdapter()
            >>> result = adapter.process_image(Path("document.png"), language="fr")
            >>> print(result.text)
        """
        ...
    
    def process_batch(
        self,
        image_paths: List[Path],
        language: Optional[str] = None,
        **kwargs
    ) -> List[OCRResult]:
        """
        Extract text from multiple images (batch processing).
        
        Args:
            image_paths: List of image file paths
            language: Language hint (None = auto-detect)
            **kwargs: Engine-specific options
        
        Returns:
            List of OCRResult objects (same order as input)
        
        Raises:
            FileNotFoundError: If any image file doesn't exist
            ValueError: If language is not supported
        
        Note:
            Default implementation processes images sequentially.
            Subclasses may override for parallel processing.
        """
        ...
    
    def is_available(self) -> bool:
        """
        Check if OCR engine is available and properly configured.
        
        Returns:
            True if engine is ready to use, False otherwise
        
        Example:
            >>> adapter = TesseractAdapter()
            >>> if adapter.is_available():
            ...     result = adapter.process_image(image_path)
            ... else:
            ...     print("Tesseract not installed")
        """
        ...
    
    def get_version(self) -> str:
        """
        Get OCR engine version.
        
        Returns:
            Version string (e.g., "5.3.0")
        """
        ...
