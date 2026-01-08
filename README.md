# Indexao

**Universal multilingual search, indexing, and translation tool**

Indexao is a modular, user-centric tool to index arbitrary file trees and enable unified multilingual search, full translated visualization (keeping structure), and export to JSON/Markdown.

**Current Status**: Sprint 3 Complete ✅ - Configuration UI Overhaul & Volume Management
**Version**: 0.4.0
**Next**: Sprint 4 (Indexer Optimization & Fast-Track)

---

## 🎯 Features

### Current (Sprint 0-3 Complete)

- ✅ **Web UI**: Upload, Documents, Search, Configuration logic overhaul
- ✅ **Configuration Page**: 
    - Full Volume Management (Add/Scan/Delete Cloud Volumes)
    - Meilisearch Index Management (Create/Delete/Configure)
    - Integrated Server-Side File Browser
- ✅ **Upload Progress**: Animated 5-stage pipeline visualization
- ✅ **Document Management**: List with statistics, pagination, filtering, modals
- ✅ **Plugin Manager**: Dynamic adapter loading, discovery, and hot-swap
- ✅ **REST API**: Full config management endpoints (`/api/config`, `/api/cloud/volumes`, `/api/meilisearch/indexes`)
- ✅ **Mock Adapters**: OCR, Translation, Search (for development/testing)
- ✅ **Database**: SQLite with document model and metadata storage
- ✅ **API Management**: Start/stop/reload script with health checks
- ✅ **Configuration**: TOML-based plugin configuration with path variables

### Planned (Sprint 3)

- ⏳ **Tesseract OCR**: Real text extraction (100+ languages)
- ⏳ **Argos Translate**: Offline neural translation
- ⏳ **Meilisearch**: Production search engine with typo-tolerance
- ⏳ **MVP**: Testable by humans (end of Sprint 3, ~2025-11-14)

### Core Capabilities (Target)

- **Universal Indexing**: Recursively scans local, network, or cloud file trees
- **Multilingual Search**: Search across languages (`ballon` = `ball` = `球`)
- **Smart Translation**: View files translated while preserving structure
- **Multiple Formats**: Text, images (OCR), PDFs, Office documents
- **Export Ready**: JSON and Markdown export for AI/analysis tools

### Plugin Architecture

All components are **swappable plugins**:

- **OCR Engines**: Tesseract, Chandra-OCR, Google Cloud Vision, etc.
- **Translators**: Argostranslate (local), Google Translate API, DeepL, etc.
- **Search Backends**: Meilisearch, Elasticsearch, Tantivy, etc.
- **Storage**: SQLite, PostgreSQL, file-based index

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip and virtualenv
- (Optional) Nginx for reverse proxy

### Installation

```bash
# Clone repository
git clone https://github.com/shamantao/indexao.git
cd indexao

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with web UI
pip install -e ".[webui]"
```

### Start the Application

```bash
# Start API server
./ci/indexao-api.sh start

# Check status
./ci/indexao-api.sh status

# View logs
./ci/indexao-api.sh logs

# Stop server
./ci/indexao-api.sh stop
```

### Access Web Interface

```bash
# Direct access (default)
open http://127.0.0.1:8000

# Or with Nginx (if configured)
open http://indexao.localhost
```

### Web UI Features

**Upload Page** (`/`)

- Drag-and-drop file upload
- Multi-file support
- Real-time 5-stage progress:
  1. Upload
  2. Detection (MIME type, language)
  3. Extraction (OCR)
  4. Translation
  5. Indexing (search engine)

**Documents Page** (`/documents`)

- Statistics dashboard (total, completed, failed, success rate)
- Paginated document list (20 items/page)
- Status filtering (all, completed, failed, pending)
- Color-coded badges
- Document detail modal
- Auto-refresh (30s)

**Search Page** (`/search`)

- Full-text search input
- Filter by: content, translations, filenames
- Status filter
- Query highlighting in results
- Example queries for quick searches

### Configuration

```bash
# Copy example config
cp config.example.toml config.toml

# Edit paths and plugins
nano config.toml
```

Example `config.toml`:

```toml
[paths]
input_dir = "input"
output_dir = "output"
logs_dir = "logs"
db_path = "data/indexao.db"

[logging]
level = "INFO"
console_enabled = true
file_enabled = true

[plugins.ocr]
adapter = "mock"  # Will be "tesseract" in Sprint 3
# Available (future): tesseract, chandra, google_vision

[plugins.translator]
adapter = "mock"  # Will be "argos" in Sprint 3
languages = ["en", "fr", "es", "de"]
# Available (future): argostranslate, google_translate, deepl

[plugins.search]
adapter = "mock"  # Will be "meilisearch" in Sprint 3
# Available (future): meilisearch, tantivy, elasticsearch
```

## 📖 API Usage

### Plugin Management (Sprint 2)

```bash
# List all available plugins
curl http://127.0.0.1:8000/api/plugins

# List plugins by type
curl http://127.0.0.1:8000/api/plugins?adapter_type=ocr

# Get active adapters
curl http://127.0.0.1:8000/api/plugins/active

# Get active adapter for specific type
curl http://127.0.0.1:8000/api/plugins/ocr/active

# Switch adapter (hot-swap without restart)
curl -X POST http://127.0.0.1:8000/api/plugins/switch \
  -H "Content-Type: application/json" \
  -d '{"adapter_type": "ocr", "adapter_name": "tesseract"}'

# Get switch history
curl http://127.0.0.1:8000/api/plugins/history
```

