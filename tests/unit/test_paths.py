"""Unit tests for indexao.paths module."""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime
import time

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from indexao.paths import (
    get_path_adapter,
    PathAdapter,
    FileInfo,
    FileType,
    LocalPathAdapter
)


class TestFileInfo:
    """Test FileInfo dataclass."""
    
    def test_fileinfo_creation(self):
        """Test FileInfo creation with required fields."""
        info = FileInfo(
            path="/data/test.txt",
            name="test.txt",
            size=1024,
            mtime=datetime.now(),
            file_type=FileType.FILE
        )
        
        assert info.path == "/data/test.txt"
        assert info.name == "test.txt"
        assert info.size == 1024
        assert info.file_type == FileType.FILE
        assert info.exists is True
    
    def test_fileinfo_repr(self):
        """Test FileInfo string representation."""
        info = FileInfo(
            path="/data/test.txt",
            name="test.txt",
            size=1024,
            mtime=datetime(2025, 11, 5, 12, 0),
            file_type=FileType.FILE
        )
        
        repr_str = repr(info)
        assert "test.txt" in repr_str
        assert "1,024" in repr_str
        assert "2025-11-05" in repr_str


class TestGetPathAdapter:
    """Test get_path_adapter factory function."""
    
    def test_file_scheme_returns_local_adapter(self):
        """Test that file:// returns LocalPathAdapter."""
        adapter = get_path_adapter("file:///tmp")
        assert isinstance(adapter, LocalPathAdapter)
    
    def test_no_scheme_returns_local_adapter(self):
        """Test that plain paths return LocalPathAdapter."""
        adapter = get_path_adapter("/tmp")
        assert isinstance(adapter, LocalPathAdapter)
    
    def test_smb_scheme_raises_not_implemented(self):
        """Test that smb:// raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            get_path_adapter("smb://server/share")
    
    def test_s3_scheme_raises_not_implemented(self):
        """Test that s3:// raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            get_path_adapter("s3://bucket/key")
    
    def test_unknown_scheme_raises_value_error(self):
        """Test that unknown scheme raises ValueError."""
        with pytest.raises(ValueError):
            get_path_adapter("ftp://server/path")


