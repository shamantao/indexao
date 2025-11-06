"""
Upload Handler Module

Handles file uploads, validation, and processing queue management.
Generates unique document IDs and moves files to processing queue.

Author: Indexao Team
License: MIT
"""

import hashlib
import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import uuid4

from .config import Config
from .logger import get_logger
from .paths import get_path_adapter, FileInfo

logger = get_logger(__name__)


class UploadError(Exception):
    """Base exception for upload-related errors."""
    pass


class FileTooLargeError(UploadError):
    """Raised when uploaded file exceeds size limit."""
    pass


class InvalidFileTypeError(UploadError):
    """Raised when uploaded file type is not allowed."""
    pass


class UploadHandler:
    """
    Manages file uploads and processing queue.
    
    Responsibilities:
    - Validate uploaded files (size, type)
    - Generate unique document IDs
    - Calculate file checksums
    - Move files to processing queue
    - Extract file metadata
    
    Attributes:
        config: Application configuration
        max_size_mb: Maximum file size in MB
        allowed_extensions: Set of allowed file extensions
        input_dir: Directory for uploaded files
        queue_dir: Directory for processing queue
    """
    
    def __init__(self, config: Config):
        """
        Initialize upload handler with configuration.
        
        Args:
            config: Application configuration object
        """
        self.config = config
        self.max_size_mb = 100  # Default 100MB limit
        
        # Allowed file extensions
        self.allowed_extensions = {
            # Text files
            '.txt', '.md', '.csv', '.json', '.xml', '.html',
            # Documents
            '.pdf', '.doc', '.docx', '.odt',
            # Images
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
            # Archives
            '.zip', '.tar', '.gz', '.bz2',
        }
        
        # Setup directories with Path Manager
        self.input_dir = Path(config.input_dir)
        self.queue_dir = self.input_dir / "_queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize path adapter for file operations
        self.path_adapter = get_path_adapter(f"file://{self.input_dir.resolve()}")
        self.queue_adapter = get_path_adapter(f"file://{self.queue_dir.resolve()}")
        
        logger.info(
            f"Upload handler initialized: "
            f"max_size={self.max_size_mb}MB, "
            f"queue={self.queue_dir}"
        )
    
    def validate_file(self, file_path: Path) -> None:
        """
        Validate uploaded file (size and extension).
        
        Args:
            file_path: Path to uploaded file
            
        Raises:
            FileTooLargeError: If file exceeds size limit
            InvalidFileTypeError: If file extension not allowed
        """
        # Check file exists
        if not file_path.exists():
            raise UploadError(f"File not found: {file_path}")
        
        # Check file size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_size_mb:
            raise FileTooLargeError(
                f"File too large: {size_mb:.2f}MB "
                f"(max: {self.max_size_mb}MB)"
            )
        
        # Check file extension
        extension = file_path.suffix.lower()
        if extension not in self.allowed_extensions:
            raise InvalidFileTypeError(
                f"File type not allowed: {extension}"
            )
        
        logger.debug(f"File validated: {file_path.name} ({size_mb:.2f}MB)")
    
    def generate_document_id(self) -> str:
        """
        Generate unique document ID.
        
        Returns:
            UUID-based document ID (format: DOC_XXXXXXXX)
        """
        doc_id = f"DOC_{uuid4().hex[:8].upper()}"
        logger.debug(f"Generated document ID: {doc_id}")
        return doc_id
    
    def calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum of file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal SHA256 checksum
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        checksum = sha256.hexdigest()
        logger.debug(f"Calculated checksum: {checksum[:16]}...")
        return checksum
    
    def detect_mime_type(self, file_path: Path) -> str:
        """
        Detect MIME type of file.
        
        Args:
            file_path: Path to file
            
        Returns:
            MIME type string (e.g., 'text/plain', 'image/jpeg')
        """
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = 'application/octet-stream'
        
        logger.debug(f"Detected MIME type: {mime_type}")
        return mime_type
    
    def extract_metadata(self, file_path: Path, doc_id: str) -> Dict[str, Any]:
        """
        Extract metadata from uploaded file.
        
        Args:
            file_path: Path to uploaded file
            doc_id: Document ID
            
        Returns:
            Dictionary with file metadata
        """
        stat = file_path.stat()
        
        metadata = {
            'document_id': doc_id,
            'filename': file_path.name,
            'extension': file_path.suffix.lower(),
            'size_bytes': stat.st_size,
            'mime_type': self.detect_mime_type(file_path),
            'checksum': self.calculate_checksum(file_path),
            'uploaded_at': datetime.now().isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'status': 'pending',
        }
        
        logger.info(
            f"Metadata extracted: {doc_id} - "
            f"{metadata['filename']} ({metadata['size_bytes']} bytes)"
        )
        
        return metadata
    
    def move_to_queue(
        self, 
        file_path: Path, 
        doc_id: str
    ) -> Path:
        """
        Move uploaded file to processing queue.
        
        Args:
            file_path: Source file path
            doc_id: Document ID
            
        Returns:
            Path to file in queue directory
        """
        # Generate queue filename: DOC_XXXXXXXX_original_name.ext
        queue_filename = f"{doc_id}_{file_path.name}"
        queue_path = self.queue_dir / queue_filename
        
        # Move file to queue
        shutil.move(str(file_path), str(queue_path))
        
        logger.info(f"File moved to queue: {queue_path.name}")
        return queue_path
    
    def handle_upload(
        self, 
        file_path: Path, 
        original_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle complete upload process.
        
        Process flow:
        1. Validate file (size, type)
        2. Generate document ID
        3. Extract metadata
        4. Move to processing queue
        5. Return upload result
        
        Args:
            file_path: Path to uploaded file (temporary location)
            original_filename: Original filename (if different from file_path)
            
        Returns:
            Dictionary with upload result and metadata
            
        Raises:
            UploadError: If upload process fails
        """
        try:
            # Use original filename if provided
            if original_filename:
                display_name = original_filename
            else:
                display_name = file_path.name
            
            logger.info(f"Processing upload: {display_name}")
            
            # Step 1: Validate file
            self.validate_file(file_path)
            
            # Step 2: Generate document ID
            doc_id = self.generate_document_id()
            
            # Step 3: Extract metadata
            metadata = self.extract_metadata(file_path, doc_id)
            metadata['original_filename'] = display_name
            
            # Step 4: Move to queue
            queue_path = self.move_to_queue(file_path, doc_id)
            metadata['queue_path'] = str(queue_path)
            
            # Success result
            result = {
                'success': True,
                'document_id': doc_id,
                'message': f'File uploaded successfully: {display_name}',
                'metadata': metadata,
            }
            
            logger.info(
                f"Upload completed: {doc_id} - {display_name}"
            )
            
            return result
            
        except UploadError as e:
            logger.error(f"Upload failed: {e}")
            raise
            
        except Exception as e:
            logger.error(f"Unexpected upload error: {e}")
            raise UploadError(f"Upload failed: {str(e)}") from e
    
    def list_queue(self) -> list[Path]:
        """
        List all files in processing queue.
        
        Returns:
            List of file paths in queue
        """
        queue_files = list(self.queue_dir.glob("DOC_*"))
        logger.debug(f"Queue contains {len(queue_files)} files")
        return queue_files
    
    def clear_queue(self) -> int:
        """
        Clear all files from processing queue.
        
        WARNING: This deletes all pending files!
        
        Returns:
            Number of files deleted
        """
        queue_files = self.list_queue()
        count = 0
        
        for file_path in queue_files:
            try:
                file_path.unlink()
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
        
        logger.warning(f"Queue cleared: {count} files deleted")
        return count
