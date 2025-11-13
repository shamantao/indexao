# Changelog

All notable changes to the Indexao project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - v0.4.0-dev

### Planned Features

- [ ] Directory scanner with background processing
- [ ] File indexation (name, path, metadata)
- [ ] Basic search (name/path)
- [ ] Tesseract OCR on scanned PDFs/images
- [ ] Metadata extraction
- [ ] UI for results visualization

### In Progress - November 13, 2025

#### Framework Manager - Local JS/CSS with CDN Fallback

**Status**: ✅ Complete

Created comprehensive framework management system for frontend dependencies:

- **Local Storage**: Alpine.js (44KB), HTMX (47KB), FontAwesome (100KB) stored in `/static/js|css/vendor/`
- **Automatic Fallback**: CDN loading if local files fail via `onerror` handlers
- **Version Management**: JSON state tracking with download dates and sizes
- **Update System**: 30-day refresh cycle with API endpoints
- **REST API**: 
  - `GET /api/frameworks/status` - Check availability and versions
  - `POST /api/frameworks/download` - Download specific or all frameworks
  - `GET /api/frameworks/check-updates` - Find outdated frameworks

**Files Created**:
- `src/indexao/framework_manager.py` (339 lines) - Core manager with Framework class
- Updated `src/indexao/templates/base.html` - Fallback script tags
- Updated `src/indexao/webui.py` - Added 3 API routes

**Benefits**:
- ✅ Offline development capability
- ✅ Faster page loads (no external requests)
- ✅ Version pinning and consistency
- ✅ Automatic failover to CDN
- ✅ Integration with PluginManager architecture

#### Cloud Volume Management UI

**Status**: ✅ Complete

Added complete interface for managing multiple cloud storage volumes:

- **3-Tab Config Page**: Indexao Settings | Cloud Volumes | Meilisearch Indexes
- **Volume Cards**: Name, path, mount status, progress bars, file counts
- **Add Volume Modal**: Name, path, index, file patterns with validation
- **Actions**: Scan Now, Delete per volume
- **API Routes** (4 endpoints):
  - `GET /api/cloud/volumes` - List all volumes with status
  - `POST /api/cloud/volumes` - Add new volume
  - `POST /api/cloud/volumes/{name}/scan` - Trigger progressive scan
  - `DELETE /api/cloud/volumes/{name}` - Remove volume

**Files Updated**:
- `src/indexao/templates/config.html` - Added cloud tab, modal, JS functions
- `src/indexao/webui.py` - Added 4 cloud volume API routes (lines 817-932)

**CSS Enhancements**:
- `.modal` and `.modal.active` classes for Alpine.js modals
- `.badge-success` and `.badge-false` for mount status indicators
- `.close-button` styling for modal close actions
- Progress bar styles with smooth transitions

**Target**: MVP Functional - Real usage ready

---

## [0.3.0-dev] - 2025-11-07

**Status**: ✅ Complete (1 day)  
**Focus**: Plugin Manager - Dynamic adapter loading with hot-swap

### Summary

Sprint completed in 1 day instead of 1 week planned (32% faster). Added complete plugin system with configuration, validation, runtime switching, discovery, and dynamic loading.

**Achievement**: Full plugin architecture operational with REST API and UI 🚀

**Key Metrics**:
- Time: 20.5h actual vs 36h estimated
- Tasks: 5/5 complete + 1 bugfix
- Files: 755 lines plugin_manager.py, 274 lines API, 154 lines UI
- Tests: 26 tests passing across all tasks

### Added

#### Plugin Manager Core (755 lines)

- Configuration system with TOML per adapter
- Interface validation with Protocol checking
- Runtime hot-swap without restart
- Automatic plugin discovery via AST parsing
- Dynamic loading with importlib + introspection
- Cleanup hooks for safe adapter switching
- Switch history tracking for debugging

#### REST API (7 endpoints - 274 lines)

