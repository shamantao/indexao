"""
Fast Track Service (Sprint 2)

Handles immediate document indexing via the "Upload" UI.
Implements Hybrid Indexing strategy:
1. Compute Hash of incoming file.
2. Index immediately if new.
3. Register Hash in DB for later "Rendez-vous" with Volume Watcher.
"""

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import UploadFile

from indexao.config import get_config
from indexao.database import DocumentDatabase
from indexao.processor import DocumentProcessor
from indexao.scanner import FileMetadata
from indexao.upload_handler import UploadHandler
from indexao.logger import get_logger

logger = get_logger(__name__)

class FastTrackService:
    """
    Service for fast-track (immediate) indexing.
    """
    
    def __init__(self):
        self.config = get_config()
        self.db = DocumentDatabase(self.config.db_path)
        # We need UploadHandler for Processor init, but we won't use its queue logic here
        self.upload_handler = UploadHandler(self.config)
        self.processor = DocumentProcessor(self.config, self.upload_handler)
        
        # Ensure temp dir exists
        self.temp_dir = Path(self.config.temp_dir) / "fast_track"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    async def handle_fast_track(self, file: UploadFile) -> Dict[str, Any]:
        """
        Handle a file upload for immediate indexing.
        
        Returns:
            Dict with status, doc_id, and hash.
        """
        try:
            filename = file.filename
            safe_filename = Path(filename).name
            
            # 1. Save to temporary location
            temp_path = self.temp_dir / safe_filename
            
            # Write file
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            # 2. Compute Hash
            file_hash = self._compute_hash(temp_path)
            logger.info(f"Fast-Track: Computed hash {file_hash[:8]} for {filename}")
            
            # 3. Check DB
            # We need to query efficienty. 
            # Note: DocumentDatabase doesn't have get_by_hash yet. We use SQL directly or add method.
            existing_doc = self._get_doc_by_hash(file_hash)
            
            if existing_doc:
                logger.info(f"Fast-Track: Document already exists (ID: {existing_doc['doc_id']})")
                # Clean up temp file
                temp_path.unlink()
                return {
                    "status": "exists",
                    "doc_id": existing_doc['doc_id'],
                    "file_hash": file_hash,
                    "message": "Document déjà indexé."
                }
            
            # 4. Process & Index
            # Create metadata wrapper
            stat = temp_path.stat()
            file_meta = FileMetadata(
                path=temp_path,
                filename=safe_filename,
                extension=temp_path.suffix,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                mime_type=file.content_type or "application/octet-stream"
            )
            
            # Use Hash as ID (Content Addressable) -> "SHA256-{hash}"
            # Or use UUID but store Hash.
            # Decision: Use "HASH_{hash}" as ID to guarantee uniqueness by content.
            doc_id = f"HASH_{file_hash}"
            
            logger.info(f"Fast-Track: Processing new document {doc_id}")
            result = self.processor.process_file(
                file_path=temp_path, 
                metadata=file_meta, 
                document_id=doc_id, 
                file_hash=file_hash
            )
            
            # Clean up temp file
            temp_path.unlink()
            
            if result.status == 'completed' or result.status == 'indexing':
                 return {
                    "status": "indexed",
                    "doc_id": doc_id,
                    "file_hash": file_hash,
                    "message": "Document indexé avec succès."
                }
            else:
                 return {
                    "status": "error",
                    "message": f"Erreur lors du traitement: {result.error_message}"
                }

        except Exception as e:
            logger.error(f"Fast-Track Error: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def _get_doc_by_hash(self, file_hash: str) -> Optional[Dict]:
        """Helper to find doc by hash."""
        with self.db._connection() as conn:
            cursor = conn.cursor()
            # We added file_hash column in migration
            try:
                cursor.execute("SELECT doc_id FROM documents WHERE file_hash = ?", (file_hash,))
                row = cursor.fetchone()
                if row:
                    return {"doc_id": row[0]}
            except Exception:
                pass
        return None
