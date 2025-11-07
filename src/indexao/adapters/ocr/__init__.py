"""OCR adapter module."""

from indexao.adapters.ocr.base import OCRAdapter, OCRResult
from indexao.adapters.ocr.mock import MockOCRAdapter
from indexao.adapters.ocr.tesseract import TesseractOCR

__all__ = ['OCRAdapter', 'OCRResult', 'MockOCRAdapter', 'TesseractOCR']
