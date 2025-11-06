"""
Demonstration of adapter interfaces.

Shows OCR, translation, and search adapters in action using mock implementations.
"""

import sys
from pathlib import Path
from datetime import datetime
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from indexao.logger import get_logger, LoggerManager
from indexao.adapters.ocr import MockOCRAdapter
from indexao.adapters.translator import MockTranslatorAdapter
from indexao.adapters.search import MockSearchAdapter, IndexedDocument

# Setup logger
import os
os.environ['INDEXAO_LOG_LEVEL'] = 'DEBUG'
logger = get_logger(__name__)


def demo_ocr_adapter():
    """Demonstrate OCR adapter."""
    logger.info("=" * 60)
    logger.info("DEMO 1: OCR Adapter")
    logger.info("=" * 60)
    
    # Create mock OCR adapter
    ocr = MockOCRAdapter(mock_text="This is extracted text from image", confidence=0.95)
    
    logger.info(f"Engine: {ocr.name}")
    logger.info(f"Version: {ocr.get_version()}")
    logger.info(f"Supported languages: {', '.join(ocr.supported_languages[:5])}...")
    logger.info(f"Available: {ocr.is_available()}")
    
    # Create temporary image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(b"dummy image data")
    
    try:
        # Process single image
        logger.info(f"\nProcessing image: {tmp_path.name}")
        result = ocr.process_image(tmp_path, language="en")
        
        logger.info(f"Text: {result.text}")
        logger.info(f"Language: {result.language}")
        logger.info(f"Confidence: {result.confidence:.2%}")
        logger.info(f"Processing time: {result.processing_time_ms:.2f}ms")
        logger.info(f"Metadata: {result.metadata}")
        
        # Process batch
        logger.info("\nProcessing batch of 3 images...")
        batch_results = ocr.process_batch([tmp_path] * 3, language="fr")
        logger.info(f"Processed {len(batch_results)} images")
        for i, r in enumerate(batch_results, 1):
            logger.info(f"  Image {i}: {r.confidence:.2%} confidence, {r.processing_time_ms:.2f}ms")
    
    finally:
        tmp_path.unlink()