### Upload File

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@document.pdf"
```

Response:

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "mime_type": "application/pdf",
  "size": 245678
}
```

### Process Document

```bash
curl -X POST http://127.0.0.1:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{"document_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

### List Documents

```bash
# All documents
curl http://127.0.0.1:8000/api/documents

# Filter by status
curl http://127.0.0.1:8000/api/documents?status=completed

# With limit
curl http://127.0.0.1:8000/api/documents?limit=10
```

### Get Document Details

```bash
curl http://127.0.0.1:8000/api/documents/550e8400-e29b-41d4-a716-446655440000
```

### Get Statistics

```bash
curl http://127.0.0.1:8000/api/stats
```

Response:

```json
{
  "total": 10,
  "completed": 8,
  "failed": 1,
  "pending": 1,
  "success_rate": 80.0
}
```

## 🛠️ Development

### Reload After Code Changes

```bash
# Reload with cache cleanup
./ci/indexao-api.sh reload
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/indexao

# Run specific test file
pytest tests/test_database.py
```

### Code Quality

```bash
# Lint code
ruff check src/

# Format code
ruff format src/

# Type checking
mypy src/
```

# Search in metadata

indexao search "author:john" --in metadata

````

### View & Export

```bash
# View translated file
indexao view /path/to/file.txt --lang fr

# Export to JSON
indexao export /path/to/file.txt --format json --lang fr,en

# Export to Markdown
indexao export /path/to/image.jpg --format markdown --lang zh-TW
````

## 🏗️ Architecture

Indexao uses a **hybrid Python/Rust architecture** (Polars Pattern):

- **Rust Core**: High-performance file scanning, indexing, and I/O operations
- **Python Layer**: Plugin ecosystem, ML models, and user interface
- **PyO3 Bridge**: Zero-copy data exchange via Apache Arrow

Benefits:

- ⚡ **Fast**: Rust performance for I/O-bound tasks
- 🐍 **Flexible**: Python ecosystem for ML/AI plugins
- 📦 **Portable**: Single binary distribution (15 MB)
- 🔌 **Modular**: Swap any component without code changes

For detailed architecture, see [`arch-tech.md`](./mkdoc/arch-tech.md).

## 🧪 Testing

### Run Tests

```bash
# Run all unit tests
python tests/test_plugin_discovery_standalone.py
python tests/test_load_adapter_standalone.py

# Run with pytest (if installed)
pytest tests/ -v
```

### Test Plugin Switcher UI

**Quick Test Procedure** (Sprint 2 Feature):

1. **Start the server**:

   ```bash
   ./ci/indexao-api.sh start
   # Or manually: uvicorn indexao.webui:app --reload
   ```

2. **Open the Config page**:

   - Navigate to: http://127.0.0.1:8000/config
   - Or via Nginx: http://indexao.localhost/config

3. **Test Plugin Switcher**:

   - Scroll to "Plugin Switcher (Hot-Swap)" section
   - See 3 dropdowns: OCR, Translator, Search
   - Each dropdown shows available plugins (currently: mock)
   - Status shows current active adapter
   - Click "Switch OCR" button to test hot-swap
   - Success message appears, page reloads

4. **Test API directly**:

   ```bash
   # List plugins
   curl http://127.0.0.1:8000/api/plugins

   # Check active adapters
   curl http://127.0.0.1:8000/api/plugins/active

   # Switch adapter
   curl -X POST http://127.0.0.1:8000/api/plugins/switch \
     -H "Content-Type: application/json" \
     -d '{"adapter_type": "ocr", "adapter_name": "mock"}'
   ```

5. **Expected behavior**:
   - ✅ Plugins load without errors
   - ✅ Dropdowns populate with available adapters
   - ✅ Status badges show active state
   - ✅ Switching updates status in real-time
   - ✅ No server restart needed

## 📚 Documentation

- [Technical Architecture](./mkdoc/arch-tech.md) - Design decisions, plugin APIs, data models
- [Sprint Backlog](./mkdoc/_backlog.md) - Development tracking
- [Changelog](./CHANGELOG.md) - Version history and updates

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

**Key principles**:

- Files ≤ 300-400 lines (split into modules)
- English comments and docstrings
- User-centric tests (end-to-end scenarios)
- Plugin-first architecture (composition over inheritance)

## 📋 Requirements

**Python**: 3.10+
**Rust**: 1.70+ (optional, for hybrid build)

**Dependencies**:

- Core: `click`, `pyyaml`, `python-magic`
- Search: `meilisearch` (or chosen backend)
- Optional: `maturin` (hybrid build), `polars` (data processing)

## 📄 License

MIT License - See [LICENSE](./LICENSE)

## 🙏 Credits

Built with best-of-breed open source tools:

- [Polars](https://pola.rs/) - Hybrid Rust/Python pattern
- [Meilisearch](https://www.meilisearch.com/) - Search engine
- [Tesseract](https://github.com/tesseract-ocr/tesseract) - OCR
- [Argostranslate](https://github.com/argosopentech/argos-translate) - Translation
- [PyO3](https://pyo3.rs/) - Rust ↔ Python bridge

---

**Status**: 🚧 Active Development - Sprint 0 (Architecture Setup)

Last updated: 2025-11-05
