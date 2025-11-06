"""
SQLite database layer for IndexAO.

Provides persistent storage for document metadata and processing queue.
Follows Sprint 0 standards: Logger + Path Manager.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from indexao.logger import get_logger
from indexao.models.document import Document, DocumentMetadata, ProcessingStage, ProcessingStatus
from indexao.paths import get_path_adapter

logger = get_logger(__name__)


class DatabaseError(Exception):
    """Database operation error."""
    pass


class DocumentDatabase:
    """
    SQLite database manager for IndexAO documents.
    
    Manages two tables:
    - documents: Persistent storage of document metadata
    - processing_queue: Temporary queue for documents being processed
    """
    
    # Schema version for migrations
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str = "data/indexao.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file (relative to project root)
        """
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Database initialized: {self.db_path}")
        
        # Initialize schema
        self._init_schema()
        
        # Verify schema version
        self._check_schema_version()
    
    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database operation failed: {e}")
        finally:
            conn.close()
    
    def _init_schema(self):
        """Initialize database schema."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            # Schema version table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    title TEXT,
                    
                    -- Metadata (JSON)
                    metadata TEXT,
                    
                    -- Translations (JSON: {lang: text})
                    translations TEXT DEFAULT '{}',
                    
                    -- Processing status
                    status TEXT NOT NULL DEFAULT 'pending',
                    current_stage TEXT NOT NULL DEFAULT 'queued',
                    error_message TEXT,
                    
                    -- Search indexing
                    indexed INTEGER DEFAULT 0,
                    search_engine TEXT,
                    
                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
                )
            """)
            
            # Processing queue table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT NOT NULL,
                    
                    -- Queue management
                    priority INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    
                    -- Timestamps
                    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                )
            """)
            
            # Indices for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_status 
                ON documents(status)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_created 
                ON documents(created_at DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_queue_priority 
                ON processing_queue(priority DESC, queued_at ASC)
            """)
            
            logger.info("✓ Database schema initialized")
    
    def _check_schema_version(self):
        """Check and update schema version if needed."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            
            current_version = row[0] if row else 0
            
            if current_version < self.SCHEMA_VERSION:
                cursor.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (self.SCHEMA_VERSION,)
                )
                logger.info(f"✓ Schema upgraded: v{current_version} → v{self.SCHEMA_VERSION}")
            else:
                logger.debug(f"Schema version: v{current_version}")
    
    # ========================================================================
    # DOCUMENT CRUD OPERATIONS
    # ========================================================================
    
    def create_document(self, document: Document) -> bool:
        """
        Create a new document in the database.
        
        Args:
            document: Document object to create
            
        Returns:
            True if successful
        """
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                
                metadata_json = json.dumps(document.metadata.to_dict()) if document.metadata else None
                translations_json = json.dumps(document.translations)
                
                cursor.execute("""
                    INSERT INTO documents (
                        doc_id, content, title, metadata, translations,
                        status, current_stage, error_message,
                        indexed, search_engine,
                        created_at, updated_at, processed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document.doc_id,
                    document.content,
                    document.title,
                    metadata_json,
                    translations_json,
                    document.status.value,
                    document.current_stage.value,
                    document.error_message,
                    1 if document.indexed else 0,
                    document.search_engine,
                    document.created_at.isoformat(),
                    document.updated_at.isoformat(),
                    document.processed_at.isoformat() if document.processed_at else None,
                ))
                
                logger.info(f"✓ Document created: {document.doc_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create document {document.doc_id}: {e}")
            return False
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document object or None if not found
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_document(row)
    
    def update_document(self, document: Document) -> bool:
        """
        Update an existing document.
        
        Args:
            document: Document object with updated data
            
        Returns:
            True if successful
        """
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                
                metadata_json = json.dumps(document.metadata.to_dict()) if document.metadata else None
                translations_json = json.dumps(document.translations)
                
                cursor.execute("""
                    UPDATE documents SET
                        content = ?,
                        title = ?,
                        metadata = ?,
                        translations = ?,
                        status = ?,
                        current_stage = ?,
                        error_message = ?,
                        indexed = ?,
                        search_engine = ?,
                        updated_at = ?,
                        processed_at = ?
                    WHERE doc_id = ?
                """, (
                    document.content,
                    document.title,
                    metadata_json,
                    translations_json,
                    document.status.value,
                    document.current_stage.value,
                    document.error_message,
                    1 if document.indexed else 0,
                    document.search_engine,
                    document.updated_at.isoformat(),
                    document.processed_at.isoformat() if document.processed_at else None,
                    document.doc_id,
                ))
                
                if cursor.rowcount == 0:
                    logger.warning(f"Document not found for update: {document.doc_id}")
                    return False
                
                logger.debug(f"Document updated: {document.doc_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update document {document.doc_id}: {e}")
            return False
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            True if successful
        """
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
                
                if cursor.rowcount == 0:
                    logger.warning(f"Document not found for deletion: {doc_id}")
                    return False
                
                logger.info(f"✓ Document deleted: {doc_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False
    
    def list_documents(
        self,
        status: Optional[ProcessingStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Document]:
        """
        List documents with optional filtering.
        
        Args:
            status: Filter by processing status
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of Document objects
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM documents"
            params = []
            
            if status:
                query += " WHERE status = ?"
                params.append(status.value)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            documents = [self._row_to_document(row) for row in rows]
            logger.debug(f"Listed {len(documents)} documents (status={status}, limit={limit})")
            
            return documents
    
    def count_documents(self, status: Optional[ProcessingStatus] = None) -> int:
        """
        Count documents with optional filtering.
        
        Args:
            status: Filter by processing status
            
        Returns:
            Number of documents
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            
            if status:
                cursor.execute(
                    "SELECT COUNT(*) FROM documents WHERE status = ?",
                    (status.value,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM documents")
            
            return cursor.fetchone()[0]
    
    # ========================================================================
    # PROCESSING QUEUE OPERATIONS
    # ========================================================================
    
    def enqueue_document(
        self,
        doc_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        priority: int = 0
    ) -> bool:
        """
        Add a document to the processing queue.
        
        Args:
            doc_id: Document ID
            filename: Original filename
            file_path: Path to file
            file_size: File size in bytes
            mime_type: MIME type
            priority: Queue priority (higher = sooner)
            
        Returns:
            True if successful
        """
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO processing_queue (
                        doc_id, filename, file_path, file_size, mime_type, priority
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (doc_id, filename, file_path, file_size, mime_type, priority))
                
                logger.info(f"✓ Document enqueued: {doc_id} (priority={priority})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to enqueue document {doc_id}: {e}")
            return False
    
    def dequeue_document(self, doc_id: str) -> bool:
        """
        Remove a document from the processing queue.
        
        Args:
            doc_id: Document ID
            
        Returns:
            True if successful
        """
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM processing_queue WHERE doc_id = ?", (doc_id,))
                
                logger.debug(f"Document dequeued: {doc_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to dequeue document {doc_id}: {e}")
            return False
    
    def get_queue_stats(self) -> Dict[str, int]:
        """
        Get processing queue statistics.
        
        Returns:
            Dictionary with queue stats
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM processing_queue")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM processing_queue WHERE started_at IS NOT NULL")
            in_progress = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM processing_queue WHERE retry_count > 0")
            retries = cursor.fetchone()[0]
            
            return {
                "total": total,
                "pending": total - in_progress,
                "in_progress": in_progress,
                "retries": retries,
            }
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _row_to_document(self, row: sqlite3.Row) -> Document:
        """Convert database row to Document object."""
        metadata = None
        if row["metadata"]:
            metadata = DocumentMetadata.from_dict(json.loads(row["metadata"]))
        
        translations = json.loads(row["translations"]) if row["translations"] else {}
        
        return Document(
            doc_id=row["doc_id"],
            content=row["content"],
            title=row["title"],
            metadata=metadata,
            translations=translations,
            status=ProcessingStatus(row["status"]),
            current_stage=ProcessingStage(row["current_stage"]),
            error_message=row["error_message"],
            indexed=bool(row["indexed"]),
            search_engine=row["search_engine"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            processed_at=datetime.fromisoformat(row["processed_at"]) if row["processed_at"] else None,
        )
    
    def clear_all(self) -> bool:
        """
        Clear all data from database (for testing).
        
        WARNING: This deletes all documents and queue entries!
        
        Returns:
            True if successful
        """
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM processing_queue")
                cursor.execute("DELETE FROM documents")
                
                logger.warning("⚠ Database cleared (all documents deleted)")
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return False
