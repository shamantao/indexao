"""Unit tests for adapter interfaces and mock implementations."""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile

from indexao.adapters.ocr import OCRAdapter, OCRResult, MockOCRAdapter
from indexao.adapters.translator import TranslatorAdapter, TranslationResult, MockTranslatorAdapter
from indexao.adapters.search import SearchAdapter, SearchResult, IndexedDocument, MockSearchAdapter


class TestOCRAdapter:
    """Tests for OCR adapter interface."""
    
    def test_ocr_result_dataclass(self):
        """Test OCRResult dataclass validation."""
        result = OCRResult(
            text="Hello world",
            language="en",
            confidence=0.95,
            processing_time_ms=123.45,
            metadata={"engine": "test"}
        )
        assert result.text == "Hello world"
        assert result.confidence == 0.95
        assert 0.0 <= result.confidence <= 1.0
    
    def test_ocr_result_invalid_confidence(self):
        """Test OCRResult rejects invalid confidence."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            OCRResult(
                text="test",
                language="en",
                confidence=1.5,  # Invalid
                processing_time_ms=100,
                metadata={}
            )
    
    def test_mock_ocr_protocol_compliance(self):
        """Test MockOCRAdapter implements OCRAdapter protocol."""
        mock = MockOCRAdapter()
        assert isinstance(mock, OCRAdapter)
        assert mock.name == "mock-ocr"
        assert len(mock.supported_languages) > 0
        assert mock.is_available()
        assert "mock" in mock.get_version()
    
    def test_mock_ocr_process_image(self, tmp_path):
        """Test mock OCR processes image."""
        # Create dummy image
        image = tmp_path / "test.png"
        image.write_text("dummy")
        
        mock = MockOCRAdapter(mock_text="Test OCR", confidence=0.9)
        result = mock.process_image(image, language="en")
        
        assert result.text == "Test OCR"
        assert result.language == "en"
        assert result.confidence == 0.9
        assert result.processing_time_ms > 0
        assert result.metadata["engine"] == "mock-ocr"
    
    def test_mock_ocr_image_not_found(self):
        """Test mock OCR raises error for missing image."""
        mock = MockOCRAdapter()
        with pytest.raises(FileNotFoundError):
            mock.process_image(Path("/nonexistent/image.png"))
    
    def test_mock_ocr_batch(self, tmp_path):
        """Test mock OCR batch processing."""
        images = [tmp_path / f"img{i}.png" for i in range(3)]
        for img in images:
            img.write_text("dummy")
        
        mock = MockOCRAdapter()
        results = mock.process_batch(images, language="fr")
        
        assert len(results) == 3
        assert all(r.language == "fr" for r in results)
        assert all(r.confidence > 0 for r in results)


class TestTranslatorAdapter:
    """Tests for translator adapter interface."""
    
    def test_translation_result_dataclass(self):
        """Test TranslationResult dataclass validation."""
        result = TranslationResult(
            translated_text="Bonjour",
            source_language="en",
            target_language="fr",
            confidence=0.98,
            processing_time_ms=50.0,
            metadata={"engine": "test"}
        )
        assert result.translated_text == "Bonjour"
        assert result.confidence == 0.98
    
    def test_translation_result_invalid_confidence(self):
        """Test TranslationResult rejects invalid confidence."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            TranslationResult(
                translated_text="test",
                source_language="en",
                target_language="fr",
                confidence=-0.1,  # Invalid
                processing_time_ms=50,
                metadata={}
            )
    
    def test_mock_translator_protocol_compliance(self):
        """Test MockTranslatorAdapter implements TranslatorAdapter protocol."""
        mock = MockTranslatorAdapter()
        assert isinstance(mock, TranslatorAdapter)
        assert mock.name == "mock-translator"
        assert len(mock.supported_languages) > 0
        assert mock.is_available()
        assert "mock" in mock.get_version()
    
    def test_mock_translator_translate(self):
        """Test mock translator translates text."""
        mock = MockTranslatorAdapter(reverse_text=True)
        result = mock.translate("Hello", target_language="fr", source_language="en")
        
        assert result.translated_text == "olleH"  # Reversed
        assert result.source_language == "en"
        assert result.target_language == "fr"
        assert result.confidence == 0.95
        assert result.processing_time_ms > 0
    
    def test_mock_translator_no_reverse(self):
        """Test mock translator without reversing."""
        mock = MockTranslatorAdapter(reverse_text=False)
        result = mock.translate("Hello", target_language="fr")
        
        assert result.translated_text == "Hello"  # Not reversed
    
    def test_mock_translator_unsupported_language(self):
        """Test mock translator rejects unsupported language."""
        mock = MockTranslatorAdapter()
        with pytest.raises(ValueError, match="Unsupported target language"):
            mock.translate("test", target_language="invalid_lang")
    
    def test_mock_translator_batch(self):
        """Test mock translator batch translation."""
        mock = MockTranslatorAdapter(reverse_text=True)
        texts = ["Hello", "World", "Test"]
        results = mock.translate_batch(texts, target_language="fr")
        
        assert len(results) == 3
        assert results[0].translated_text == "olleH"
        assert results[1].translated_text == "dlroW"
        assert all(r.target_language == "fr" for r in results)
    
    def test_mock_translator_detect_language(self):
        """Test mock translator language detection."""
        mock = MockTranslatorAdapter()
        lang = mock.detect_language("Hello world")
        assert lang == "en"  # Mock always returns 'en'


