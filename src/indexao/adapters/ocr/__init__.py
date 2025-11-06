"""OCR adapter module."""

from indexao.adapters.ocr.base import OCRAdapter, OCRResult
from indexao.adapters.ocr.mock import MockOCRAdapter

__all__ = ['OCRAdapter', 'OCRResult', 'MockOCRAdapter']