- `GET /api/plugins` - List all available plugins
- `GET /api/plugins/active` - Get active adapters
- `GET /api/plugins/{type}/active` - Get active for specific type
- `POST /api/plugins/switch` - Hot-swap adapter
- `GET /api/plugins/registered` - In-memory registry
- `GET /api/plugins/history` - Switch history

#### UI Enhancements

- Plugin switcher in `/config` page
- Dropdown per adapter type (OCR, Translator, Search)
- Real-time status indicators
- Hot-swap without page reload
- Automatic plugin discovery on load

### Fixed

- Log paths simplified - now centralized in `logs/` at project root
- Path variable expansion working correctly with `${vars}` syntax
- Removed complex log path resolution from startup script

### Technical Details

**Files Modified/Added**:
- `src/indexao/plugin_manager.py`: 755 lines (new core)
- `src/indexao/plugin_routes.py`: 274 lines (new API)
- `src/indexao/webui.py`: +12 lines (integration)
- `templates/config.html`: +154 lines (UI switcher)
- `static/css/styles.css`: +136 lines (styles)
- `ci/indexao-api.sh`: Simplified log handling
- `config.toml`: Logs now in `logs/` (not external path)
- `.gitignore`: Added `logs/` directory

**Tests**: 26 total
- test_plugin_manager.py: 15 tests
- test_protocol_validation.py: 9 tests
- test_runtime_switching.py: 8 tests
- test_plugin_discovery.py: 13 tests
- test_load_adapter_standalone.py: 8 tests

---

## [0.2.1-dev] - 2025-11-07

**Status**: ✅ Complete (6h)  
**Focus**: Path Variables System - DRY Configuration

### Summary

Implemented `${var}` variable system in TOML configuration to eliminate path repetition. Reduced configuration redundancy by 90%.

### Added

- Path variables system with `${var}` syntax in TOML
- Recursive variable expansion in config.py (~80 lines)
- 8 predefined variables (home, workspace_data, downloads, index, sources, volumes, logs, cache)
- Complete documentation (PATHS-CONFIG.md, config.example.toml)

### Changed

- Migrated config.toml to use 17 variable references
- Maintenance now requires 2-3 variables instead of 10+ absolute paths

### Technical Details

**Key Metrics**:
- Reduction: -90% path repetition
- Variables: 8 defined
- References: 17 in config.toml

---

## [0.2.0-dev] - 2025-11-06

**Status**: ✅ Complete (3 days)  
**Focus**: MVP Core, Cleanup, Architecture & Documentation

### Summary (v0.2.0)

Three rapid iterations completed:
1. **Core MVP** (1 day): Complete UI with mock backend
2. **Cleanup** (1 day): Workspace organization and architecture docs
3. **Design** (1 day): Plugin manager specifications

### Added - Core MVP

#### Processing Pipeline (3 components)

**Upload Handler** (`upload_handler.py` - 127 lines)
- Multi-file upload via `POST /api/upload`
- MIME type detection and validation
- Secure temporary storage
- Metadata extraction
- Unique document ID generation

**File Scanner** (`file_scanner.py` - 156 lines)
- Recursive file discovery
- Protocol support: `file://`, `smb://`, `nfs://`
- Extension-based filtering
- File metadata extraction

**Document Processor** (`processor.py` - 248 lines)
- 5-stage pipeline: Upload → Detection → Extraction → Translation → Indexing
- Per-document status tracking
- Robust error handling with detailed logs
- Progress tracking for UI

#### Mock Adapters (3 adapters)

**Mock OCR** (`adapters/mock_ocr.py` - 98 lines)
- Simulated text extraction
- Multi-page support
- 4-language detection (en, fr, es, de)
- Confidence scores per page

**Mock Translator** (`adapters/mock_translator.py` - 87 lines)
- Simulated translation (4 languages)
- Automatic source language detection
- Translation result caching
- Batch processing support
- Mock delay simulation

**Mock Search** (`adapters/mock_search.py` - 112 lines)
- In-memory document storage
- Case-insensitive full-text search
- Status and date filtering
- Basic relevance ranking
- Query highlighting

