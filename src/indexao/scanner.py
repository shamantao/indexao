"""
File Scanner Module

Recursive directory traversal and file discovery.
Filters files by extension, size, and metadata extraction.

Author: Indexao Team
License: MIT
"""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Dict, Any, Iterator
from dataclasses import dataclass, field

from .logger import get_logger
from .paths import get_path_adapter, FileInfo as PathFileInfo

logger = get_logger(__name__)


@dataclass
class FileMetadata:
    """
    File metadata container.
    
    Attributes:
        path: Absolute path to file
        filename: File name only
        extension: File extension (lowercase, with dot)
        size_bytes: File size in bytes
        mime_type: MIME type string
        modified_at: Last modification timestamp
        is_hidden: Whether file is hidden (starts with .)
        relative_path: Path relative to scan root
    """
    path: Path
    filename: str
    extension: str
    size_bytes: int
    mime_type: str
    modified_at: datetime
    is_hidden: bool = False
    relative_path: Optional[Path] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'path': str(self.path),
            'filename': self.filename,
            'extension': self.extension,
            'size_bytes': self.size_bytes,
            'mime_type': self.mime_type,
            'modified_at': self.modified_at.isoformat(),
            'is_hidden': self.is_hidden,
            'relative_path': str(self.relative_path) if self.relative_path else None,
        }


class ScanError(Exception):
    """Base exception for scanner errors."""
    pass


