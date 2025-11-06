"""
Base protocol and dataclasses for path adapters.

Defines the interface that all path adapters must implement.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, List, Optional, BinaryIO, runtime_checkable
from enum import Enum


class FileType(Enum):
    """Type of file system entry."""
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    UNKNOWN = "unknown"


@dataclass
class FileInfo:
    """
    Rich metadata about a file or directory.
    
    Attributes:
        path: Full path (absolute or URI)
        name: File/directory name
        size: Size in bytes (0 for directories)
        mtime: Last modification time
        file_type: Type of entry (file, directory, symlink)
        mime_type: MIME type (if determinable)
        is_readable: Whether file is readable
        is_writable: Whether file is writable
        exists: Whether file exists
    """
    path: str
    name: str
    size: int
    mtime: datetime
    file_type: FileType
    mime_type: Optional[str] = None
    is_readable: bool = True
    is_writable: bool = False
    exists: bool = True
    
    def __repr__(self) -> str:
        """String representation."""
        type_symbol = {
            FileType.FILE: "📄",
            FileType.DIRECTORY: "📁",
            FileType.SYMLINK: "🔗",
            FileType.UNKNOWN: "❓"
        }.get(self.file_type, "")
        
        size_str = f"{self.size:,}" if self.file_type == FileType.FILE else "-"
        return (
            f"{type_symbol} {self.name} "
            f"({size_str} bytes, {self.mtime:%Y-%m-%d %H:%M})"
        )


@runtime_checkable
class PathAdapter(Protocol):
    """
    Protocol for path adapters.
    
    All path adapters must implement this interface to provide
    uniform access to files across different protocols.
    """
    
    def list_dir(self, uri: Optional[str] = None, recursive: bool = False) -> List[FileInfo]:
        """
        List files in directory.
        
        Args:
            uri: Directory URI (None = use adapter's base URI)
            recursive: Whether to list recursively
        
        Returns:
            List of FileInfo for each entry
        
        Raises:
            FileNotFoundError: If directory doesn't exist
            PermissionError: If directory isn't readable
        """
        ...
    
    def read_file(self, uri: str) -> bytes:
        """
        Read entire file into memory.
        
        Args:
            uri: File URI (relative to adapter's base)
        
        Returns:
            File contents as bytes
        
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file isn't readable
        """
        ...
    
    def open_stream(self, uri: str, mode: str = 'rb') -> BinaryIO:
        """
        Open file as stream for reading/writing.
        
        Args:
            uri: File URI (relative to adapter's base)
            mode: File open mode ('rb', 'wb', etc.)
        
        Returns:
            Binary stream object
        
        Raises:
            FileNotFoundError: If file doesn't exist (read mode)
            PermissionError: If file isn't readable/writable
        """
        ...
    
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
        ...
    
    def exists(self, uri: str) -> bool:
        """
        Check if file/directory exists.
        
        Args:
            uri: File/directory URI
        
        Returns:
            True if exists, False otherwise
        """
        ...
    
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
        ...