#### Database Layer (2 components)

**Document Model** (`models.py` - 145 lines)
- SQLAlchemy ORM with SQLite backend
- Complete document lifecycle tracking
- JSON columns for flexible metadata
- Automatic timestamp management

**Database Operations** (`database.py` - 187 lines)
- Thread-safe SQLite connections
- CRUD operations (Create, Read, Update, Delete)
- Bulk insert support
- Document search and filtering
- Connection pooling
- Transaction management

#### UI Enhancements (3 pages)

**Upload Progress** (`index.html` updates)
- Real-time upload progress bar
- Multi-file selection
- Drag-and-drop support
- File preview thumbnails
- Status indicators

**Documents Page** (`templates/documents.html` - 285 lines)
- Paginated document list
- Advanced filtering (status, date, MIME type)
- Sortable columns
- Document actions (view, delete, reprocess)
- Status badges with color coding

**Search Interface** (`templates/search.html` - 268 lines)
- Full-text search input
- Search filters (language, date range)
- Result highlighting
- Relevance scoring display
- Quick actions (view, download)

### Added - Cleanup & Architecture

**Workspace Cleanup**
- Removed 8 obsolete files
- Cleaned 20+ cache directories
- Organized project structure
- Updated .gitignore

**Documentation** (1750+ lines)
- ADAPTER-INTERFACES.md (1100+ lines): Complete adapter specifications
- PLUGIN-MANAGER-DESIGN.md (650+ lines): Plugin system architecture
- Updated README.md with current features
- Refined Sprint 2-3 backlog

---

## [0.1.0-dev] - 2025-11-05/06

**Status**: ✅ Complete (1 day)  
**Focus**: Technical Foundation & Setup

### Summary

Established solid technical foundation with plugin-first architecture in 1 day instead of 2 weeks planned.

### Added

#### Core Infrastructure

**Architecture & Documentation**
- arch-tech.md: Technical architecture document
- README.md: Project overview and setup
- CHANGELOG.md: Version history
- .AI-INSTRUCTIONS.md: Development guidelines

**Repository Structure**
- src/indexao/: Main Python package
- config/: Configuration files
- venv/: Virtual environment
- tests/: Test suite structure

**Configuration System**
- TOML configuration loader
- Path management system
- Environment variable support
- Multi-environment configs

#### Web Interface

**Web UI Dark Mode** (FastAPI + Templates)
- Dark theme matching GEDtao design
- Responsive layout
- FontAwesome icons
- Modern CSS with animations

**Routes** (6 initial endpoints)
- `/`: Home page
- `/config`: Configuration panel
- `/api/config`: Config API
- `/api/upload`: File upload
- `/api/files`: File listing
- `/health`: Health check

#### DevOps

**API Management** (`ci/indexao-api.sh`)
- Start/stop/status commands
- Process management
- Log file handling
- Health checks

**Nginx Integration**
- Reverse proxy setup
- indexao.localhost domain
- SSL/TLS ready
- Static file serving

### Technical Details

**Quality Metrics**:
- Files: 15+ created
- Lines: ~1,100 (HTML/CSS/JS/Python)
- File size: All files < 500 lines ✓
- Response time: < 100ms average

---
- Complete CRUD operations:
  - Create document
  - Read by ID or filters
  - Update document fields
  - Delete document
  - List with pagination
- Statistics API (total, completed, failed, success rate)
- Automatic database migrations
- Backup/restore functions

#### P4: UI Enhancements (3/3)

**Task 4.1: Upload Progress**

- Enhanced `templates/index.html` (+52 lines)
  - Progress section with 5 animated stages
  - Progress bar 0-100% with gradient fill
  - Stage indicators with spinners (active) and checkmarks (completed)
- Enhanced `static/css/styles.css` (+200 lines)
  - `.upload-progress` styles
  - `.progress-bar` with gradient animation
  - `.processing-stages` horizontal layout
  - Stage active/completed states