def demo_translator_adapter():
    """Demonstrate translator adapter."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO 2: Translator Adapter")
    logger.info("=" * 60)
    
    # Create mock translator (reverses text)
    translator = MockTranslatorAdapter(reverse_text=True)
    
    logger.info(f"Engine: {translator.name}")
    logger.info(f"Version: {translator.get_version()}")
    logger.info(f"Supported languages: {', '.join(translator.supported_languages[:5])}...")
    logger.info(f"Available: {translator.is_available()}")
    
    # Translate single text
    text = "Hello, this is a test translation"
    logger.info(f"\nTranslating: '{text}'")
    result = translator.translate(text, target_language="fr", source_language="en")
    
    logger.info(f"Translated: {result.translated_text}")
    logger.info(f"Source language: {result.source_language}")
    logger.info(f"Target language: {result.target_language}")
    logger.info(f"Confidence: {result.confidence:.2%}")
    logger.info(f"Processing time: {result.processing_time_ms:.2f}ms")
    
    # Translate batch
    texts = ["First text", "Second text", "Third text"]
    logger.info(f"\nTranslating batch of {len(texts)} texts...")
    batch_results = translator.translate_batch(texts, target_language="es")
    for i, r in enumerate(batch_results, 1):
        logger.info(f"  Text {i}: '{r.translated_text}' ({r.confidence:.2%})")
    
    # Detect language
    logger.info("\nDetecting language...")
    detected = translator.detect_language("Hello world")
    logger.info(f"Detected language: {detected}")


def demo_search_adapter():
    """Demonstrate search adapter."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO 3: Search Adapter")
    logger.info("=" * 60)
    
    # Create mock search backend
    search = MockSearchAdapter()
    
    logger.info(f"Backend: {search.name}")
    logger.info(f"Version: {search.get_version()}")
    logger.info(f"Available: {search.is_available()}")
    
    # Index documents
    logger.info("\nIndexing documents...")
    docs = [
        IndexedDocument(
            doc_id="doc1",
            title="Python Programming Guide",
            content="Learn Python programming with examples and best practices. Python is a versatile language.",
            language="en",
            file_path=Path("/guides/python.txt"),
            metadata={"author": "John Doe", "tags": ["python", "programming"]},
            created_at=datetime.now(),
            updated_at=datetime.now()
        ),
        IndexedDocument(
            doc_id="doc2",
            title="JavaScript Basics",
            content="Introduction to JavaScript for beginners. Learn variables, functions, and more.",
            language="en",
            file_path=Path("/guides/javascript.txt"),
            metadata={"author": "Jane Smith", "tags": ["javascript", "web"]},
            created_at=datetime.now(),
            updated_at=datetime.now()
        ),
        IndexedDocument(
            doc_id="doc3",
            title="Guide Python",
            content="Apprendre Python avec des exemples pratiques.",
            language="fr",
            file_path=Path("/guides/python_fr.txt"),
            metadata={"author": "Marie Dubois", "tags": ["python"]},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    ]
    
    indexed_count = search.index_batch(docs)
    logger.info(f"Indexed {indexed_count} documents")
    logger.info(f"Total documents: {search.count_documents()}")
    logger.info(f"English documents: {search.count_documents(language='en')}")
    logger.info(f"French documents: {search.count_documents(language='fr')}")
    
    # Search
    logger.info("\nSearching for 'Python'...")
    results = search.search("Python")
    logger.info(f"Found {len(results)} results:")
    for r in results:
        logger.info(f"  - {r.title} (score: {r.score:.2f})")
        logger.info(f"    Language: {r.language}")
        logger.info(f"    Snippet: {r.content_snippet[:80]}...")
    
    # Search with language filter
    logger.info("\nSearching for 'Python' in French only...")
    results_fr = search.search("Python", language="fr")
    logger.info(f"Found {len(results_fr)} French results:")
    for r in results_fr:
        logger.info(f"  - {r.title}")
    
    # Get specific document
    logger.info("\nRetrieving document 'doc2'...")
    doc = search.get_document("doc2")
    if doc:
        logger.info(f"Title: {doc.title}")
        logger.info(f"Content: {doc.content[:80]}...")
        logger.info(f"Metadata: {doc.metadata}")
    
    # Update document
    logger.info("\nUpdating document 'doc1'...")
    search.update_document("doc1", {"title": "Python Programming Guide - Updated"})
    updated_doc = search.get_document("doc1")
    if updated_doc:
        logger.info(f"Updated title: {updated_doc.title}")
    
    # Delete document
    logger.info("\nDeleting document 'doc3'...")
    search.delete_document("doc3")
    logger.info(f"Documents remaining: {search.count_documents()}")
    
    # Pagination
    logger.info("\nDemonstrating pagination...")
    # Index more docs
    extra_docs = [
        IndexedDocument(
            doc_id=f"extra{i}",
            title=f"Extra Document {i}",
            content="Some extra content for pagination test",
            language="en",
            file_path=Path(f"/extra{i}.txt"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        for i in range(10)
    ]
    search.index_batch(extra_docs)
    
    page1 = search.search("content", limit=3, offset=0)
    page2 = search.search("content", limit=3, offset=3)
    logger.info(f"Page 1 ({len(page1)} results): {[r.doc_id for r in page1]}")
    logger.info(f"Page 2 ({len(page2)} results): {[r.doc_id for r in page2]}")
    
    # Clear index
    logger.info("\nClearing index...")
    search.clear_index()
    logger.info(f"Documents after clear: {search.count_documents()}")


def demo_adapter_compatibility():
    """Demonstrate adapter protocol compatibility."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO 4: Adapter Protocol Compatibility")
    logger.info("=" * 60)
    
    from indexao.adapters.ocr import OCRAdapter
    from indexao.adapters.translator import TranslatorAdapter
    from indexao.adapters.search import SearchAdapter
    
    # Check protocol compliance
    ocr = MockOCRAdapter()
    translator = MockTranslatorAdapter()
    search = MockSearchAdapter()
    
    logger.info("Checking protocol compliance...")
    logger.info(f"MockOCRAdapter implements OCRAdapter: {isinstance(ocr, OCRAdapter)}")
    logger.info(f"MockTranslatorAdapter implements TranslatorAdapter: {isinstance(translator, TranslatorAdapter)}")
    logger.info(f"MockSearchAdapter implements SearchAdapter: {isinstance(search, SearchAdapter)}")
    
    # Check common interface
    logger.info("\nCommon interface methods:")
    for adapter, protocol_name in [(ocr, "OCR"), (translator, "Translator"), (search, "Search")]:
        logger.info(f"{protocol_name} Adapter:")
        logger.info(f"  name: {adapter.name}")
        logger.info(f"  is_available(): {adapter.is_available()}")
        logger.info(f"  get_version(): {adapter.get_version()}")


def main():
    """Run all demos."""
    logger.info("Starting adapter demos...")
    logger.info(f"Python version: {sys.version}")
    
    try:
        demo_ocr_adapter()
        demo_translator_adapter()
        demo_search_adapter()
        demo_adapter_compatibility()
        
        logger.info("\n" + "=" * 60)
        logger.info("All demos completed successfully! ✓")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.exception(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
