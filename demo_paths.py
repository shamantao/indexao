#!/usr/bin/env python3
"""
Demo script for Indexao path management system.

Run with:
    python demo_paths.py
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from indexao.paths import get_path_adapter, FileInfo, FileType
from indexao.logger import init_logging

def main():
    """Demonstrate path management features."""
    
    print("=" * 70)
    print("Indexao Path Management Demo")
    print("=" * 70)
    print()
    
    # Initialize logging
    init_logging(level='DEBUG', log_dir='../index/logs', console=True, file=True)
    
    # Create temporary test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create test files
        print("1. Creating test files...")
        (tmp_path / "document.txt").write_text("Sample document content")
        (tmp_path / "report.md").write_text("# Report\n\nMarkdown content")
        (tmp_path / "data.bin").write_bytes(b"\x00\x01\x02\x03\x04")
        
        # Create subdirectory with files
        subdir = tmp_path / "subfolder"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested file content")
        (subdir / "image.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")  # JPEG header
        
        print(f"   ✅ Created test structure in {tmpdir}")
        print()
        
        # Get path adapter
        print("2. Getting path adapter...")
        adapter = get_path_adapter(f"file://{tmpdir}")
        print(f"   ✅ LocalPathAdapter initialized for {tmpdir}")
        print()
        
        # List directory (non-recursive)
        print("3. Listing directory (non-recursive):")
        files = adapter.list_dir()
        for file in files:
            icon = "📁" if file.file_type == FileType.DIRECTORY else "📄"
            size_str = f"{file.size:,} bytes" if file.file_type == FileType.FILE else "directory"
            print(f"   {icon} {file.name:20} ({size_str})")
        print()
        
        # List directory (recursive)
        print("4. Listing directory (recursive):")
        files_recursive = adapter.list_dir(recursive=True)
        print(f"   Found {len(files_recursive)} total items")
        for file in files_recursive:
            if file.file_type == FileType.FILE:
                indent = "      " if "subfolder" in file.path else "   "
                print(f"{indent}📄 {file.name} ({file.size} bytes)")
        print()
        
        # Read file
        print("5. Reading file content:")
        # Use absolute path from list_dir result
        doc_path = Path(tmpdir) / "document.txt"
        content = doc_path.read_bytes()
        print(f"   document.txt: {len(content)} bytes")
        print(f"   Content: {content.decode('utf-8')}")
        print()
        
        # Get file stats
        print("6. Getting file metadata:")
        info = adapter.stat(str(doc_path))
        print(f"   Name: {info.name}")
        print(f"   Size: {info.size} bytes")
        print(f"   Type: {info.file_type.value}")
        print(f"   MIME: {info.mime_type}")
        print(f"   Modified: {info.mtime:%Y-%m-%d %H:%M:%S}")
        print(f"   Readable: {info.is_readable}")
        print()
        
        # Open stream
        print("7. Opening file stream:")
        data_path = Path(tmpdir) / "data.bin"
        with adapter.open_stream(str(data_path), "rb") as stream:
            data = stream.read()
            print(f"   Read {len(data)} bytes from stream")
            print(f"   First 5 bytes: {' '.join(f'{b:02x}' for b in data[:5])}")
        print()
        
        # Check existence
        print("8. Checking file existence:")
        print(f"   document.txt exists: {adapter.exists(str(doc_path))}")
        nonexist_path = Path(tmpdir) / "nonexistent.txt"
        print(f"   nonexistent.txt exists: {adapter.exists(str(nonexist_path))}")
        print()
        
        # Resolve paths
        print("9. Resolving paths:")
        nested_path = Path(tmpdir) / "subfolder" / "nested.txt"
        resolved = adapter.resolve(str(nested_path))
        print(f"   Input: {nested_path}")
        print(f"   Resolved: {resolved}")
        print()
        
        # Write new file via stream
        print("10. Writing new file:")
        output_path = Path(tmpdir) / "output.txt"
        with adapter.open_stream(str(output_path), "wb") as stream:
            stream.write(b"This is new content written via stream")
        
        new_content = adapter.read_file(str(output_path))
        print(f"   ✅ Written {len(new_content)} bytes to output.txt")
        print(f"   Content: {new_content.decode('utf-8')}")
        print()
        
        # Test with different URI formats
        print("11. Testing different URI formats:")
        
        # Absolute path (no scheme)
        adapter2 = get_path_adapter(tmpdir)
        files2 = adapter2.list_dir()
        print(f"   Plain path: {len(files2)} items found")
        
        # file:// URI
        adapter3 = get_path_adapter(f"file://{tmpdir}")
        files3 = adapter3.list_dir()
        print(f"   file:// URI: {len(files3)} items found")
        print()
        
        # Test caching
        print("12. Testing path resolution cache:")
        for i in range(3):
            adapter.resolve(str(doc_path))
        cache_size = len(adapter._path_cache) if hasattr(adapter, '_path_cache') else 0
        print(f"   ✅ Path resolutions cached: {cache_size}")
        print()
    
    print("=" * 70)
    print("Demo complete!")
    print("Check logs in: ../index/logs/")
    print("=" * 70)


if __name__ == '__main__':
    main()