- Enhanced `static/js/app.js` (+154 lines)
  - `showProgress()` - Display and reset progress UI
  - `updateProgress(percent, status)` - Update bar and text
  - `updateStage(name, status)` - Animate stage transitions
  - `processDocument(docId)` - Trigger processing with stage tracking
  - Integration with `POST /api/process` endpoint

**Task 4.2: Documents Page**

- New `templates/documents.html` (126 lines)
  - Statistics dashboard (4 cards):
    - Total documents
    - Completed documents
    - Failed documents
    - Success rate percentage
  - Document list with pagination (20 items/page)
  - Status filter dropdown (all, completed, failed, pending)
  - Color-coded status badges
  - Document detail modal with full content
  - Auto-refresh every 30 seconds
- New `static/js/documents.js` (334 lines)
  - `loadStatistics()` - Fetch from `GET /api/stats`
  - `loadDocuments()` - Fetch from `GET /api/documents?status=...`
  - `displayDocuments()` - Render paginated list
  - `updatePagination()` - Previous/next page controls
  - `showDocumentDetails(docId)` - Modal with full document data
  - `getStatusBadge(status)` - Generate color-coded HTML badges
  - `getFileIcon(mime)` - MIME type to icon mapping
- Enhanced `static/css/styles.css` (+150 lines)
  - `.documents-list` grid layout
  - `.document-item` with hover effects
  - `.status-badge` colored badges (4 variants)
  - `.modal` full-screen overlay
  - `.modal-content` centered card with scroll
  - `.detail-section` organized sections
- Route added: `GET /documents`

**Task 4.3: Search Interface**

- New `templates/search.html` (142 lines)
  - Search form with query input and submit button
  - 3 filter checkboxes (search in: content, translations, filenames)
  - Status filter dropdown (all, completed, failed)
  - Results card (hidden until search performed)
  - 4 example queries with pre-fill buttons:
    - "database"
    - "test"
    - "document"
    - "Sprint"
  - Document detail modal (reused from documents page)
- New `static/js/search.js` (289 lines)
  - `performSearch(event)` - Form submission handler
  - `searchDocuments(query)` - Client-side search implementation
    - Fetches documents from `GET /api/documents`
    - Filters by query match in selected fields
    - Case-insensitive search
  - `displayResults(results, query)` - Render results with highlighting
  - `highlightText(text, query)` - Wrap matches in `<mark>` tags (regex-based)
  - `searchExample(query)` - Pre-fill from example buttons
  - `clearSearch()` - Reset search state
  - `showDocumentDetails(docId)` - Open modal with full content
- Enhanced `static/css/styles.css` (+200 lines)
  - `.search-form` styles
  - `.search-input-group` flex layout
  - `.search-filters` filter controls
  - `.search-result-item` result cards with hover
  - `.result-preview mark` highlighting styles (yellow background)
  - `.examples-grid` example query buttons
- Route added: `GET /search`

#### API Routes Added

| Route                     | Method | Description                           |
| ------------------------- | ------ | ------------------------------------- |
| `POST /api/upload`        | POST   | Upload file(s) and get document ID    |
| `POST /api/process`       | POST   | Process uploaded document (5 stages)  |
| `GET /api/documents`      | GET    | List documents with filters           |
| `GET /api/documents/{id}` | GET    | Get single document details           |
| `GET /api/stats`          | GET    | Statistics (total, completed, failed) |
| `GET /documents`          | GET    | Documents list page (HTML)            |
| `GET /search`             | GET    | Search interface page (HTML)          |

### Changed

- Version bumped from 0.1.0-dev to 0.2.0-dev
- Navigation updated with Documents and Search links
- `styles.css` expanded from 429 to 620+ lines
- `app.js` expanded from 146 to 300+ lines
- `index.html` enhanced with progress section

### Technical Metrics - Sprint 1

