# Changelog

All notable changes to the Indexao project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- Initial project architecture (Hybrid Python/Rust - Polars Pattern)
- Documentation: README.md, arch-tech.md, changelog.md
- Sprint planning in mkdoc/backlog.md
- Directory structure for modular plugin system
- Configuration examples (config.example.toml)

### Architecture Decisions

- **Hybrid Rust/Python approach** using PyO3 + maturin (inspired by Polars)
- **Plugin-first design** for OCR, translation, and search backends
- **Apache Arrow** for zero-copy data exchange between Rust and Python
- **Meilisearch** as default search engine (multilingual, typo-tolerant)
- **Path abstraction layer** supporting local, network (SMB), and cloud (S3) schemes

---

## [0.1.0-dev] - Sprint 0 (2025-11-05 → 2025-11-19)

### Added - Days 3-4 (2025-11-05)

- **Path Management Module** (`src/indexao/paths/` - 586 lines)

  - `PathAdapter` protocol for universal path abstraction
  - `FileInfo` dataclass with rich metadata (size, mtime, MIME type, permissions)
  - `FileType` enum (FILE, DIRECTORY, SYMLINK, UNKNOWN)
  - `LocalPathAdapter` for file:// protocol (production-ready)
  - Path resolution cache (thread-safe with Lock)
  - Retry logic with exponential backoff
  - Support for absolute and relative paths
  - Performance tracking integration (logger.timer)
  - Factory function `get_path_adapter(uri)` with scheme dispatch
  - Future schemes prepared: smb://, s3://

- **Tests** (`tests/unit/test_paths.py` - 323 lines)

  - 27 test cases (100% pass rate)
  - FileInfo, factory, LocalPathAdapter operations
  - Cache, retry, MIME detection tests
  - Coverage: ~90% of path management code

- **Demo** (`demo_paths.py` - 150 lines)

  - 12 scenarios: list_dir, read_file, stream, stat, exists, path resolution
  - All scenarios validated successfully

**Technical:**

- @runtime_checkable protocols for adapter dispatch
- Thread-safe cache with Lock for concurrent access
- Retry logic with exponential backoff (3 attempts, 100ms → 400ms)
- MIME type detection via mimetypes module
- Absolute path resolution with base_path support
- Logger integration with TRACE-level debugging
- Zero-copy Path objects (no string manipulation)

**Metrics:**

- Lines: 586 (base.py: 156, local.py: 367, **init**.py: 63)
- Tests: 27/27 (100% pass rate)
- Coverage: ~90%
- Performance: Tests run in 0.15s
- Documentation: `mkdoc/20251105_sprint0_days34_paths_COMPLET.md`

---

### Added - Days 6-7 (2025-11-05)

**Base Adapter Interfaces** (`src/indexao/adapters/` - 892 lines)

- **OCR Adapter Protocol** (`ocr/base.py` - 143 lines)

  - `OCRAdapter` protocol: 6 methods (`name`, `supported_languages`, `process_image()`, `process_batch()`, `is_available()`, `get_version()`)
  - `OCRResult` dataclass with confidence validation (0.0-1.0)
  - Word-level OCR details support

- **Translator Adapter Protocol** (`translator/base.py` - 136 lines)

  - `TranslatorAdapter` protocol: 7 methods (translate, batch, detect language)
  - `TranslationResult` dataclass with confidence validation
  - Multi-language support declaration

- **Search Adapter Protocol** (`search/base.py` - 244 lines)

  - `SearchAdapter` protocol: 11 methods (CRUD + search operations)
  - `IndexedDocument` dataclass for indexing
  - `SearchResult` dataclass with score validation (0.0-1.0)
  - Language filtering, pagination, metadata support

- **Mock Implementations** for testing:

  - `MockOCRAdapter` (106 lines): Configurable text, simulates latency
  - `MockTranslatorAdapter` (119 lines): Reverse text or pass-through
  - `MockSearchAdapter` (177 lines): In-memory storage, substring search

- **Tests** (`tests/unit/test_adapters.py` - 447 lines)

  - 28 test cases: 7 OCR, 8 Translator, 13 Search
  - Protocol compliance via `isinstance()` checks
  - Dataclass validation (confidence/score ranges)
  - Mock adapter functional testing
  - 100% success rate (28/28 pass in 0.16s)

- **Demo Script** (`demo_adapters.py` - 259 lines)

  - 4 scenarios: OCR, translation, search, protocol compatibility
  - All demos completed successfully

- **Build Configuration** (`pyproject.toml` - 68 lines)
  - Package metadata, dependencies, build system
  - pytest/black/ruff configuration
  - Editable install: `pip install -e .`

**Technical:**

- @runtime_checkable protocols (duck typing)
- **post_init** validation for dataclasses
- Thread-safe mock implementations
- Logger integration
- Zero-copy Path objects

**Metrics:**

