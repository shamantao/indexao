# Technical Architecture - Indexao

**Version**: 0.3.0-dev  
**Last Updated**: 2025-11-07  
**Sprint**: Sprint 2 Complete ✅ (Plugin Manager + Dynamic Loading + UI)  
**Architecture Pattern**: Hybrid Rust/Python (Polars Pattern)

---

## Current Status

**Sprint 0-2 Complete** (2025-11-05 → 2025-11-07)

- ✅ Foundation: Config, logging, web UI, API management
- ✅ Processing Pipeline: Upload → Scanner → Processor (5 stages)
- ✅ Mock Adapters: OCR, Translator, Search (in-memory)
- ✅ Database: SQLite with document model
- ✅ Web UI: Upload (progress), Documents (stats/list), Search (highlighting), Config (plugin switcher)
- ✅ **Plugin Manager**: Dynamic loading, auto-discovery, protocol validation, hot-swap
- ✅ **REST API**: 7 endpoints for plugin management
- ✅ **UI Switcher**: Runtime adapter switching without restart

**Next Steps**

- Sprint 3: Real Adapters (Tesseract, Argos, Meilisearch) → **MVP TESTABLE**

---

## Table of Contents

1. [Technology Choices](#technology-choices)
2. [Hybrid Architecture](#hybrid-architecture)
3. [Module Responsibilities](#module-responsibilities)
4. [Plugin API Specifications](#plugin-api-specifications)
5. [Data Models](#data-models)
6. [Path/Routes Management](#pathroutes-management)
7. [Build & Distribution](#build--distribution)

---

## Technology Choices

### Primary Language: **Python 3.10+** with **Rust Core**

**Rationale**:

- **Python**: Rich ML/AI ecosystem (OCR, translation, NLP libraries), rapid prototyping, user-friendly
- **Rust**: High performance for I/O-bound operations (file scanning, indexing), memory safety, single binary distribution
- **Best of both worlds**: Python for flexibility + Rust for speed

### Core Stack

| Component                 | Technology                          | Justification                                 | Fallback                                |
| ------------------------- | ----------------------------------- | --------------------------------------------- | --------------------------------------- |
| **Hybrid Bridge**         | PyO3 + maturin                      | Zero-copy via Arrow, proven pattern (Polars)  | Pure Python (slower)                    |
| **Search Engine**         | Meilisearch                         | Multilingual, typo-tolerant, 40MB Rust binary | Tantivy (Rust lib) or Simple SQLite FTS |
| **OCR (default)**         | Tesseract                           | Mature, 100+ languages, local                 | Chandra-OCR (VLM), Cloud APIs           |
| **Translation (default)** | Argostranslate                      | Offline, free, neural MT                      | Google Translate API, LibreTranslate    |
| **Data Format**           | Apache Arrow                        | Zero-copy Python ↔ Rust, columnar format      | JSON (slower)                           |
| **Config**                | TOML                                | Simple, human-readable, standard              | YAML or JSON                            |
| **Logging**               | Python `logging` + `tracing` (Rust) | Standard, configurable                        | Simple file logs                        |

---

## Hybrid Architecture

### Polars Pattern (Rust Core + Python Bindings)

```
┌─────────────────────────────────────────────────────────┐
│               User Interface (CLI/Web)                  │
│                   Python Layer                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │   OCR    │  │Translator│  │ Exporter │  Plugins   │
│  │ Adapters │  │ Adapters │  │ Adapters │  (Python)  │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                                         │
├─────────────────────────────────────────────────────────┤
│              PyO3 Bridge (Arrow Format)                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Scanner │  │ Indexer  │  │  Search  │  Rust Core │
│  │  (I/O)   │  │ (Engine) │  │ (Query)  │  (Fast)    │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Smart Task Dispatcher

**Automatic routing** based on task characteristics:

| Task Type         | Execution  | Reason                         |
| ----------------- | ---------- | ------------------------------ |
| File scanning     | **Rust**   | I/O-bound, needs speed         |
| Indexing          | **Rust**   | CPU + I/O intensive            |
| Search queries    | **Rust**   | Performance-critical           |
| OCR processing    | **Python** | ML models, plugin ecosystem    |
| Translation       | **Python** | Neural models, APIs            |
| Export formatting | **Python** | String manipulation, templates |

```python
# Example: Transparent smart dispatching
from indexao import scan_files

# Automatically uses Rust if available, falls back to Python
results = scan_files("/path/to/folder")  # Rust core
# Returns Arrow DataFrame, usable in Python
```

---

## Module Responsibilities

### Directory Structure

```
indexao/
├── README.md                    # User documentation
├── arch-tech.md                 # This file
├── changelog.md                 # Version history
├── pyproject.toml              # Python package config
├── Cargo.toml                  # Rust workspace config (if hybrid)
├── Makefile                    # Dev commands
├── config.example.toml         # Sample configuration
├── .gitignore
│
├── src/
│   ├── indexao/                # Python package root
│   │   ├── __init__.py         # Package entry, version
│   │   ├── cli.py              # CLI interface (Click)
│   │   ├── config.py           # Configuration loader
│   │   ├── logger.py           # Logging setup
│   │   │
│   │   ├── paths/              # Path/Routes abstraction
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # PathAdapter interface
│   │   │   ├── local.py        # file:// handler
│   │   │   ├── smb.py          # smb:// handler (optional)
│   │   │   └── s3.py           # s3:// handler (optional)
│   │   │
│   │   ├── adapters/           # Plugin adapters
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Adapter base classes
│   │   │   │
│   │   │   ├── ocr/            # OCR plugins
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py     # OCRAdapter interface
│   │   │   │   ├── tesseract.py
│   │   │   │   ├── chandra.py
│   │   │   │   └── mock.py     # For testing
│   │   │   │
│   │   │   ├── translator/     # Translation plugins
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py     # TranslatorAdapter interface
│   │   │   │   ├── argos.py
│   │   │   │   ├── google.py   # API-based
│   │   │   │   └── mock.py
│   │   │   │
│   │   │   └── search/         # Search backend plugins
│   │   │       ├── __init__.py
│   │   │       ├── base.py     # SearchAdapter interface
│   │   │       ├── meilisearch.py
│   │   │       ├── tantivy.py  # Pure Rust option
│   │   │       └── simple.py   # SQLite FTS fallback
│   │   │
│   │   ├── indexer/            # Indexing logic
│   │   │   ├── __init__.py
│   │   │   ├── scanner.py      # File tree traversal (calls Rust or Python)
│   │   │   ├── detector.py     # File type detection
│   │   │   └── extractor.py    # Content extraction orchestrator
│   │   │
│   │   ├── search/             # Search logic
│   │   │   ├── __init__.py
│   │   │   ├── query.py        # Query parser & builder
│   │   │   └── multilingual.py # Language mapping & synonyms
│   │   │
│   │   ├── viewer/             # File viewing & translation
│   │   │   ├── __init__.py
│   │   │   ├── renderer.py     # Translated file rendering
│   │   │   └── formatter.py    # Structure preservation
│   │   │
│   │   └── exporter/           # Export functionality
│   │       ├── __init__.py
│   │       ├── json_exporter.py
│   │       └── markdown_exporter.py
│   │
│   └── indexao_core/           # Rust crate (optional, for hybrid build)
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs          # PyO3 bindings
│           ├── scanner.rs      # Fast file scanning
│           ├── indexer.rs      # Indexing engine
│           └── search.rs       # Query execution
│
├── tests/
│   ├── unit/                   # Unit tests per module
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end user scenarios
│       ├── test_user_story_1.py
│       ├── test_user_story_2.py
│       └── test_user_story_3.py
│
├── demo_data/                  # Small demo dataset
│   ├── sport.txt
│   ├── img1.jpg
│   └── binary.bin
│
├── ci/
│   ├── lint.sh
│   ├── test.sh
│   └── build.sh
│
└── mkdoc/                      # Sprint tracking (not in Git)
    ├── 20251105_backlog.md
    └── sprint_notes/
```

### File Size Constraint

**All source files ≤ 300-400 lines**. If a module exceeds this:

- Split into submodules (e.g., `ocr/tesseract_preprocessing.py`, `ocr/tesseract_postprocessing.py`)
- Extract common utilities to `utils/` folder
- Use composition to delegate responsibilities

---

## Plugin API Specifications

### 1. OCR Adapter

**Interface**: `indexao.adapters.ocr.base.OCRAdapter`

```python
from typing import Protocol, IO
from dataclasses import dataclass

@dataclass
class OCRResult:
    """OCR extraction result"""
    text: str
    confidence: float
    language: str
    metadata: dict  # EXIF, bbox coordinates, etc.

class OCRAdapter(Protocol):
    """OCR plugin interface"""

    def extract_text(self, stream: IO[bytes], config: dict) -> OCRResult:
        """
        Extract text from image or PDF stream.

        Args:
            stream: Binary file stream
            config: Plugin-specific configuration

        Returns:
            OCRResult with text and metadata
        """
        ...

    def supported_formats(self) -> list[str]:
        """Return list of supported MIME types"""
        ...
```

**Example Implementation**:

```python
# indexao/adapters/ocr/tesseract.py
import pytesseract
from PIL import Image

class TesseractAdapter:
    def extract_text(self, stream, config):
        img = Image.open(stream)
        lang = config.get('lang', 'eng')

        data = pytesseract.image_to_data(img, lang=lang, output_type='dict')
        text = ' '.join(data['text'])
        confidence = sum(data['conf']) / len(data['conf'])

        return OCRResult(
            text=text,
            confidence=confidence,
            language=lang,
            metadata={'bbox': data['left'], 'top': data['top']}
        )

    def supported_formats(self):
        return ['image/png', 'image/jpeg', 'image/tiff']
```

**Plugin Registration**:

```toml
# config.toml
[plugins.ocr.tesseract]
enabled = true
lang = "eng+fra+chi_tra"
path = "/usr/bin/tesseract"

[plugins.ocr.chandra]
enabled = false
model_path = "../_sources/chandra-ocr/model.bin"
device = "cpu"
```

### 2. Translator Adapter

**Interface**: `indexao.adapters.translator.base.TranslatorAdapter`

```python
from typing import Protocol

class TranslatorAdapter(Protocol):
    """Translation plugin interface"""

    def translate(self, text: str, src_lang: str, target_lang: str) -> str:
        """
        Translate text between languages.

        Args:
            text: Source text
            src_lang: Source language code (ISO 639-1)
            target_lang: Target language code

        Returns:
            Translated text
        """
        ...

    def supported_languages(self) -> list[str]:
        """Return list of supported language codes"""
        ...
```

### 3. Search Adapter

**Interface**: `indexao.adapters.search.base.SearchAdapter`

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class SearchResult:
    """Single search result"""
    path: str
    score: float
    snippet: str
    translations: dict[str, str]  # {lang: translated_snippet}
    metadata: dict

class SearchAdapter(Protocol):
    """Search backend plugin interface"""

    def index_document(self, doc: dict) -> str:
        """Index a document, return document ID"""
        ...

    def search(self, query: str, languages: list[str], filters: dict) -> list[SearchResult]:
        """
        Execute search query.

        Args:
            query: Search query string
            languages: Target languages for multilingual search
            filters: Additional filters (file type, date range, etc.)

        Returns:
            List of SearchResult objects
        """
        ...

    def delete_document(self, doc_id: str) -> bool:
        """Remove document from index"""
        ...
```

### 4. Exporter

**Interface**: `indexao.exporter.base.Exporter`

```python
from typing import Protocol

class Exporter(Protocol):
    """Export plugin interface"""

    def export_to_json(self, doc: dict, translations: dict[str, str]) -> str:
        """Export document with translations to JSON string"""
        ...

    def export_to_markdown(self, doc: dict, translations: dict[str, str]) -> str:
        """Export document with translations to Markdown string"""
        ...
```

---

## Data Models

### Document Model

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Document:
    """Indexed document representation"""
    id: str                      # SHA256 hash of path + mtime
    path: str                    # Absolute path or URI
    name: str                    # Filename
    type: str                    # MIME type
    size: int                    # Bytes
    modified: datetime           # Last modification time
    content: str                 # Extracted text content
    language: str                # Detected language (ISO 639-1)
    metadata: dict               # EXIF, XMP, custom fields
    translations: dict[str, str] # {lang: translated_content}
    indexed_at: datetime         # Indexing timestamp
```

### Index Schema (Meilisearch)

```json
{
  "uid": "documents",
  "primaryKey": "id",
  "searchableAttributes": ["name", "content", "translations.*", "metadata.*"],
  "filterableAttributes": ["type", "language", "indexed_at"],
  "sortableAttributes": ["modified", "indexed_at", "size"]
}
```

---

## Path/Routes Management

**Central module**: `indexao.paths`

### PathAdapter Interface

```python
from typing import Protocol, Iterator
from pathlib import Path

class PathAdapter(Protocol):
    """Path scheme handler interface"""

    def list_dir(self, path: str) -> Iterator[str]:
        """List directory contents, yield paths"""
        ...

    def read_file(self, path: str) -> bytes:
        """Read file contents"""
        ...

    def stat(self, path: str) -> dict:
        """Get file metadata (size, mtime, etc.)"""
        ...

    def open_stream(self, path: str) -> IO[bytes]:
        """Open file as binary stream"""
        ...
```

### Usage Example

```python
from indexao.paths import get_adapter

# Automatically selects adapter based on scheme
adapter = get_adapter("file:///home/user/docs")
for file in adapter.list_dir("file:///home/user/docs"):
    content = adapter.read_file(file)

# Works with network paths
adapter = get_adapter("smb://server/share/folder")
for file in adapter.list_dir("smb://server/share/folder"):
    stats = adapter.stat(file)
```

---

## Build & Distribution

### Pure Python Build

```bash
# Development
pip install -e .

# Production package
python -m build
pip install dist/indexao-*.whl
```

### Hybrid Rust/Python Build (Polars Pattern)

```bash
# Install build tools
pip install maturin

# Development (debug)
maturin develop

# Production (optimized)
maturin develop --release

# Build distributable wheel
maturin build --release
```

### Distribution Strategy

| Platform        | Distribution             | Size                 | Install Time |
| --------------- | ------------------------ | -------------------- | ------------ |
| **Python-only** | PyPI wheel               | ~200 MB (with deps)  | 30-60 min    |
| **Hybrid**      | PyPI wheel + Rust binary | ~15 MB binary + deps | 3-5 min      |
| **Standalone**  | Single binary (future)   | ~50 MB               | 30 sec       |

**Hybrid benefits**:

- ⚡ 10x faster file scanning (Rust)
- 📦 Smaller distribution size
- 🔌 Still supports Python plugins
- 🚀 Gradual migration path (start Python, optimize with Rust)

---

## Performance Targets (MVP)

| Operation      | Target   | Rust Core           | Python-only |
| -------------- | -------- | ------------------- | ----------- |
| Scan 10k files | < 2 sec  | ✅ 0.5 sec          | ⚠️ 5 sec    |
| Index 1k docs  | < 5 sec  | ✅ 2 sec            | ⚠️ 15 sec   |
| Search query   | < 100 ms | ✅ 50 ms            | ✅ 80 ms    |
| OCR image      | ~1 sec   | N/A (Python plugin) | 1 sec       |
| Translate text | ~2 sec   | N/A (Python plugin) | 2 sec       |

---

## Logging Strategy

```python
# indexao/logger.py
import logging
import os

LOG_LEVEL = os.getenv('INDEXAO_LOG_LEVEL', 'INFO')

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f'indexao.{name}')
```

**Usage**:

```python
from indexao.logger import get_logger

logger = get_logger('scanner')
logger.info("Scanning directory: %s", path)
logger.debug("Found %d files", count)
```

**Configuration**:

```bash
# Set via environment variable
export INDEXAO_LOG_LEVEL=DEBUG
indexao scan /path

# Or via config file
[logging]
level = "DEBUG"
file = "../index/logs/indexao.log"
```

---

## Testing Strategy

### Test Pyramid

```
      ┌────────────┐
      │    E2E     │  3 user scenarios (slow, high-value)
      │  (pytest)  │
      └────────────┘
     ┌──────────────┐
     │ Integration  │  Plugin interactions (medium speed)
     │  (pytest)    │
     └──────────────┘
    ┌────────────────┐
    │     Unit       │  Module logic (fast, many tests)
    │   (pytest)     │
    └────────────────┘
```

### User-Centric E2E Tests

**Test 1**: Multilingual search

```python
# tests/e2e/test_user_story_1.py
def test_user_indexes_and_searches_multilingual(demo_folder):
    """
    User indexes a demo folder containing:
    - sport.txt (contains "ball")
    - img1.jpg (has "球" in OCR text)
    - binary.bin

    User searches for "ballon" and sees all files referenced
    with translations and working view/export.
    """
    # Index demo folder
    result = run_cli(['index', demo_folder])
    assert result.exit_code == 0

    # Search for "ballon"
    result = run_cli(['search', 'ballon'])
    assert 'sport.txt' in result.output
    assert 'img1.jpg' in result.output
    assert 'ball' in result.output  # English translation
    assert '球' in result.output     # Chinese translation

    # Export one result
    result = run_cli(['export', 'sport.txt', '--format', 'json', '--lang', 'fr'])
    data = json.loads(result.output)
    assert 'translations' in data
    assert 'fr' in data['translations']
```

---

## Plugin Replacement Example

**Scenario**: Replace Tesseract with Chandra-OCR

```python
# config.toml BEFORE
[plugins.ocr]
default = "tesseract"

# config.toml AFTER
[plugins.ocr]
default = "chandra"

[plugins.ocr.chandra]
model_path = "../_sources/chandra-ocr/model.bin"
device = "cpu"
```

**No code changes required** - adapter pattern handles the swap!

```python
# indexao/adapters/ocr/__init__.py
from .base import OCRAdapter
from .tesseract import TesseractAdapter
from .chandra import ChandraAdapter

ADAPTERS = {
    'tesseract': TesseractAdapter,
    'chandra': ChandraAdapter,
}

def get_ocr_adapter(name: str, config: dict) -> OCRAdapter:
    """Factory function - returns configured adapter"""
    adapter_class = ADAPTERS.get(name)
    if not adapter_class:
        raise ValueError(f"Unknown OCR adapter: {name}")
    return adapter_class(config)
```

---

## Roadmap

### Sprint 0 (Setup - 2 weeks)

- ✅ Architecture documentation
- ✅ Repository structure
- ⏳ Base adapter interfaces
- ⏳ Path management module
- ⏳ Logging & config
- ⏳ CI setup

### Sprint 1 (MVP Core - 2 weeks)

- ⏳ File scanner (Python, then Rust)
- ⏳ Tesseract OCR adapter
- ⏳ Argostranslate adapter
- ⏳ Meilisearch backend
- ⏳ Basic CLI
- ⏳ E2E test 1

### Sprint 2 (Polish - 2 weeks)

- ⏳ Export functionality
- ⏳ Viewer/translator
- ⏳ E2E tests 2-3
- ⏳ Documentation
- ⏳ Demo data
- ⏳ PyPI package

---

**Status**: 🚧 Sprint 0 in progress  
**Next Review**: End of Sprint 0 (2025-11-19)
