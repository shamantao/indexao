"""
Path management module for Indexao.

Provides universal path adapters for accessing files via different protocols:
- file:// - Local filesystem
- smb:// - Windows/Samba network shares (future)
- s3:// - AWS S3 buckets (future)

Usage:
    from indexao.paths import get_path_adapter, FileInfo
    
    # Get adapter for URI
    adapter = get_path_adapter("file:///data/docs")
    
    # List directory
    files = adapter.list_dir()
    for file in files:
        print(f"{file.name}: {file.size} bytes")
    
    # Read file
    content = adapter.read_file("document.txt")
    
    # Stream large file
    with adapter.open_stream("large_video.mp4") as stream:
        process_chunks(stream)
"""

from typing import Optional
from urllib.parse import urlparse

from indexao.paths.base import PathAdapter, FileInfo, FileType
from indexao.paths.local import LocalPathAdapter
from indexao.logger import get_logger

logger = get_logger(__name__)


def get_path_adapter(uri: str) -> PathAdapter:
    """
    Get appropriate path adapter for given URI.
    
    Args:
        uri: URI to access (file://, smb://, s3://, etc.)
    
    Returns:
        PathAdapter instance for the URI scheme
    
    Raises:
        ValueError: If URI scheme is not supported
    
    Example:
        >>> adapter = get_path_adapter("file:///data/docs")
        >>> files = adapter.list_dir()
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower() if parsed.scheme else 'file'
    
    logger.debug(f"Getting path adapter for scheme: {scheme}", extra={'uri': uri})
    
    if scheme == 'file' or scheme == '':
        return LocalPathAdapter(uri)
    elif scheme == 'smb':
        logger.error(f"SMB protocol not yet implemented", extra={'uri': uri})
        raise NotImplementedError("SMB protocol support coming in future release")
    elif scheme == 's3':
        logger.error(f"S3 protocol not yet implemented", extra={'uri': uri})
        raise NotImplementedError("S3 protocol support coming in future release")
    else:
        logger.error(f"Unsupported URI scheme: {scheme}", extra={'uri': uri})
        raise ValueError(f"Unsupported URI scheme: {scheme}")


__all__ = [
    'PathAdapter',
    'FileInfo',
    'FileType',
    'LocalPathAdapter',
    'get_path_adapter',
]
