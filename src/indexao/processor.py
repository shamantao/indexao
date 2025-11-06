"""
Document Processor Module

Main processing pipeline that orchestrates:
Scanner → OCR → Translator → Indexer

Handles different file types, error recovery, and progress tracking.

Author: Indexao Team
License: MIT
"""

import asyncio
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .config import Config
from .logger import get_logger
from .scanner import FileMetadata
from .upload_handler import UploadHandler
from .paths import get_path_adapter
from .adapters.ocr import MockOCRAdapter, OCRResult
from .adapters.translator import MockTranslatorAdapter, TranslationResult
from .adapters.search import MockSearchAdapter, IndexedDocument
from .database import DocumentDatabase
from .models.document import Document, DocumentMetadata, ProcessingStatus as DocStatus, ProcessingStage

logger = get_logger(__name__)


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    SCANNING = "scanning"
    OCR = "ocr"
    TRANSLATING = "translating"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, Enum):
    """Supported file types for processing."""
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


@dataclass
class ProcessingResult:
    """
    Result of document processing.
    
    Attributes:
        document_id: Unique document identifier
        status: Final processing status
        file_metadata: File metadata from scanner
        extracted_text: Text extracted from document
        translations: Dictionary of translations (lang_code -> text)
        search_indexed: Whether document was indexed for search
        error_message: Error message if processing failed
        processing_time_seconds: Total processing time
        stages_completed: List of completed processing stages
    """
    document_id: str
    status: ProcessingStatus
    file_metadata: Optional[FileMetadata] = None
    extracted_text: Optional[str] = None
    translations: Dict[str, str] = field(default_factory=dict)
    search_indexed: bool = False
    error_message: Optional[str] = None
    processing_time_seconds: float = 0.0
    stages_completed: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'document_id': self.document_id,
            'status': self.status.value,
            'file_metadata': self.file_metadata.to_dict() if self.file_metadata else None,
            'extracted_text': self.extracted_text,
            'translations': self.translations,
            'search_indexed': self.search_indexed,
            'error_message': self.error_message,
            'processing_time_seconds': round(self.processing_time_seconds, 2),
            'stages_completed': self.stages_completed,
        }


class ProcessingError(Exception):
    """Base exception for processing errors."""
    pass