class FileScanner:
    """
    Recursive file system scanner.
    
    Features:
    - Recursive directory traversal
    - Extension filtering (whitelist/blacklist)
    - Size filtering (min/max)
    - Hidden file filtering
    - MIME type detection
    - Metadata extraction
    
    Attributes:
        root_dir: Root directory to scan
        recursive: Enable recursive scanning
        follow_symlinks: Follow symbolic links
        include_hidden: Include hidden files (starting with .)
        allowed_extensions: Set of allowed extensions (None = all)
        excluded_extensions: Set of excluded extensions
        min_size_bytes: Minimum file size (0 = no limit)
        max_size_bytes: Maximum file size (0 = no limit)
    """
    
    def __init__(
        self,
        root_dir: Path | str,
        recursive: bool = True,
        follow_symlinks: bool = False,
        include_hidden: bool = False,
        allowed_extensions: Optional[Set[str]] = None,
        excluded_extensions: Optional[Set[str]] = None,
        min_size_bytes: int = 0,
        max_size_bytes: int = 0,
    ):
        """
        Initialize file scanner.
        
        Args:
            root_dir: Root directory to scan
            recursive: Enable recursive subdirectory scanning
            follow_symlinks: Follow symbolic links
            include_hidden: Include hidden files (starting with .)
            allowed_extensions: Whitelist of extensions (e.g., {'.txt', '.pdf'})
            excluded_extensions: Blacklist of extensions
            min_size_bytes: Minimum file size in bytes (0 = no limit)
            max_size_bytes: Maximum file size in bytes (0 = no limit)
        """
        self.root_dir = Path(root_dir).resolve()
        self.recursive = recursive
        self.follow_symlinks = follow_symlinks
        self.include_hidden = include_hidden
        self.min_size_bytes = min_size_bytes
        self.max_size_bytes = max_size_bytes
        
        # Initialize path adapter for file operations
        self.path_adapter = get_path_adapter(f"file://{self.root_dir}")
        
        # Normalize extensions (lowercase, with dot)
        self.allowed_extensions = (
            {ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
             for ext in allowed_extensions}
            if allowed_extensions else None
        )
        
        self.excluded_extensions = (
            {ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
             for ext in excluded_extensions}
            if excluded_extensions else set()
        )
        
        # Validation
        if not self.root_dir.exists():
            raise ScanError(f"Root directory does not exist: {self.root_dir}")
        
        if not self.root_dir.is_dir():
            raise ScanError(f"Root path is not a directory: {self.root_dir}")
        
        logger.info(
            f"File scanner initialized: root={self.root_dir}, "
            f"recursive={self.recursive}, "
            f"extensions={self.allowed_extensions or 'all'}"
        )
    
    def _is_hidden(self, path: Path) -> bool:
        """
        Check if file or directory is hidden.
        
        Args:
            path: Path to check
            
        Returns:
            True if path starts with dot (hidden)
        """
        return path.name.startswith('.')
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """
        Check if file should be skipped based on filters.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if file should be skipped
        """
        # Skip hidden files if not included
        if not self.include_hidden and self._is_hidden(file_path):
            logger.debug(f"Skipping hidden file: {file_path.name}")
            return True
        
        # Check extension whitelist
        extension = file_path.suffix.lower()
        if self.allowed_extensions and extension not in self.allowed_extensions:
            logger.debug(f"Skipping non-whitelisted extension: {extension}")
            return True
        
        # Check extension blacklist
        if extension in self.excluded_extensions:
            logger.debug(f"Skipping blacklisted extension: {extension}")
            return True
        
        # Check file size
        try:
            size = file_path.stat().st_size
            
            if self.min_size_bytes > 0 and size < self.min_size_bytes:
                logger.debug(f"Skipping small file: {file_path.name} ({size} bytes)")
                return True
            
            if self.max_size_bytes > 0 and size > self.max_size_bytes:
                logger.debug(f"Skipping large file: {file_path.name} ({size} bytes)")
                return True
        
        except Exception as e:
            logger.warning(f"Failed to check file size: {file_path} - {e}")
            return True
        
        return False
    
    def _extract_metadata(self, file_path: Path) -> FileMetadata:
        """
        Extract file metadata.
        
        Args:
            file_path: Path to file
            
        Returns:
            FileMetadata object
            
        Raises:
            ScanError: If metadata extraction fails
        """
        try:
            stat = file_path.stat()
            
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type is None:
                mime_type = 'application/octet-stream'
            
            # Calculate relative path
            try:
                relative_path = file_path.relative_to(self.root_dir)
            except ValueError:
                relative_path = None
            
            metadata = FileMetadata(
                path=file_path,
                filename=file_path.name,
                extension=file_path.suffix.lower(),
                size_bytes=stat.st_size,
                mime_type=mime_type,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                is_hidden=self._is_hidden(file_path),
                relative_path=relative_path,
            )
            
            logger.debug(f"Extracted metadata: {file_path.name} ({metadata.size_bytes} bytes)")
            return metadata
        
        except Exception as e:
            raise ScanError(f"Failed to extract metadata from {file_path}: {e}") from e
    
    def _scan_directory(self, directory: Path) -> Iterator[FileMetadata]:
        """
        Scan a single directory (non-recursive).
        
        Args:
            directory: Directory to scan
            
        Yields:
            FileMetadata objects for each valid file
        """
        try:
            for entry in directory.iterdir():
                # Skip hidden directories if not included
                if entry.is_dir() and not self.include_hidden and self._is_hidden(entry):
                    continue
                
                # Handle symlinks
                if entry.is_symlink():
                    if not self.follow_symlinks:
                        logger.debug(f"Skipping symlink: {entry}")
                        continue
                    
                    # Check if symlink target exists
                    try:
                        entry.stat()
                    except Exception as e:
                        logger.warning(f"Broken symlink: {entry} - {e}")
                        continue
                
                # Process files
                if entry.is_file():
                    if not self._should_skip_file(entry):
                        try:
                            metadata = self._extract_metadata(entry)
                            yield metadata
                        except ScanError as e:
                            logger.error(f"Metadata extraction failed: {e}")
                
                # Recurse into subdirectories
                elif entry.is_dir() and self.recursive:
                    yield from self._scan_directory(entry)
        
        except PermissionError as e:
            logger.warning(f"Permission denied: {directory} - {e}")
        
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
    
    def scan(self) -> List[FileMetadata]:
        """
        Scan root directory and return all matching files.
        
        Returns:
            List of FileMetadata objects
        """
        logger.info(f"Starting scan: {self.root_dir}")
        start_time = datetime.now()
        
        files = list(self._scan_directory(self.root_dir))
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Scan complete: {len(files)} files found in {duration:.2f}s "
            f"({len(files)/duration:.1f} files/s)"
        )
        
        return files
    
    def scan_iter(self) -> Iterator[FileMetadata]:
        """
        Scan root directory and yield files as found (streaming).
        
        Useful for large directories to avoid loading all files in memory.
        
        Yields:
            FileMetadata objects as files are discovered
        """
        logger.info(f"Starting streaming scan: {self.root_dir}")
        yield from self._scan_directory(self.root_dir)
    
    def count(self) -> int:
        """
        Count total number of matching files without full metadata extraction.
        
        Returns:
            Number of files that match filters
        """
        count = 0
        for _ in self._scan_directory(self.root_dir):
            count += 1
        return count
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get scan summary with statistics.
        
        Returns:
            Dictionary with scan statistics
        """
        files = self.scan()
        
        # Calculate statistics
        total_size = sum(f.size_bytes for f in files)
        extensions = {}
        mime_types = {}
        
        for file in files:
            # Count extensions
            ext = file.extension or '(no extension)'
            extensions[ext] = extensions.get(ext, 0) + 1
            
            # Count MIME types
            mime_types[file.mime_type] = mime_types.get(file.mime_type, 0) + 1
        
        return {
            'root_dir': str(self.root_dir),
            'total_files': len(files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'extensions': extensions,
            'mime_types': mime_types,
            'filters': {
                'recursive': self.recursive,
                'include_hidden': self.include_hidden,
                'allowed_extensions': list(self.allowed_extensions) if self.allowed_extensions else 'all',
                'excluded_extensions': list(self.excluded_extensions),
                'min_size_bytes': self.min_size_bytes,
                'max_size_bytes': self.max_size_bytes,
            }
        }


def scan_directory(
    root_dir: Path | str,
    **kwargs
) -> List[FileMetadata]:
    """
    Convenience function to scan a directory.
    
    Args:
        root_dir: Directory to scan
        **kwargs: Additional arguments for FileScanner
        
    Returns:
        List of FileMetadata objects
        
    Example:
        >>> files = scan_directory('/data/documents', recursive=True)
        >>> print(f"Found {len(files)} files")
    """
    scanner = FileScanner(root_dir, **kwargs)
    return scanner.scan()
