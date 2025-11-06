"""
Local filesystem path adapter.

Implements PathAdapter for local file:// URIs.
"""

import os
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import List, Optional, BinaryIO, Dict
from urllib.parse import urlparse, unquote
import time
from threading import Lock

from indexao.paths.base import PathAdapter, FileInfo, FileType
from indexao.logger import get_logger

logger = get_logger(__name__)


class LocalPathAdapter:
    """
    Path adapter for local filesystem (file:// protocol).
    
    Features:
    - Resolves file:// URIs to absolute paths
    - Caches path resolutions for performance
    - Provides rich FileInfo metadata
    - Thread-safe operations
    - Retry logic for transient errors
    
    Example:
        >>> adapter = LocalPathAdapter("file:///data/docs")
        >>> files = adapter.list_dir()
        >>> content = adapter.read_file("report.txt")
    """
    
    def __init__(
        self,
        base_uri: str,
        cache_enabled: bool = True,
        retry_count: int = 3,
        retry_delay: float = 0.1
    ):
        """
        Initialize local path adapter.
        
        Args:
            base_uri: Base URI for relative paths (e.g., "file:///data")
            cache_enabled: Enable path resolution cache
            retry_count: Number of retries for transient errors
            retry_delay: Delay between retries (seconds)
        """
        self.base_uri = base_uri
        self.base_path = self._parse_uri(base_uri)
        self.cache_enabled = cache_enabled
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        
        # Cache for path resolutions
        self._path_cache: Dict[str, Path] = {}
        self._cache_lock = Lock()
        
        logger.debug(
            f"Initialized LocalPathAdapter",
            extra={'base_uri': base_uri, 'base_path': str(self.base_path)}
        )
    
    def _parse_uri(self, uri: str) -> Path:
        """
        Parse file:// URI to Path (without resolving relative paths).
        
        Args:
            uri: URI to parse (file://..., /absolute, or relative)
        
        Returns:
            Path object (may be relative or absolute)
        """
        parsed = urlparse(uri)
        
        if parsed.scheme == 'file':
            # file:///path/to/file -> /path/to/file
            path_str = unquote(parsed.path)
            path = Path(path_str)
        elif parsed.scheme == '':
            # Plain path (no scheme)
            path = Path(unquote(uri))
        else:
            raise ValueError(f"Expected file:// URI, got {parsed.scheme}://")
        
        # Only expand ~, but don't resolve() yet (keep relative paths)
        path = path.expanduser()
        
        # If absolute, resolve it now
        if path.is_absolute():
            path = path.resolve()
        
        return path
    
    def _get_cached_path(self, uri: str) -> Path:
        """Get path from cache or resolve and cache it."""
        if not self.cache_enabled:
            return self._parse_uri(uri)
        
        with self._cache_lock:
            if uri not in self._path_cache:
                self._path_cache[uri] = self._parse_uri(uri)
                logger.trace(f"Cached path resolution", extra={'uri': uri})
            return self._path_cache[uri]
    
    def _make_absolute(self, uri: str) -> Path:
        """
        Make URI absolute relative to base_path.
        
        Args:
            uri: URI (absolute or relative)
        
        Returns:
            Absolute Path
        """
        # Parse URI to Path
        path = self._get_cached_path(uri)
        
        # If path is already absolute, return as-is
        if path.is_absolute():
            return path
        
        # Relative path: resolve relative to base_path
        absolute = self.base_path / path
        logger.trace(f"Resolved relative path", extra={
            'input': uri,
            'base_path': str(self.base_path),
            'result': str(absolute)
        })
        return absolute
    
    def _retry_operation(self, operation, *args, **kwargs):
        """
        Retry operation on transient errors.
        
        Args:
            operation: Function to call
            *args, **kwargs: Arguments to pass
        
        Returns:
            Operation result
        
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.retry_count):
            try:
                return operation(*args, **kwargs)
            except (OSError, IOError) as e:
                last_exception = e
                logger.warning(
                    f"Operation failed (attempt {attempt + 1}/{self.retry_count}): {e}",
                    extra={'operation': operation.__name__}
                )
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
        
        # All retries failed
        raise last_exception
    
    def _get_file_type(self, path: Path) -> FileType:
        """Determine file type."""
        if path.is_symlink():
            return FileType.SYMLINK
        elif path.is_dir():
            return FileType.DIRECTORY
        elif path.is_file():
            return FileType.FILE
        else:
            return FileType.UNKNOWN
    
    def _get_mime_type(self, path: Path) -> Optional[str]:
        """Guess MIME type from file extension."""
        if path.is_file():
            mime_type, _ = mimetypes.guess_type(str(path))
            return mime_type
        return None
    
    def _path_to_fileinfo(self, path: Path) -> FileInfo:
        """Convert Path to FileInfo."""
        try:
            stat = path.stat()
            
            return FileInfo(
                path=str(path),
                name=path.name,
                size=stat.st_size if path.is_file() else 0,
                mtime=datetime.fromtimestamp(stat.st_mtime),
                file_type=self._get_file_type(path),
                mime_type=self._get_mime_type(path),
                is_readable=os.access(path, os.R_OK),
                is_writable=os.access(path, os.W_OK),
                exists=True
            )
        except Exception as e:
            logger.error(f"Failed to get file info: {e}", extra={'path': str(path)})
            return FileInfo(
                path=str(path),
                name=path.name,
                size=0,
                mtime=datetime.now(),
                file_type=FileType.UNKNOWN,
                exists=False
            )
    
    def list_dir(self, uri: Optional[str] = None, recursive: bool = False) -> List[FileInfo]:
        """
        List files in directory.
        
        Args:
            uri: Directory URI (None = use base_path)
            recursive: Whether to list recursively
        
        Returns:
            List of FileInfo for each entry
        
        Raises:
            FileNotFoundError: If directory doesn't exist
            PermissionError: If directory isn't readable
        """
        dir_path = self.base_path if uri is None else self._make_absolute(uri)
        
        logger.debug(
            f"Listing directory (recursive={recursive})",
            extra={'path': str(dir_path)}
        )
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")
        
        def _list():
            results = []
            
            if recursive:
                for item in dir_path.rglob('*'):
                    results.append(self._path_to_fileinfo(item))
            else:
                for item in dir_path.iterdir():
                    results.append(self._path_to_fileinfo(item))
            
            return results
        
        with logger.timer(f"list_dir({dir_path.name})", slow_threshold_ms=500):
            return self._retry_operation(_list)
    
    def read_file(self, uri: str) -> bytes:
        """
        Read entire file into memory.
        
        Args:
            uri: File URI (relative to base_path)
        
        Returns:
            File contents as bytes
        
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file isn't readable
        """
        file_path = self._make_absolute(uri)
        
        logger.debug(f"Reading file", extra={'path': str(file_path)})
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise IsADirectoryError(f"Not a file: {file_path}")
        
        def _read():
            with open(file_path, 'rb') as f:
                return f.read()
        
        with logger.timer(f"read_file({file_path.name})", slow_threshold_ms=1000):
            return self._retry_operation(_read)
    
    def open_stream(self, uri: str, mode: str = 'rb') -> BinaryIO:
        """
        Open file as stream for reading/writing.
        
        Args:
            uri: File URI (relative to base_path)
            mode: File open mode ('rb', 'wb', etc.)
        
        Returns:
            Binary stream object
        
        Raises:
            FileNotFoundError: If file doesn't exist (read mode)
            PermissionError: If file isn't readable/writable
        """
        file_path = self._make_absolute(uri)
        
        logger.debug(f"Opening stream", extra={'path': str(file_path), 'mode': mode})
        
        if 'r' in mode and not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return self._retry_operation(open, file_path, mode)
    
    def stat(self, uri: str) -> FileInfo:
        """
        Get file/directory metadata.
        
        Args:
            uri: File/directory URI
        
        Returns:
            FileInfo with metadata
        
        Raises:
            FileNotFoundError: If path doesn't exist
        """
        path = self._make_absolute(uri)
        
        logger.trace(f"Getting file stats", extra={'path': str(path)})
        
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        return self._retry_operation(self._path_to_fileinfo, path)
    
    def exists(self, uri: str) -> bool:
        """
        Check if file/directory exists.
        
        Args:
            uri: File/directory URI
        
        Returns:
            True if exists, False otherwise
        """
        path = self._make_absolute(uri)
        logger.trace(f"Checking existence", extra={'path': str(path)})
        return path.exists()
    
    def resolve(self, uri: str) -> Path:
        """
        Resolve URI to absolute path.
        
        Args:
            uri: URI to resolve (may be relative)
        
        Returns:
            Absolute Path object
        
        Raises:
            ValueError: If URI is invalid
        """
        return self._make_absolute(uri)