class DocumentProcessor:
    """
    Main document processing pipeline.
    
    Orchestrates the complete workflow:
    1. File type detection
    2. Text extraction (OCR for images, direct read for text)
    3. Translation to target languages
    4. Search indexing
    
    Attributes:
        config: Application configuration
        upload_handler: Upload handler for queue management
        ocr_adapter: OCR adapter (will be initialized from config)
        translator_adapter: Translation adapter (will be initialized from config)
        search_adapter: Search adapter (will be initialized from config)
    """
    
    def __init__(self, config: Config, upload_handler: UploadHandler):
        """
        Initialize document processor.
        
        Args:
            config: Application configuration
            upload_handler: Upload handler instance
        """
        self.config = config
        self.upload_handler = upload_handler
        
        # Initialize database
        self.db = DocumentDatabase("data/indexao.db")
        logger.info(f"✓ Database initialized")
        
        # Initialize adapters based on configuration
        self._init_adapters()
        
        logger.info("Document processor initialized with adapters")
    
    def _init_adapters(self):
        """Initialize OCR, Translator, and Search adapters from configuration."""
        # OCR Adapter
        ocr_engine = self.config.plugins.ocr.engine
        if ocr_engine == "mock":
            self._ocr_adapter = MockOCRAdapter(
                mock_text="[OCR extracted text]",
                confidence=0.95
            )
            logger.info(f"✓ OCR adapter initialized: {ocr_engine}")
        else:
            logger.warning(f"Unsupported OCR engine: {ocr_engine}, falling back to mock")
            self._ocr_adapter = MockOCRAdapter()
        
        # Translator Adapter
        translator_engine = self.config.plugins.translator.engine
        if translator_engine == "mock":
            self._translator_adapter = MockTranslatorAdapter()
            logger.info(f"✓ Translator adapter initialized: {translator_engine}")
        else:
            logger.warning(f"Unsupported translator engine: {translator_engine}, falling back to mock")
            self._translator_adapter = MockTranslatorAdapter()
        
        # Search Adapter
        search_engine = self.config.plugins.search.engine
        if search_engine == "mock":
            self._search_adapter = MockSearchAdapter()
            logger.info(f"✓ Search adapter initialized: {search_engine}")
        else:
            logger.warning(f"Unsupported search engine: {search_engine}, falling back to mock")
            self._search_adapter = MockSearchAdapter()
    
    def _detect_file_type(self, metadata: FileMetadata) -> FileType:
        """
        Detect file type from metadata.
        
        Args:
            metadata: File metadata
            
        Returns:
            FileType enum value
        """
        mime_type = metadata.mime_type.lower()
        extension = metadata.extension.lower()
        
        # Text files
        if mime_type.startswith('text/') or extension in {'.txt', '.md', '.csv', '.json', '.xml'}:
            return FileType.TEXT
        
        # Images
        if mime_type.startswith('image/') or extension in {'.jpg', '.jpeg', '.png', '.tiff', '.gif', '.bmp'}:
            return FileType.IMAGE
        
        # PDFs
        if mime_type == 'application/pdf' or extension == '.pdf':
            return FileType.PDF
        
        # Office documents
        if extension in {'.doc', '.docx', '.odt', '.rtf'}:
            return FileType.DOCUMENT
        
        logger.warning(f"Unknown file type: {mime_type} ({extension})")
        return FileType.UNKNOWN
    
    def _read_text_file(self, file_path: Path) -> str:
        """
        Read text directly from file using Path Manager.
        
        Args:
            file_path: Path to text file
            
        Returns:
            File content as string
            
        Raises:
            ProcessingError: If file cannot be read
        """
        try:
            # Use path adapter for file reading with absolute path
            path_adapter = get_path_adapter(f"file://{file_path.parent.resolve()}")
            
            # Read file as bytes using relative path
            content_bytes = path_adapter.read_file(file_path.name)
            
            # Try UTF-8 first
            try:
                content = content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # Fallback to latin-1 (never fails)
                logger.debug(f"UTF-8 decode failed, trying latin-1: {file_path.name}")
                content = content_bytes.decode('latin-1')
            
            logger.info(f"✓ Read {len(content)} chars from {file_path.name} via Path Manager")
            return content.strip()
        
        except Exception as e:
            raise ProcessingError(f"Failed to read text file: {e}") from e
    
    def _extract_text_from_image(self, file_path: Path) -> str:
        """
        Extract text from image using OCR adapter.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Extracted text
            
        Raises:
            ProcessingError: If OCR fails
        """
        try:
            logger.debug(f"  → Applying OCR adapter to: {file_path.name}")
            
            # Use OCR adapter
            ocr_result: OCRResult = self._ocr_adapter.process_image(file_path)
            
            logger.debug(
                f"  → OCR completed: {len(ocr_result.text)} chars, "
                f"confidence={ocr_result.confidence:.2f}, "
                f"language={ocr_result.language}"
            )
            
            return ocr_result.text
        
        except Exception as e:
            raise ProcessingError(f"OCR extraction failed: {e}") from e
    
    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """
        Extract text from PDF.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text
            
        Raises:
            ProcessingError: If extraction fails
        """
        try:
            # For now, return mock text (will be implemented with PyPDF2 or similar)
            logger.debug(f"Mock PDF extraction from {file_path.name}")
            return f"[Mock PDF text extracted from {file_path.name}]"
        
        except Exception as e:
            raise ProcessingError(f"PDF extraction failed: {e}") from e
    
    def _extract_text(self, file_path: Path, file_type: FileType) -> str:
        """
        Extract text from file based on type.
        
        Args:
            file_path: Path to file
            file_type: Detected file type
            
        Returns:
            Extracted text content
            
        Raises:
            ProcessingError: If extraction fails
        """
        extraction_start = datetime.now()
        
        if file_type == FileType.TEXT:
            logger.debug(f"  → Reading text file directly: {file_path.name}")
            result = self._read_text_file(file_path)
        
        elif file_type == FileType.IMAGE:
            logger.debug(f"  → Applying OCR to image: {file_path.name}")
            result = self._extract_text_from_image(file_path)
        
        elif file_type == FileType.PDF:
            logger.debug(f"  → Extracting from PDF: {file_path.name}")
            result = self._extract_text_from_pdf(file_path)
        
        elif file_type == FileType.DOCUMENT:
            # Office documents - would use python-docx or similar
            logger.warning(f"  → Document type not yet supported: {file_type}")
            result = f"[Document extraction not yet implemented for {file_path.name}]"
        
        else:
            logger.error(f"  → Unsupported file type: {file_type}")
            raise ProcessingError(f"Unsupported file type: {file_type}")
        
        duration = (datetime.now() - extraction_start).total_seconds()
        logger.debug(f"  → Extraction took {duration:.3f}s, got {len(result)} chars")
        
        return result
    
    def _translate_text(self, text: str, target_languages: List[str]) -> Dict[str, str]:
        """
        Translate text to target languages using translator adapter.
        
        Args:
            text: Text to translate
            target_languages: List of target language codes (e.g., ['fr', 'zh'])
            
        Returns:
            Dictionary of translations (lang_code -> translated_text)
        """
        translations = {}
        
        for lang in target_languages:
            logger.debug(f"  → Translating to {lang} via adapter")
            
            # Use translator adapter
            translation_result: TranslationResult = self._translator_adapter.translate(
                text=text,
                target_language=lang,
                source_language="auto"  # Auto-detect
            )
            
            translations[lang] = translation_result.translated_text
        
        return translations
    
    def _index_document(
        self,
        document_id: str,
        metadata: FileMetadata,
        text: str,
        translations: Dict[str, str]
    ) -> bool:
        """
        Index document for search using search adapter.
        
        Args:
            document_id: Document ID
            metadata: File metadata
            text: Extracted text
            translations: Translations dictionary
            
        Returns:
            True if indexing succeeded
        """
        try:
            logger.debug(f"  → Indexing via search adapter: {document_id}")
            
            # Prepare document for indexing using IndexedDocument
            indexed_doc = IndexedDocument(
                doc_id=document_id,
                title=metadata.filename,
                content=text,
                language="auto",  # Will be detected
                file_path=metadata.path,
                metadata={
                    "translations": translations,
                    "mime_type": metadata.mime_type,
                    "size_bytes": metadata.size_bytes,
                    "modified_at": metadata.modified_at.isoformat(),
                    "extension": metadata.extension,
                }
            )
            
            # Use search adapter
            result = self._search_adapter.index_document(indexed_doc)
            
            logger.debug(f"  → Indexing result: success={result}")
            return result
        
        except Exception as e:
            logger.error(f"  ✗ Indexing failed for {document_id}: {e}")
            return False
    
    def process_file(self, file_path: Path, metadata: FileMetadata) -> ProcessingResult:
        """
        Process a single file through the complete pipeline.
        
        Args:
            file_path: Path to file to process
            metadata: File metadata from scanner
            
        Returns:
            ProcessingResult with complete processing information
        """
        start_time = datetime.now()
        document_id = f"DOC_{file_path.stem[:8].upper()}"
        
        result = ProcessingResult(
            document_id=document_id,
            status=ProcessingStatus.PENDING,
            file_metadata=metadata
        )
        
        try:
            logger.info(
                f"[PIPELINE START] Document: {document_id} | "
                f"File: {metadata.filename} | "
                f"Size: {metadata.size_bytes} bytes | "
                f"MIME: {metadata.mime_type}"
            )
            
            # Stage 1: File type detection
            result.status = ProcessingStatus.SCANNING
            logger.info(f"[STAGE 1/4] File type detection - {document_id}")
            file_type = self._detect_file_type(metadata)
            result.stages_completed.append("file_type_detection")
            logger.info(f"✓ File type detected: {file_type.value} | MIME: {metadata.mime_type} | Ext: {metadata.extension}")
            
            # Stage 2: Text extraction
            result.status = ProcessingStatus.OCR
            logger.info(f"[STAGE 2/4] Text extraction ({file_type.value}) - {document_id}")
            stage2_start = datetime.now()
            extracted_text = self._extract_text(file_path, file_type)
            stage2_duration = (datetime.now() - stage2_start).total_seconds()
            result.extracted_text = extracted_text
            result.stages_completed.append("text_extraction")
            logger.info(
                f"✓ Text extracted: {len(extracted_text)} chars | "
                f"Duration: {stage2_duration:.2f}s | "
                f"Preview: {extracted_text[:100]}..."
            )
            
            # Stage 3: Translation
            result.status = ProcessingStatus.TRANSLATING
            target_languages = self.config.plugins.translator.target_languages
            logger.info(f"[STAGE 3/4] Translation to {len(target_languages)} languages - {document_id}")
            stage3_start = datetime.now()
            translations = self._translate_text(extracted_text, target_languages)
            stage3_duration = (datetime.now() - stage3_start).total_seconds()
            result.translations = translations
            result.stages_completed.append("translation")
            logger.info(
                f"✓ Translations completed: {list(translations.keys())} | "
                f"Duration: {stage3_duration:.2f}s"
            )
            
            # Stage 4: Search indexing
            result.status = ProcessingStatus.INDEXING
            logger.info(f"[STAGE 4/4] Search indexing - {document_id}")
            stage4_start = datetime.now()
            indexed = self._index_document(
                document_id,
                metadata,
                extracted_text,
                translations
            )
            stage4_duration = (datetime.now() - stage4_start).total_seconds()
            result.search_indexed = indexed
            result.stages_completed.append("indexing")
            
            if indexed:
                logger.info(f"✓ Document indexed successfully | Duration: {stage4_duration:.2f}s")
            else:
                logger.warning(f"⚠ Indexing failed but pipeline continued | Duration: {stage4_duration:.2f}s")
            
            # Success
            result.status = ProcessingStatus.COMPLETED
            
            # Calculate processing time
            duration = (datetime.now() - start_time).total_seconds()
            result.processing_time_seconds = duration
            
            # Save to database
            try:
                doc_metadata = DocumentMetadata(
                    filename=metadata.filename,
                    file_path=str(file_path),
                    file_size=metadata.size_bytes,
                    mime_type=metadata.mime_type,
                    text_length=len(extracted_text),
                    language="auto",
                    processing_duration=duration,
                    stages_completed=result.stages_completed,
                )
                
                document = Document(
                    doc_id=document_id,
                    content=extracted_text,
                    title=metadata.filename,
                    metadata=doc_metadata,
                    translations=translations,
                    status=DocStatus.COMPLETED,
                    current_stage=ProcessingStage.COMPLETED,
                    indexed=indexed,
                    search_engine="mock",
                )
                
                document.mark_completed()
                
                if self.db.create_document(document):
                    logger.info(f"✓ Document saved to database: {document_id}")
                else:
                    logger.warning(f"⚠ Failed to save document to database: {document_id}")
            
            except Exception as db_error:
                logger.error(f"Database save error for {document_id}: {db_error}")
            
            logger.info(
                f"[PIPELINE SUCCESS] {document_id} | "
                f"Total: {duration:.2f}s | "
                f"Stages: {len(result.stages_completed)}/4 | "
                f"Text: {len(extracted_text)} chars | "
                f"Translations: {len(translations)} | "
                f"Indexed: {indexed}"
            )
            
            return result
        
        except ProcessingError as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            result.processing_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # Save failed document to database
            try:
                doc_metadata = DocumentMetadata(
                    filename=metadata.filename,
                    file_path=str(file_path),
                    file_size=metadata.size_bytes,
                    mime_type=metadata.mime_type,
                    text_length=len(result.extracted_text) if result.extracted_text else 0,
                    processing_duration=result.processing_time_seconds,
                    stages_completed=result.stages_completed,
                )
                
                document = Document(
                    doc_id=document_id,
                    content=result.extracted_text or "",
                    title=metadata.filename,
                    metadata=doc_metadata,
                    translations=result.translations,
                    status=DocStatus.FAILED,
                    current_stage=ProcessingStage.FAILED,
                    error_message=str(e),
                    indexed=False,
                )
                
                document.mark_failed(str(e))
                
                if self.db.create_document(document):
                    logger.info(f"✓ Failed document saved to database: {document_id}")
            
            except Exception as db_error:
                logger.error(f"Database save error for failed document {document_id}: {db_error}")
            
            logger.error(
                f"[PIPELINE FAILED] {document_id} | "
                f"Duration: {result.processing_time_seconds:.2f}s | "
                f"Last stage: {result.status.value} | "
                f"Completed stages: {result.stages_completed} | "
                f"Error: {e}"
            )
            return result
        
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = f"Unexpected error: {str(e)}"
            result.processing_time_seconds = (datetime.now() - start_time).total_seconds()
            
            logger.error(
                f"[PIPELINE ERROR] {document_id} | "
                f"Duration: {result.processing_time_seconds:.2f}s | "
                f"Last stage: {result.status.value} | "
                f"Completed stages: {result.stages_completed} | "
                f"Unexpected error: {e}",
                exc_info=True
            )
            return result
    
    def process_queue(self) -> List[ProcessingResult]:
        """
        Process all files in the upload queue.
        
        Returns:
            List of ProcessingResult objects
        """
        logger.info("=" * 80)
        logger.info("[QUEUE PROCESSING START]")
        
        queue_files = self.upload_handler.list_queue()
        logger.info(f"Queue contains {len(queue_files)} file(s)")
        
        if not queue_files:
            logger.info("Queue is empty, nothing to process")
            logger.info("=" * 80)
            return []
        
        results = []
        
        for idx, queue_file in enumerate(queue_files, 1):
            try:
                logger.info(f"\n>>> Processing file {idx}/{len(queue_files)}: {queue_file.name}")
                
                # Extract metadata
                from .scanner import FileScanner
                scanner = FileScanner(queue_file.parent, recursive=False)
                
                # Scan and find matching file by name
                all_metadata = scanner.scan()
                metadata = None
                
                for m in all_metadata:
                    if m.filename == queue_file.name:
                        metadata = m
                        break
                
                if not metadata:
                    logger.error(f"✗ Failed to get metadata for {queue_file.name}")
                    continue
                
                # Process file
                result = self.process_file(queue_file, metadata)
                results.append(result)
                
            except Exception as e:
                logger.error(f"✗ Exception while processing {queue_file.name}: {e}", exc_info=True)
        
        # Summary
        completed = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
        total_time = sum(r.processing_time_seconds for r in results)
        
        logger.info("\n" + "=" * 80)
        logger.info("[QUEUE PROCESSING COMPLETE]")
        logger.info(f"Total processed: {len(results)}")
        logger.info(f"  ✓ Completed: {completed}")
        logger.info(f"  ✗ Failed: {failed}")
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info(f"Average time: {total_time/len(results):.2f}s per document" if results else "N/A")
        logger.info("=" * 80)
        
        return results
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get processing status summary.
        
        Returns:
            Dictionary with queue statistics
        """
        queue_files = self.upload_handler.list_queue()
        
        return {
            'queue_count': len(queue_files),
            'processor_ready': True,
            'adapters': {
                'ocr': self.config.plugins.ocr.engine,
                'translator': self.config.plugins.translator.engine,
                'search': self.config.plugins.search.engine,
            }
        }


async def process_document_async(
    processor: DocumentProcessor,
    file_path: Path,
    metadata: FileMetadata
) -> ProcessingResult:
    """
    Async wrapper for document processing.
    
    Useful for processing multiple documents concurrently.
    
    Args:
        processor: DocumentProcessor instance
        file_path: Path to file
        metadata: File metadata
        
    Returns:
        ProcessingResult
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        processor.process_file,
        file_path,
        metadata
    )