- Lines: 1,699 (protocols 523 + mocks 402 + tests 447 + demo 259 + config 68)
- Tests: 28/28 (100%)
- Coverage: ~95%
- Performance: 0.16s test execution
- Documentation: `mkdoc/20251105_sprint0_days67_adapters_COMPLET.md`

---

- **Configuration** (`config.example.toml`)
  - New `[paths.adapters]` section
  - cache_enabled, timeout, retry_count, retry_delay settings

### Added - Day 2 (2025-11-05)

- **Advanced Logging System** (`src/indexao/logger.py` - 448 lines)

  - Custom TRACE level (level 5) for ultra-verbose debugging
  - ColoredFormatter with ANSI codes for terminal output
  - JSONFormatter for structured logging (log aggregation ready)
  - ContextEnrichedLogger with nested context support
  - LoggerManager singleton for global configuration
  - Performance tracking with `timer()` context manager
  - Automatic slow operation detection (configurable threshold)
  - Multiple handlers: console (colored), file (daily rotation), debug_file (TRACE), json
  - Thread-safe operations with Lock
  - 8 environment variables for flexible configuration
  - `init_logging()`, `set_level()`, `get_logger()` public API

- **Tests** (`tests/unit/test_logger.py` - 294 lines)

  - 14 test cases covering all functionality
  - Formatters, context enrichment, performance timer, rotation

- **Demo** (`demo_logger.py` - 97 lines)

  - 9 usage scenarios demonstrating all features

- **Configuration** (`config.example.toml`)

  - New `[logging]` section with 5 subsections
  - Console, file, debug_file, json, format, performance settings

- **Development Environment**
  - Python venv with pytest
  - Makefile `setup` target
  - .gitignore updated (venv/)

### Added - Day 1 (2025-11-05)

**Duration**: 2025-11-05 to 2025-11-19 (2 weeks)

#### Objectives

- [x] Define technical architecture and technology stack
- [x] Create repository structure with modular layout
- [ ] Implement base adapter interfaces (OCR, Translator, Search)
- [ ] Build path/routes management module
- [ ] Setup logging and configuration system
- [ ] Configure CI pipeline (lint, test, build)

#### Documentation Created

- `README.md` - User-facing documentation with quick start guide
- `arch-tech.md` - Technical architecture with plugin APIs and data models
- `changelog.md` - This file
- `mkdoc/20251105_backlog.md` - Detailed sprint planning

#### Technology Stack Finalized

- **Languages**: Python 3.10+ (primary), Rust 1.70+ (performance core)
- **Bridge**: PyO3 with maturin build system
- **Search**: Meilisearch (default), Tantivy (alternative), SQLite FTS (fallback)
- **OCR**: Tesseract (default plugin), Chandra-OCR (VLM plugin), Cloud APIs (future)
- **Translation**: Argostranslate (local), Google Translate API (optional)
- **Data Format**: Apache Arrow (zero-copy), JSON (fallback)
- **Config**: TOML (primary), YAML (alternative)

#### Key Design Patterns

- **Adapter Pattern**: All components (OCR, translator, search) are swappable plugins
- **Composition over Inheritance**: Plugin system uses composition for flexibility
- **Smart Dispatcher**: Automatic routing of tasks to Rust (I/O) or Python (ML)
- **Zero-Copy**: Apache Arrow format for efficient Rust ↔ Python data exchange

#### File Size Constraint

- All source files limited to **≤ 300-400 lines**
- Enforced via code reviews and CI checks
- Modules split when exceeding limit

#### Next Sprint Preview

Sprint 1 (MVP Core) will deliver:

- File scanner (recursive directory traversal)
- Tesseract OCR adapter implementation
- Argostranslate translation adapter
- Meilisearch indexing backend
- Basic CLI commands (index, search, view)
- First end-to-end test (multilingual search scenario)

---

## Version History

| Version   | Date       | Sprint   | Status         |
| --------- | ---------- | -------- | -------------- |
| 0.1.0-dev | 2025-11-05 | Sprint 0 | 🚧 In Progress |
| 0.2.0-dev | 2025-11-19 | Sprint 1 | ⏳ Planned     |
| 0.3.0-dev | 2025-12-03 | Sprint 2 | ⏳ Planned     |
| 1.0.0     | 2025-12-17 | Release  | 🎯 Target      |

---

## Contributing

When adding entries to this changelog:

1. **Format**: Use `YYYY-MM-DD — <Short Title>` for each entry
2. **Categories**: Added, Changed, Deprecated, Removed, Fixed, Security
3. **Detail Level**: Be specific but concise (bullet points preferred)
4. **User Focus**: Write for users, not just developers
5. **Links**: Reference issues, PRs, commits when relevant

Example:

```markdown
### Added

- New Google Cloud Vision OCR adapter plugin (#42)
- Support for S3 paths in path management module (#38)

### Fixed

- Memory leak in Rust file scanner (#45)
- Translation cache not respecting TTL (#43)
```

---

**Status**: 🚧 Active Development - Sprint 0  
**Last Updated**: 2025-11-05  
**Next Review**: 2025-11-19 (End of Sprint 0)