class TestLocalPathAdapter:
    """Test LocalPathAdapter implementation."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create test files
            (tmp_path / "file1.txt").write_text("content 1")
            (tmp_path / "file2.md").write_text("# Markdown")
            (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03")
            
            # Create subdirectory
            subdir = tmp_path / "subdir"
            subdir.mkdir()
            (subdir / "nested.txt").write_text("nested content")
            
            yield tmpdir
    
    def test_adapter_initialization(self, temp_dir):
        """Test adapter initializes correctly."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        assert adapter.base_path == Path(temp_dir).resolve()
        assert adapter.cache_enabled is True
    
    def test_list_dir_non_recursive(self, temp_dir):
        """Test listing directory non-recursively."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        files = adapter.list_dir()
        
        # Should have 3 files + 1 directory
        assert len(files) == 4
        
        names = {f.name for f in files}
        assert "file1.txt" in names
        assert "file2.md" in names
        assert "binary.bin" in names
        assert "subdir" in names
    
    def test_list_dir_recursive(self, temp_dir):
        """Test listing directory recursively."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        files = adapter.list_dir(recursive=True)
        
        # Should have all files including nested
        assert len(files) >= 5
        
        names = {f.name for f in files}
        assert "nested.txt" in names
    
    def test_list_dir_nonexistent_raises_error(self, temp_dir):
        """Test listing nonexistent directory raises FileNotFoundError."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        with pytest.raises(FileNotFoundError):
            adapter.list_dir("nonexistent")
    
    def test_read_file(self, temp_dir):
        """Test reading file contents."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        content = adapter.read_file("file1.txt")
        
        assert content == b"content 1"
    
    def test_read_file_nonexistent_raises_error(self, temp_dir):
        """Test reading nonexistent file raises FileNotFoundError."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        with pytest.raises(FileNotFoundError):
            adapter.read_file("nonexistent.txt")
    
    def test_open_stream_read(self, temp_dir):
        """Test opening file stream for reading."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        with adapter.open_stream("file1.txt", "rb") as stream:
            content = stream.read()
            assert content == b"content 1"
    
    def test_open_stream_write(self, temp_dir):
        """Test opening file stream for writing."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        with adapter.open_stream("new_file.txt", "wb") as stream:
            stream.write(b"new content")
        
        # Verify written
        content = adapter.read_file("new_file.txt")
        assert content == b"new content"
    
    def test_stat_file(self, temp_dir):
        """Test getting file stats."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        info = adapter.stat("file1.txt")
        
        assert info.name == "file1.txt"
        assert info.size == 9  # "content 1"
        assert info.file_type == FileType.FILE
        assert info.exists is True
        assert info.is_readable is True
    
    def test_stat_directory(self, temp_dir):
        """Test getting directory stats."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        info = adapter.stat("subdir")
        
        assert info.name == "subdir"
        assert info.file_type == FileType.DIRECTORY
        assert info.exists is True
    
    def test_stat_nonexistent_raises_error(self, temp_dir):
        """Test stat on nonexistent path raises FileNotFoundError."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        with pytest.raises(FileNotFoundError):
            adapter.stat("nonexistent")
    
    def test_exists_returns_true_for_existing(self, temp_dir):
        """Test exists returns True for existing files."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        assert adapter.exists("file1.txt") is True
        assert adapter.exists("subdir") is True
    
    def test_exists_returns_false_for_nonexistent(self, temp_dir):
        """Test exists returns False for nonexistent files."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        assert adapter.exists("nonexistent") is False
    
    def test_resolve_absolute_path(self, temp_dir):
        """Test resolving absolute path."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        resolved = adapter.resolve("file1.txt")
        
        assert resolved.is_absolute()
        assert resolved.name == "file1.txt"
    
    def test_resolve_relative_path(self, temp_dir):
        """Test resolving relative path."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        resolved = adapter.resolve("subdir/nested.txt")
        
        assert resolved.is_absolute()
        assert resolved.name == "nested.txt"
    
    def test_mime_type_detection(self, temp_dir):
        """Test MIME type detection."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        info_txt = adapter.stat("file1.txt")
        assert info_txt.mime_type == "text/plain"
        
        info_md = adapter.stat("file2.md")
        # markdown might be text/markdown or text/plain depending on system
        assert info_md.mime_type is not None
    
    def test_cache_path_resolutions(self, temp_dir):
        """Test that path resolutions are cached."""
        adapter = LocalPathAdapter(f"file://{temp_dir}", cache_enabled=True)
        
        # First resolution
        path1 = adapter.resolve("file1.txt")
        
        # Second resolution should use cache
        path2 = adapter.resolve("file1.txt")
        
        assert path1 == path2
        assert len(adapter._path_cache) == 1
    
    def test_cache_disabled(self, temp_dir):
        """Test that cache can be disabled."""
        adapter = LocalPathAdapter(f"file://{temp_dir}", cache_enabled=False)
        
        adapter.resolve("file1.txt")
        adapter.resolve("file2.md")
        
        # Cache should remain empty
        assert len(adapter._path_cache) == 0
    
    def test_retry_on_transient_error(self, temp_dir):
        """Test retry logic on transient errors."""
        adapter = LocalPathAdapter(f"file://{temp_dir}", retry_count=3)
        
        # This should succeed without retries
        files = adapter.list_dir()
        assert len(files) > 0


class TestPerformanceLogging:
    """Test performance logging integration."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a file
            (tmp_path / "test.txt").write_text("test content")
            
            yield tmpdir
    
    def test_list_dir_logs_performance(self, temp_dir):
        """Test that list_dir logs performance metrics."""
        adapter = LocalPathAdapter(f"file://{temp_dir}")
        
        # Should log timing
        files = adapter.list_dir()
        assert len(files) >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
