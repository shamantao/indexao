"""
Base adapter interfaces for Indexao.

This module defines the core protocols that all plugin adapters must implement.
Adapters provide a uniform interface for swappable components:
- OCR engines (Tesseract, Chandra-OCR, Google Vision, etc.)
- Translation engines (Argostranslate, Google Translate, DeepL, etc.)
- Search backends (Meilisearch, Tantivy, SQLite FTS, etc.)
- Export formats (JSON, Markdown, HTML, etc.)
"""

from indexao.adapters.ocr.base import OCRAdapter, OCRResult
from indexao.adapters.translator.base import TranslatorAdapter, TranslationResult
from indexao.adapters.search.base import SearchAdapter, SearchResult, IndexedDocument

__all__ = [
    'OCRAdapter',
    'OCRResult',
    'TranslatorAdapter',
    'TranslationResult',
    'SearchAdapter',
    'SearchResult',
    'IndexedDocument',
]