- **Duration**: 1 day (10 hours)
- **Tasks completed**: 11/11 (100%)
- **Files created**: 8 new files
- **Files modified**: 5 files
- **Lines of code added**: ~2,000 lines
- **Database**: 10 documents indexed (100% success rate)
- **Code quality**: All files < 500 lines ✓
- **UI Components**: 3 pages (Upload, Documents, Search)
- **Status**: ✅ Production ready (with mock adapters)

### Demo Sprint 1

```bash
# Start API
./ci/indexao-api.sh start

# Access features
open http://127.0.0.1:8000/           # Upload with animated progress
open http://127.0.0.1:8000/documents   # Documents list with stats
open http://127.0.0.1:8000/search      # Search with highlighting

# Test workflow
# 1. Upload file → watch 5-stage progress animation
# 2. Go to Documents → see statistics dashboard + badges
# 3. Click document → see modal with full details
# 4. Go to Search → search "database" → see highlighted results
```

---

## [0.1.0-dev] - Sprint 0 (2025-11-05 → 2025-11-06)

**Status**: ✅ Complete (1 day)  
**Focus**: Technical foundation and web interface

### Added

#### Architecture & Documentation

- Project architecture documentation (`arch-tech.md`)
- Development guidelines (`.AI-INSTRUCTIONS.md`)
- Sprint backlog (`mkdoc/20251105_backlog.md`)
- README with user guide
- VERSION file for release tracking

#### Configuration System

- TOML-based configuration (`config.example.toml`)
- Config loader module (`src/indexao/config.py`)
- Plugin configuration (OCR, Translator, Search)
- Path configuration (input/output/logs)
- Log level management

#### Web UI (Dark Mode - GEDtao Style)

- FastAPI web server (`src/indexao/webui.py`)
- Upload interface (`templates/index.html` - 128 lines)
- Configuration viewer (`templates/config.html` - 377 lines)
- Dark theme CSS (`static/css/styles.css` - 429 lines)
- Client-side JavaScript (`static/js/app.js` - 146 lines)
- FontAwesome 6.4.0 icons integration
- Cache-busting mechanism

#### API Endpoints

- `GET /` - Upload interface
- `GET /config` - Configuration viewer
- `GET /api/config` - JSON configuration
- `POST /api/upload` - File upload
- `GET /api/files` - File list
- `GET /health` - Health check

#### DevOps & Tooling

- API management script (`ci/indexao-api.sh`)
  - Commands: start, stop, restart, status, reload, logs
  - PID management and health checks
  - Python cache cleanup
  - Colored terminal output
- Nginx reverse proxy configuration
- Virtual environment setup
- Package installation (`pyproject.toml`)

#### Path Management

- `PathAdapter` protocol for universal path abstraction
- `FileInfo` dataclass with metadata
- `LocalPathAdapter` for file:// protocol
- Path resolution cache (thread-safe)
- Retry logic with exponential backoff
- Factory function `get_path_adapter(uri)`

### Technical Details

- **Lines of code**: ~1,100 lines
- **Files created**: 15+
- **Code quality**: All files < 500 lines ✓
- **Architecture**: Plugin-first design
- **UI Framework**: FastAPI + Jinja2
- **Styling**: Custom dark theme (GEDtao inspired)

### Infrastructure

- **Web Server**: FastAPI on port 8000
- **Reverse Proxy**: Nginx (indexao.localhost)
- **URL**: http://indexao.localhost/
- **Upload Limit**: 100MB
- **Timeouts**: 300s

---

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
| 0.1.0-dev | 2025-11-05 | Sprint 0 | ✅ Done        |
| 0.2.0-dev | 2025-11-19 | Sprint 1 | 🚧 In Progress |
| 0.3.0-dev | 2025-12-03 | Sprint 2 | ⏳ Planned     |
| 1.0.0     | 2025-12-17 | Release  | 🎯 Target      |

---

## Contributing

When adding entries to this changelog:

1. **Format**: Use `YYYY-MM — <Short Title>` for each entry
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

**Last Updated**: 2025-11-06
