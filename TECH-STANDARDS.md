# Technical Standards & Best Practices

> **For AI**: Read this document when implementing new features requiring detailed technical patterns.  
> **For Developers**: Reference guide for architecture patterns, code standards, and implementation examples.

## Table of Contents

1. [Logger System](#1-logger-system)
2. [Path Manager](#2-path-manager)
3. [Import Patterns](#3-import-patterns)
4. [Code Organization](#4-code-organization)
5. [Testing Standards](#5-testing-standards)

---

## 1. Logger System

### 1.1 Basic Usage

```python
from indexao.logger import get_logger

logger = get_logger(__name__)

# Standard logging
logger.info("Processing file", extra={"filename": "doc.pdf"})
logger.debug("Debug details", extra={"count": 42})
logger.error("Error occurred", extra={"error": str(e)})
logger.warning("Warning message")
logger.trace("Detailed trace info")  # Very verbose, only in trace mode
```

### 1.2 Performance Timing

```python
# Automatic timing with context manager
with logger.timer("database_query"):
    results = db.query(...)

# Manual timing
logger.timer_start("complex_operation")
# ... operation ...
logger.timer_end("complex_operation")
```

### 1.3 Metrics

```python
# Track metrics
logger.metric("files_processed", 150)
logger.metric("processing_speed", 45.2, unit="files/sec")
logger.metric("error_rate", 0.02, unit="percent")
```

### 1.4 Configuration

Logger is configured via `config.toml`:

```toml
[logging]
level = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
format = "json"  # or "text"
output = "file"  # or "console" or "both"

[logging.files]
path = "logs"
max_size_mb = 10
backup_count = 5
```

Environment variables override TOML:

- `INDEXAO_LOG_LEVEL=DEBUG`
- `INDEXAO_LOG_FORMAT=json`

---

## 2. Path Manager

### 2.1 Basic File Operations

```python
from indexao.paths import get_path_adapter, FileInfo, FileType

# Get adapter for local filesystem
adapter = get_path_adapter("file:///data/documents")

# List directory
files = adapter.list_dir(recursive=False)
for file_info in files:
    print(f"{file_info.name}: {file_info.size} bytes")

# Read file
content = adapter.read_file("document.txt")

# Write file
adapter.write_file("output.txt", "content here")

# Check existence
if adapter.exists("config.json"):
    config = adapter.read_file("config.json")
```

### 2.2 Streaming Large Files

```python
# Stream large file without loading all in memory
with adapter.open_stream("large_video.mp4") as stream:
    for chunk in stream:
        process_chunk(chunk)
```

### 2.3 File Metadata

```python
# Get rich metadata
file_info: FileInfo = adapter.get_info("document.pdf")

print(f"Name: {file_info.name}")
print(f"Size: {file_info.size}")
print(f"Type: {file_info.file_type}")  # FILE, DIRECTORY, SYMLINK
print(f"MIME: {file_info.mime_type}")
print(f"Modified: {file_info.modified_at}")
print(f"Permissions: {file_info.permissions}")
```

### 2.4 Multi-Protocol Support

```python
# Local filesystem
local_adapter = get_path_adapter("file:///data/docs")

# SMB network share (future)
smb_adapter = get_path_adapter("smb://server/share/folder")

# S3 bucket (future)
s3_adapter = get_path_adapter("s3://bucket-name/prefix")

# All adapters implement same PathAdapter protocol
# → Code works identically regardless of protocol
```

### 2.5 When to Use What

**Use Path Manager** ✅:

- Reading/writing files
- Listing directories
- Getting file metadata
- Any I/O operation

**Use pathlib.Path** ✅:

- Path manipulation only (`.parent`, `.joinpath()`, `.stem`)
- Constructing paths without I/O
- Temporary/internal paths

**Example**:

```python
from pathlib import Path
from indexao.paths import get_path_adapter

# ✅ Path manipulation
config_dir = Path("config")
config_file = config_dir / "settings.toml"

# ✅ I/O operations via adapter
adapter = get_path_adapter(f"file://{config_file}")
content = adapter.read_file(config_file.name)
```

---

## 3. Import Patterns

### 3.1 Standard Module Template

```python
"""
Module description here.

This module provides functionality for...

Author: Indexao Team
License: MIT
"""

# Standard library imports
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Third-party imports
import httpx
from pydantic import BaseModel

# Indexao core imports (ALWAYS use these)
from indexao.config import Config
from indexao.logger import get_logger
from indexao.paths import get_path_adapter, FileInfo

# Indexao local imports
from .models import Document
from .utils import validate_input

# Initialize logger (REQUIRED)
logger = get_logger(__name__)
```

### 3.2 Import Order

1. **Standard library** (datetime, pathlib, typing, etc.)
2. **Third-party** (httpx, pydantic, sqlalchemy, etc.)
3. **Indexao core** (config, logger, paths)
4. **Local module** (relative imports)

Separated by blank lines, sorted alphabetically within each group.

---

## 4. Code Organization

### 4.1 File Size Limits

- **Maximum**: 500 lines per file
- **Ideal**: 200-300 lines per file
- **Action**: Split into multiple files if exceeding limit

### 4.2 Module Structure

```
src/indexao/feature/
├── __init__.py          # Public API exports
├── models.py            # Data models (Pydantic, SQLAlchemy)
├── service.py           # Business logic
├── routes.py            # API endpoints (FastAPI)
├── utils.py             # Helper functions
└── tests/
    ├── test_models.py
    ├── test_service.py
    └── test_routes.py
```

### 4.3 Naming Conventions

- **Files/Directories**: `lowercase_with_underscores`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

### 4.4 Comments

- **Language**: English only
- **Style**: Clear, concise, explain "why" not "what"
- **Docstrings**: Required for all public functions/classes

```python
def process_document(file_path: Path, lang: str = "en") -> Document:
    """
    Process a document and extract metadata.

    Args:
        file_path: Path to document file
        lang: Language code for OCR (default: "en")

    Returns:
        Document object with extracted metadata

    Raises:
        FileNotFoundError: If file doesn't exist
        ProcessingError: If document processing fails
    """
    # Implementation note: Using PaddleOCR for better Chinese support
    # compared to Tesseract (benchmark: 95% vs 87% accuracy)
    ...
```

---

## 5. Testing Standards

### 5.1 Test Structure

```python
"""
Tests for document processing module.
"""

import pytest
from pathlib import Path
from indexao.documents import process_document
from indexao.paths import get_path_adapter

class TestDocumentProcessing:
    """Test document processing functionality."""

    def test_process_pdf_success(self, tmp_path):
        """Test successful PDF processing."""
        # Arrange
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")

        # Act
        result = process_document(test_file)

        # Assert
        assert result.filename == "test.pdf"
        assert result.mime_type == "application/pdf"

    def test_process_missing_file(self):
        """Test processing non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            process_document(Path("missing.pdf"))
```

### 5.2 Test Coverage

- **Minimum**: 80% code coverage
- **Target**: 90% for core modules
- **Critical paths**: 100% (auth, payment, data integrity)

### 5.3 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/indexao --cov-report=html

# Run specific module
pytest tests/unit/test_scanner.py

# Run with verbose output
pytest -v
```

---

## 6. Performance Guidelines

### 6.1 Database Queries

```python
# ❌ Bad: N+1 queries
for doc in documents:
    doc.author = db.query(User).filter_by(id=doc.author_id).first()

# ✅ Good: Single query with join
documents = db.query(Document).options(joinedload(Document.author)).all()
```

### 6.2 File I/O

```python
# ❌ Bad: Load entire file in memory
content = open("large_file.txt").read()

# ✅ Good: Stream file
with adapter.open_stream("large_file.txt") as stream:
    for line in stream:
        process_line(line)
```

### 6.3 Caching

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_config(key: str) -> str:
    """Cached config lookup."""
    return config.get(key)
```

---

## 7. Error Handling

### 7.1 Custom Exceptions

```python
class IndexaoError(Exception):
    """Base exception for Indexao."""
    pass

class ScanError(IndexaoError):
    """Raised when file scanning fails."""
    pass

class ProcessingError(IndexaoError):
    """Raised when document processing fails."""
    pass
```

### 7.2 Exception Handling

```python
try:
    result = process_document(file_path)
except FileNotFoundError as e:
    logger.error("File not found", extra={"path": str(file_path)})
    raise ProcessingError(f"Cannot process missing file: {file_path}") from e
except Exception as e:
    logger.error("Unexpected error", extra={"error": str(e)})
    raise
```

---

## 8. API Design

### 8.1 REST Endpoints

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/documents")

class DocumentCreate(BaseModel):
    filename: str
    content: str

@router.post("/", response_model=DocumentResponse)
async def create_document(doc: DocumentCreate):
    """
    Create a new document.

    Returns:
        Created document with ID
    """
    try:
        result = service.create(doc)
        logger.info("Document created", extra={"id": result.id})
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 8.2 Response Models

```python
class DocumentResponse(BaseModel):
    id: int
    filename: str
    created_at: datetime

    class Config:
        from_attributes = True  # For SQLAlchemy models
```

---

## 9. Git Workflow

### 9.1 Branch Naming

- `feature/scanner-smb-support`
- `fix/memory-leak-large-files`
- `docs/update-api-guide`

### 9.2 Commit Messages

```
feat(scanner): add SMB protocol support

- Implement SmbPathAdapter with authentication
- Add retry logic for network failures
- Update tests with SMB fixtures

Closes #42
```

Format: `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

---

## 10. Deployment

### 10.1 Environment Variables

```bash
# Required
INDEXAO_CONFIG=/path/to/config.toml
INDEXAO_DB_URL=sqlite:///data/indexao.db

# Optional
INDEXAO_LOG_LEVEL=INFO
INDEXAO_DEBUG=false
```

### 10.2 Docker Build

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
CMD ["uvicorn", "indexao.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

**Last Updated**: 2025-11-06  
**Version**: 0.2.0-dev
