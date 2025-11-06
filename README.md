# Indexao

**Universal multilingual search, indexing, and translation tool**

Indexao is a modular, user-centric tool to index arbitrary file trees and enable unified multilingual search, full translated visualization (keeping structure), and export to JSON/Markdown.

## 🎯 Features

### Core Capabilities

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

### Installation

```bash
# Clone repository
git clone https://github.com/shamantao/indexao.git
cd indexao

# Install dependencies
pip install -e .

# Or use the hybrid Rust/Python build (faster)
pip install maturin
maturin develop --release
```

### First Run - Demo

```bash
# Run demo with sample data
make demo

# Or manually:
python -m indexao.cli index ../_Volumes/demo
python -m indexao.cli search "ball"
```

```bash
# Démarrer l'API
./ci/indexao-api.sh start

# Vérifier le statut
./ci/indexao-api.sh status

# Après modification du code : recharger sans cache
./ci/indexao-api.sh reload

# Suivre les logs
./ci/indexao-api.sh logs
```

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
index_root = "../index"
sources_root = "../_sources"
volumes_root = "../_Volumes"

[languages]
enabled = ["fr", "en", "zh-TW"]
default = "en"

[plugins.ocr]
default = "tesseract"
# Available: tesseract, chandra, google_vision

[plugins.translator]
default = "argostranslate"
# Available: argostranslate, google_translate, deepl

[plugins.search]
backend = "meilisearch"
# Available: meilisearch, tantivy, simple
```

## 📖 Usage Examples

### Index a folder

```bash
# Index local folder
indexao index ~/Documents

# Index with specific OCR engine
indexao index ~/Pictures --ocr chandra

# Index and translate immediately
indexao index ~/Data --translate fr,en,zh-TW
```

### Search

```bash
# Simple search
indexao search "ballon"

# Search with language filter
indexao search "ball" --lang en

# Search in metadata
indexao search "author:john" --in metadata
```

### View & Export

```bash
# View translated file
indexao view /path/to/file.txt --lang fr

# Export to JSON
indexao export /path/to/file.txt --format json --lang fr,en

# Export to Markdown
indexao export /path/to/image.jpg --format markdown --lang zh-TW
```

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

For detailed architecture, see [`arch-tech.md`](./arch-tech.md).

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test suite
pytest tests/test_indexing.py

# Run end-to-end tests
pytest tests/e2e/
```

## 📚 Documentation

- [Technical Architecture](./arch-tech.md) - Design decisions, plugin APIs, data models
- [Changelog](./changelog.md) - Version history and updates
- [Sprint Progress](./mkdoc/) - Development tracking (not in Git)

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