class TestSearchAdapter:
    """Tests for search adapter interface."""
    
    def test_indexed_document_dataclass(self):
        """Test IndexedDocument dataclass."""
        doc = IndexedDocument(
            doc_id="doc1",
            title="Test Doc",
            content="Test content",
            language="en",
            file_path=Path("/path/to/file.txt"),
            metadata={"author": "test"},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert doc.doc_id == "doc1"
        assert doc.title == "Test Doc"
        assert doc.language == "en"
    
    def test_search_result_dataclass(self):
        """Test SearchResult dataclass validation."""
        result = SearchResult(
            doc_id="doc1",
            title="Test",
            content_snippet="Test snippet",
            score=0.85,
            language="en",
            metadata={},
            highlights=["test"]
        )
        assert result.score == 0.85
        assert 0.0 <= result.score <= 1.0
    
    def test_search_result_invalid_score(self):
        """Test SearchResult rejects invalid score."""
        with pytest.raises(ValueError, match="Score must be between 0.0 and 1.0"):
            SearchResult(
                doc_id="doc1",
                title="Test",
                content_snippet="snippet",
                score=1.2,  # Invalid
                language="en"
            )
    
    def test_mock_search_protocol_compliance(self):
        """Test MockSearchAdapter implements SearchAdapter protocol."""
        mock = MockSearchAdapter()
        assert isinstance(mock, SearchAdapter)
        assert mock.name == "mock-search"
        assert mock.is_available()
        assert "mock" in mock.get_version()
    
    def test_mock_search_index_document(self):
        """Test mock search indexes document."""
        mock = MockSearchAdapter()
        doc = IndexedDocument(
            doc_id="doc1",
            title="Test Document",
            content="This is test content",
            language="en",
            file_path=Path("/test.txt"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        assert mock.index_document(doc)
        assert mock.count_documents() == 1
    
    def test_mock_search_index_batch(self):
        """Test mock search batch indexing."""
        mock = MockSearchAdapter()
        docs = [
            IndexedDocument(
                doc_id=f"doc{i}",
                title=f"Doc {i}",
                content=f"Content {i}",
                language="en",
                file_path=Path(f"/doc{i}.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            for i in range(5)
        ]
        
        count = mock.index_batch(docs)
        assert count == 5
        assert mock.count_documents() == 5
    
    def test_mock_search_search(self):
        """Test mock search query."""
        mock = MockSearchAdapter()
        
        # Index documents
        docs = [
            IndexedDocument(
                doc_id="doc1",
                title="Python Guide",
                content="Learn Python programming",
                language="en",
                file_path=Path("/python.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            IndexedDocument(
                doc_id="doc2",
                title="JavaScript Tutorial",
                content="Learn JavaScript basics",
                language="en",
                file_path=Path("/js.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        mock.index_batch(docs)
        
        # Search
        results = mock.search("Python")
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
        assert results[0].score > 0
    
    def test_mock_search_language_filter(self):
        """Test mock search language filtering."""
        mock = MockSearchAdapter()
        
        # Index multilingual documents
        docs = [
            IndexedDocument(
                doc_id="en_doc",
                title="English",
                content="English content",
                language="en",
                file_path=Path("/en.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            IndexedDocument(
                doc_id="fr_doc",
                title="French",
                content="French content",
                language="fr",
                file_path=Path("/fr.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        mock.index_batch(docs)
        
        # Filter by language
        results = mock.search("content", language="fr")
        assert len(results) == 1
        assert results[0].language == "fr"
    
    def test_mock_search_pagination(self):
        """Test mock search pagination."""
        mock = MockSearchAdapter()
        
        # Index many documents
        docs = [
            IndexedDocument(
                doc_id=f"doc{i}",
                title=f"Document {i}",
                content="test content",
                language="en",
                file_path=Path(f"/doc{i}.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            for i in range(20)
        ]
        mock.index_batch(docs)
        
        # Test pagination
        page1 = mock.search("content", limit=5, offset=0)
        page2 = mock.search("content", limit=5, offset=5)
        
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].doc_id != page2[0].doc_id
    
    def test_mock_search_get_document(self):
        """Test mock search get document."""
        mock = MockSearchAdapter()
        doc = IndexedDocument(
            doc_id="doc1",
            title="Test",
            content="Content",
            language="en",
            file_path=Path("/test.txt"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock.index_document(doc)
        
        retrieved = mock.get_document("doc1")
        assert retrieved is not None
        assert retrieved.doc_id == "doc1"
        assert mock.get_document("nonexistent") is None
    
    def test_mock_search_update_document(self):
        """Test mock search update document."""
        mock = MockSearchAdapter()
        doc = IndexedDocument(
            doc_id="doc1",
            title="Original",
            content="Content",
            language="en",
            file_path=Path("/test.txt"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock.index_document(doc)
        
        assert mock.update_document("doc1", {"title": "Updated"})
        updated = mock.get_document("doc1")
        assert updated is not None
        assert updated.title == "Updated"
    
    def test_mock_search_delete_document(self):
        """Test mock search delete document."""
        mock = MockSearchAdapter()
        doc = IndexedDocument(
            doc_id="doc1",
            title="Test",
            content="Content",
            language="en",
            file_path=Path("/test.txt"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock.index_document(doc)
        
        assert mock.count_documents() == 1
        assert mock.delete_document("doc1")
        assert mock.count_documents() == 0
        assert not mock.delete_document("nonexistent")
    
    def test_mock_search_clear_index(self):
        """Test mock search clear index."""
        mock = MockSearchAdapter()
        docs = [
            IndexedDocument(
                doc_id=f"doc{i}",
                title=f"Doc {i}",
                content="content",
                language="en",
                file_path=Path(f"/doc{i}.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            for i in range(10)
        ]
        mock.index_batch(docs)
        
        assert mock.count_documents() == 10
        assert mock.clear_index()
        assert mock.count_documents() == 0
    
    def test_mock_search_count_by_language(self):
        """Test mock search count by language."""
        mock = MockSearchAdapter()
        docs = [
            IndexedDocument(
                doc_id=f"en{i}",
                title=f"EN {i}",
                content="content",
                language="en",
                file_path=Path(f"/en{i}.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            for i in range(3)
        ] + [
            IndexedDocument(
                doc_id=f"fr{i}",
                title=f"FR {i}",
                content="content",
                language="fr",
                file_path=Path(f"/fr{i}.txt"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            for i in range(2)
        ]
        mock.index_batch(docs)
        
        assert mock.count_documents() == 5
        assert mock.count_documents(language="en") == 3
        assert mock.count_documents(language="fr") == 2
