"""
Document data models for IndexAO.

Defines Pydantic models for document metadata, processing status, and translations.
Follows Sprint 0 standards: Logger + Path Manager.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from indexao.logger import get_logger

logger = get_logger(__name__)


class ProcessingStage(str, Enum):
    """Processing pipeline stages."""
    
    QUEUED = "queued"
    FILE_TYPE_DETECTION = "file_type_detection"
    TEXT_EXTRACTION = "text_extraction"
    TRANSLATION = "translation"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus(str, Enum):
    """Overall document processing status."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranslationData:
    """Translation data for a document."""
    
    language: str
    text: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "language": self.language,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TranslationData":
        """Create from dictionary."""
        return cls(
            language=data["language"],
            text=data["text"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class DocumentMetadata:
    """Document metadata extracted during processing."""
    
    # File information
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    
    # Content information
    text_length: int = 0
    language: Optional[str] = None
    
    # OCR information (if applicable)
    ocr_confidence: Optional[float] = None
    ocr_engine: Optional[str] = None
    
    # Processing information
    processing_duration: float = 0.0
    stages_completed: List[str] = field(default_factory=list)
    
    # Additional metadata
    extra: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "text_length": self.text_length,
            "language": self.language,
            "ocr_confidence": self.ocr_confidence,
            "ocr_engine": self.ocr_engine,
            "processing_duration": self.processing_duration,
            "stages_completed": self.stages_completed,
            "extra": self.extra,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DocumentMetadata":
        """Create from dictionary."""
        return cls(
            filename=data["filename"],
            file_path=data["file_path"],
            file_size=data["file_size"],
            mime_type=data["mime_type"],
            text_length=data.get("text_length", 0),
            language=data.get("language"),
            ocr_confidence=data.get("ocr_confidence"),
            ocr_engine=data.get("ocr_engine"),
            processing_duration=data.get("processing_duration", 0.0),
            stages_completed=data.get("stages_completed", []),
            extra=data.get("extra", {}),
        )


@dataclass
class Document:
    """
    Main document model for IndexAO.
    
    Represents a document with all its metadata, content, translations,
    and processing status.
    """
    
    # Primary key
    doc_id: str
    
    # Content
    content: str
    title: Optional[str] = None
    
    # Metadata
    metadata: Optional[DocumentMetadata] = None
    
    # Translations
    translations: Dict[str, str] = field(default_factory=dict)
    
    # Processing status
    status: ProcessingStatus = ProcessingStatus.PENDING
    current_stage: ProcessingStage = ProcessingStage.QUEUED
    error_message: Optional[str] = None
    
    # Search indexing
    indexed: bool = False
    search_engine: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate document after initialization."""
        if not self.doc_id:
            raise ValueError("doc_id is required")
        if not self.content:
            logger.warning(f"Document {self.doc_id} has empty content")
    
    def mark_stage(self, stage: ProcessingStage):
        """Mark current processing stage."""
        self.current_stage = stage
        self.updated_at = datetime.utcnow()
        logger.debug(f"Document {self.doc_id} → stage: {stage.value}")
    
    def mark_completed(self):
        """Mark document as completed."""
        self.status = ProcessingStatus.COMPLETED
        self.current_stage = ProcessingStage.COMPLETED
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        logger.info(f"✓ Document {self.doc_id} marked as COMPLETED")
    
    def mark_failed(self, error: str):
        """Mark document as failed with error message."""
        self.status = ProcessingStatus.FAILED
        self.current_stage = ProcessingStage.FAILED
        self.error_message = error
        self.updated_at = datetime.utcnow()
        logger.error(f"✗ Document {self.doc_id} marked as FAILED: {error}")
    
    def add_translation(self, language: str, text: str):
        """Add a translation for a specific language."""
        self.translations[language] = text
        self.updated_at = datetime.utcnow()
        logger.debug(f"Translation added: {self.doc_id} → {language} ({len(text)} chars)")
    
    def mark_indexed(self, engine: str):
        """Mark document as indexed in search engine."""
        self.indexed = True
        self.search_engine = engine
        self.updated_at = datetime.utcnow()
        logger.debug(f"Document {self.doc_id} indexed in {engine}")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "title": self.title,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "translations": self.translations,
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "error_message": self.error_message,
            "indexed": self.indexed,
            "search_engine": self.search_engine,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Document":
        """Create from dictionary."""
        metadata = None
        if data.get("metadata"):
            metadata = DocumentMetadata.from_dict(data["metadata"])
        
        return cls(
            doc_id=data["doc_id"],
            content=data["content"],
            title=data.get("title"),
            metadata=metadata,
            translations=data.get("translations", {}),
            status=ProcessingStatus(data.get("status", "pending")),
            current_stage=ProcessingStage(data.get("current_stage", "queued")),
            error_message=data.get("error_message"),
            indexed=data.get("indexed", False),
            search_engine=data.get("search_engine"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            processed_at=datetime.fromisoformat(data["processed_at"]) if data.get("processed_at") else None,
        )
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Document(doc_id={self.doc_id}, "
            f"status={self.status.value}, "
            f"stage={self.current_stage.value}, "
            f"content_length={len(self.content)}, "
            f"translations={len(self.translations)})"
        )
