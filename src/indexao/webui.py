"""
Web UI for Indexao - Sprint 0 Basic Interface

A simple web interface to test the indexing system.
Features:
- Upload documents
- View indexed content
- Search interface
- Configuration viewer
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import threading

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import httpx

from indexao.config import load_config, get_config, Config
from indexao.logger import get_logger
from indexao.upload_handler import UploadHandler, UploadError
from indexao.services.fast_track import FastTrackService # Sprint 2
from indexao.scanner import FileScanner, scan_directory
from indexao.processor import DocumentProcessor, ProcessingStatus
from indexao.database import DocumentDatabase
from indexao.models.document import ProcessingStatus as DocStatus
from indexao.framework_manager import get_framework_manager, ensure_frameworks_available
from indexao.plugin_manager import PluginManager
from indexao.plugin_routes import router as plugin_router, set_plugin_manager

# Initialize logger
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Indexao Web UI",
    description="Simple web interface for document indexing",
    version="0.1.0"
)

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

# Create directories if they don't exist
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include plugin routes
app.include_router(plugin_router)

# Include pipeline routes
from indexao.pipeline.routes import router as pipeline_router
app.include_router(pipeline_router)

# Include search routes
from indexao.search_routes import router as search_router
app.include_router(search_router)

# Track ongoing scans
_active_scans: Dict[str, Dict[str, Any]] = {}
_scan_lock = threading.Lock()


@app.get("/api/docs")
async def api_docs_redirect():
    """Redirect to local MkDocs server."""
    return RedirectResponse(url="http://localhost:8001")


@app.on_event("startup")
async def startup_event():
    """Initialize configuration on startup."""
    try:
        logger.info("Starting Indexao Web UI...")
        
        # Ensure offline frameworks are available
        logger.info("Checking frontend frameworks...")
        try:
            if ensure_frameworks_available():
                logger.info("✓ Frontend frameworks ready (Alpine.js, HTMX, FontAwesome)")
            else:
                logger.warning("! Helper frameworks download failed - UI might degrade offline")
        except Exception as e:
             logger.error(f"Framework check failed: {e}")

        config = load_config()
        logger.info(f"Configuration loaded: {config}")
        
        # Load version from file
        try:
            # webui.py is in src/indexao/, so we go up 3 levels to reach root
            version_file = Path(__file__).parent.parent.parent / "VERSION"
            if version_file.exists():
                app_version = version_file.read_text().strip()
                templates.env.globals["version"] = app_version
                logger.info(f"✓ Version loaded: {app_version}")
            else:
                logger.warning(f"Version file not found at {version_file}")
                templates.env.globals["version"] = "0.4.0-dev"
        except Exception as e:
            logger.warning(f"Failed to load version: {e}")
            templates.env.globals["version"] = "unknown"

        # Create required directories
        Path(config.input_dir).mkdir(parents=True, exist_ok=True)
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        Path(config.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize upload handler
        app.state.upload_handler = UploadHandler(config)
        
        # Initialize FastTrack Service (Sprint 2 - Hybrid Indexing)
        app.state.fast_track = FastTrackService()

        # Initialize document processor
        app.state.processor = DocumentProcessor(config, app.state.upload_handler)
        
        # Initialize plugin manager (empty config for now, will read from TOML later)
        app.state.plugin_manager = PluginManager({})
        set_plugin_manager(app.state.plugin_manager)
        
        # Auto-load mock adapters for initial state
        try:
            app.state.plugin_manager.load_adapter('ocr', 'mock', auto_register=True, fallback_to_mock=False)
            app.state.plugin_manager.load_adapter('translator', 'mock', auto_register=True, fallback_to_mock=False)
            app.state.plugin_manager.load_adapter('search', 'mock', auto_register=True, fallback_to_mock=False)
            logger.info("✓ Mock adapters loaded")
        except Exception as e:
            logger.warning(f"Failed to load mock adapters: {e}")
        
        # Initialize pipeline with real adapters (MVP: Tesseract + Meilisearch)
        try:
            from indexao.pipeline.routes import initialize_processor
            initialize_processor(use_real_adapters=True)
            logger.info("✓ Pipeline processor initialized (Tesseract + Meilisearch)")
        except Exception as e:
            logger.warning(f"Failed to initialize pipeline: {e}")
        
        # Initialize search adapter
        try:
            from indexao.search_routes import initialize_search_adapter
            config = get_config()
            
            # Robust config access for Meilisearch
            # Assuming config structure matches TOML: plugins.search.meilisearch.host
            try:
                # Try explicit meilisearch config first
                meili_host = config.plugins.search.meilisearch.host
                # API Key is optional
                meili_key = getattr(config.plugins.search.meilisearch, 'api_key', None)
            except AttributeError:
                # Fallback to flattened or default
                meili_host = "http://localhost:7700"
                meili_key = None
                logger.warning("Using default Meilisearch config (config path not found)")

            initialize_search_adapter(
                host=meili_host,
                api_key=meili_key,
                index_name="indexao_documents" # TODO: Make configurable
            )
            logger.info(f"✓ Search API initialized (Meilisearch at {meili_host})")
        except Exception as e:
            logger.warning(f"Failed to initialize search API: {e}")
        
        logger.info("✓ Web UI ready")
    except Exception as e:
        logger.error(f"Failed to start Web UI: {e}")
        raise


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Redirect root to search page (new home)."""
    return RedirectResponse(url="/search", status_code=302)


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Upload page interface."""
    config = get_config()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Indexao - Document Indexing",
        "version": "0.4.0",
        "config": {
            "ocr_engine": config.plugins.ocr.engine,
            "translator_engine": config.plugins.translator.engine,
            "search_engine": config.plugins.search.engine,
            "languages": config.plugins.ocr.languages
        }
    })


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration viewer page."""
    config = get_config()
    return templates.TemplateResponse("config.html", {
        "request": request,
        "title": "Configuration",
        "version": "0.4.0",
        "config": config
    })


@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request):
    """Documents list page."""
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "title": "Documents - Indexao",
        "version": "0.4.0"
    })


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Search page - now the home page."""
    return templates.TemplateResponse("search.html", {
        "request": request,
        "title": "Search - Indexao",
        "version": "0.4.0"
    })


@app.get("/search/results", response_class=HTMLResponse)
async def search_results(
    request: Request,
    q: str = Query(..., description="Search query"),
    lang: Optional[str] = Query(None)
):
    """HTMX endpoint for search results."""
    from indexao.search_routes import get_search_adapter
    try:
        adapter = get_search_adapter()
        # Ensure q is not empty
        if not q.strip():
            return HTMLResponse("")
            
        results = adapter.search(query=q, language=lang, limit=25)
        return templates.TemplateResponse("components/search_results.html", {
            "request": request,
            "results": results
        })
    except Exception as e:
        logger.error(f"Search error: {e}")
        return HTMLResponse(f"<div class='alert alert-danger'>Error: {e}</div>")


@app.get("/doc/{doc_id}", response_class=HTMLResponse)
async def document_reader(request: Request, doc_id: str):
    """Document reader page."""
    from indexao.search_routes import get_search_adapter
    try:
        adapter = get_search_adapter()
        doc = adapter.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Ensure minimal fields for template
        if not doc.get('title'): doc['title'] = doc.get('filename', 'Untitled')
        
        return templates.TemplateResponse("reader.html", {
            "request": request,
            "doc": doc
        })
    except Exception as e:
        logger.error(f"Reader error: {e}")
        # Mock document for testing layout if search fails
        if request.query_params.get("mock"):
             return templates.TemplateResponse("reader.html", {
                "request": request,
                "doc": {
                    "doc_id": doc_id,
                    "title": "Mock Document",
                    "language": "en",
                    "content_html": "<p>This is a <b>mock</b> document.</p>" * 20
                }
            })
        raise HTTPException(status_code=404, detail="Document not found")


@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    """Real-time monitoring page."""
    return templates.TemplateResponse("monitoring.html", {
        "request": request,
        "title": "Monitoring - Indexao",
        "version": "0.4.0"
    })


@app.get("/api/config")
async def get_config_api() -> Dict[str, Any]:
    """Get current configuration as JSON."""
    config = get_config()
    return {
        "logging": {
            "level": config.logging.level,
            "console_enabled": config.logging.console_enabled,
            "file_enabled": config.logging.file_enabled,
            "log_dir": config.logging.log_dir
        },
        "paths": {
            "input_dir": config.input_dir,
            "output_dir": config.output_dir,
            "temp_dir": config.temp_dir,
            "cache_enabled": config.paths.cache_enabled,
            "cache_ttl_seconds": config.paths.cache_ttl_seconds,
            "retry_enabled": config.paths.retry_enabled,
            "retry_attempts": config.paths.retry_attempts
        },
        "plugins": {
            "ocr": {
                "engine": config.plugins.ocr.engine,
                "languages": config.plugins.ocr.languages,
                "confidence_threshold": config.plugins.ocr.confidence_threshold
            },
            "translator": {
                "engine": config.plugins.translator.engine,
                "source_language": config.plugins.translator.source_language,
                "target_languages": config.plugins.translator.target_languages
            },
            "search": {
                "engine": config.plugins.search.engine,
                "host": config.plugins.search.host,
                "port": config.plugins.search.port,
                "index_name": config.plugins.search.index_name
            }
        }
    }


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload a document for indexing (Fast-Track).
    
    Uses FastTrackService to immediately index the document content
    using a Hash-based ID strategy (Hybrid Indexing).
    
    Args:
        file: Uploaded file
    
    Returns:
        Upload result with document ID and metadata
    """
    try:
        # Validate filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        logger.info(f"Received fast-track upload: {file.filename}")
        
        # Use FastTrack Service
        # Note: We pass the UploadFile directly. The service handles buffering/streaming.
        result = await app.state.fast_track.handle_fast_track(file)
        
        if result['status'] == 'error':
             raise HTTPException(status_code=500, detail=result['message'])

        return {
            "status": "success",
            "document_id": result['doc_id'],
            "filename": file.filename,
            "hash": result['file_hash'],
            "message": result.get('message', 'Document indexé avec succès')
        }
    
    except Exception as e:
        logger.error(f"Fast-Track upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/files")
async def list_files() -> Dict[str, Any]:
    """
    List uploaded files using FileScanner.
    
    Returns file metadata from input directory including queue.
    """
    try:
        config = get_config()
        input_dir = Path(config.input_dir)
        
        if not input_dir.exists():
            return {
                "status": "success",
                "count": 0,
                "files": [],
                "message": "Input directory not found"
            }
        
        # Scan input directory (excluding queue subdirectory)
        scanner = FileScanner(
            root_dir=input_dir,
            recursive=False,  # Don't recurse into _queue
            include_hidden=False
        )
        
        file_metadata = scanner.scan()
        
        # Convert to response format
        files = []
        for meta in file_metadata:
            files.append({
                "filename": meta.filename,
                "size_bytes": meta.size_bytes,
                "modified": meta.modified_at.isoformat(),
                "extension": meta.extension,
                "mime_type": meta.mime_type,
                "path": str(meta.relative_path) if meta.relative_path else meta.filename
            })
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "status": "success",
            "count": len(files),
            "files": files
        }
    
    except Exception as e:
        logger.error(f"Failed to list files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@app.get("/api/scan")
async def scan_input_directory() -> Dict[str, Any]:
    """
    Scan input directory and return statistics.
    
    Returns detailed scan summary with file counts and sizes.
    """
    try:
        config = get_config()
        input_dir = Path(config.input_dir)
        
        if not input_dir.exists():
            raise HTTPException(status_code=404, detail="Input directory not found")
        
        # Create scanner with common document extensions
        scanner = FileScanner(
            root_dir=input_dir,
            recursive=True,
            include_hidden=False,
            allowed_extensions={
                '.txt', '.md', '.pdf', '.doc', '.docx',
                '.jpg', '.jpeg', '.png', '.tiff', '.gif',
                '.csv', '.json', '.xml', '.html'
            }
        )
        
        summary = scanner.get_summary()
        
        return {
            "status": "success",
            "summary": summary
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@app.get("/api/queue")
async def list_queue() -> Dict[str, Any]:
    """
    List files in processing queue.
    
    Returns files waiting to be processed.
    """
    try:
        upload_handler: UploadHandler = app.state.upload_handler
        queue_files = upload_handler.list_queue()
        
        files = []
        for file_path in queue_files:
            stat = file_path.stat()
            # Extract document ID from filename (DOC_XXXXXXXX_...)
            parts = file_path.name.split('_', 2)
            doc_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else "UNKNOWN"
            
            files.append({
                "document_id": doc_id,
                "filename": file_path.name,
                "size_bytes": stat.st_size,
                "queued_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        # Sort by queue time (oldest first - FIFO)
        files.sort(key=lambda x: x["queued_at"])
        
        return {
            "status": "success",
            "count": len(files),
            "files": files
        }
    
    except Exception as e:
        logger.error(f"Failed to list queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list queue: {str(e)}")


@app.post("/api/process")
async def process_documents() -> Dict[str, Any]:
    """
    Process all documents in the queue.
    
    Triggers the complete pipeline:
    - Scan queue directory
    - Process each file (OCR → Translation → Indexing)
    - Return processing results
    
    Returns:
        JSON with processing results for each file
    """
    try:
        logger.info("Processing queue via API request")
        
        processor: DocumentProcessor = app.state.processor
        
        # Process all files in queue
        results = processor.process_queue()
        
        if not results:
            return {
                "status": "success",
                "message": "Queue is empty",
                "processed": 0,
                "results": []
            }
        
        # Convert results to dict
        results_data = [r.to_dict() for r in results]
        
        # Count successes and failures
        completed = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
        
        return {
            "status": "success",
            "message": f"Processed {len(results)} documents",
            "processed": len(results),
            "completed": completed,
            "failed": failed,
            "results": results_data
        }
    
    except Exception as e:
        logger.error(f"Failed to process queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process queue: {str(e)}")


@app.post("/api/process/{document_id}")
async def process_single_document(document_id: str) -> Dict[str, Any]:
    """
    Process a single document from the queue.
    
    Args:
        document_id: Document ID (e.g., DOC_FDABB347)
        
    Returns:
        JSON with processing result
    """
    try:
        logger.info(f"Processing single document: {document_id}")
        
        processor: DocumentProcessor = app.state.processor
        upload_handler: UploadHandler = app.state.upload_handler
        
        # Find file in queue
        queue_files = upload_handler.list_queue()
        matching_files = [f for f in queue_files if document_id in f.name]
        
        if not matching_files:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found in queue"
            )
        
        file_path = matching_files[0]
        
        # Get metadata
        from .scanner import FileScanner
        scanner = FileScanner(file_path.parent, recursive=False)
        
        # Scan and find matching file by name
        all_metadata = scanner.scan()
        metadata = None
        
        for m in all_metadata:
            if m.filename == file_path.name:
                metadata = m
                break
        
        if not metadata:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get metadata for {document_id}"
            )
        
        # Process file
        result = processor.process_file(file_path, metadata)
        
        return {
            "status": "success",
            "result": result.to_dict()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@app.get("/api/processor/status")
async def get_processor_status() -> Dict[str, Any]:
    """
    Get processor status and statistics.
    
    Returns:
        JSON with processor information
    """
    try:
        processor: DocumentProcessor = app.state.processor
        summary = processor.get_status_summary()
        
        return {
            "status": "success",
            **summary
        }
    
    except Exception as e:
        logger.error(f"Failed to get processor status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        config = get_config()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "config_loaded": True,
            "ocr_engine": config.plugins.ocr.engine,
            "search_engine": config.plugins.search.engine
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@app.get("/api/documents")
async def list_documents(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List documents from database.
    
    Query params:
        status: Filter by processing status (pending, completed, failed)
        limit: Maximum number of results (default: 100)
        offset: Offset for pagination (default: 0)
    """
    try:
        config = get_config()
        db = DocumentDatabase(str(config.db_path))
        
        # Parse status filter
        doc_status = None
        if status:
            try:
                doc_status = DocStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Valid values: pending, processing, completed, failed"
                )
        
        # Get documents
        documents = db.list_documents(status=doc_status, limit=limit, offset=offset)
        total = db.count_documents(status=doc_status)
        
        # Convert to dict
        results = []
        for doc in documents:
            doc_dict = doc.to_dict()
            # Add shortened content preview
            doc_dict["content_preview"] = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
            del doc_dict["content"]  # Remove full content for list view
            results.append(doc_dict)
        
        return {
            "status": "success",
            "total": total,
            "count": len(results),
            "limit": limit,
            "offset": offset,
            "documents": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str) -> Dict[str, Any]:
    """
    Get a specific document by ID.
    
    Args:
        doc_id: Document ID
    """
    try:
        config = get_config()
        db = DocumentDatabase(str(config.db_path))
        document = db.get_document(doc_id)
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
        
        return {
            "status": "success",
            "document": document.to_dict()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_statistics() -> Dict[str, Any]:
    """Get database statistics."""
    try:
        config = get_config()
        db = DocumentDatabase(str(config.db_path))
        
        total = db.count_documents()
        completed = db.count_documents(DocStatus.COMPLETED)
        failed = db.count_documents(DocStatus.FAILED)
        pending = db.count_documents(DocStatus.PENDING)
        
        queue_stats = db.get_queue_stats()
        
        return {
            "status": "success",
            "documents": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "pending": pending,
                "success_rate": round(completed / total * 100, 1) if total > 0 else 0
            },
            "queue": queue_stats
        }
    
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Meilisearch Proxy API Routes
# =============================================================================

@app.get("/api/meilisearch/indexes")
async def meilisearch_list_indexes():
    """List all Meilisearch indexes."""
    config = get_config()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{config.plugins.search.host}:{config.plugins.search.port}/indexes",
                headers={"Authorization": f"Bearer {config.plugins.search.api_key}"}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error listing Meilisearch indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/meilisearch/indexes")
async def meilisearch_create_index(request: Request):
    """Create a new Meilisearch index."""
    config = get_config()
    
    try:
        body = await request.json()
        uid = body.get("uid")
        primaryKey = body.get("primaryKey")
        
        if not uid:
            raise HTTPException(status_code=400, detail="uid is required")
        
        payload = {"uid": uid}
        if primaryKey:
            payload["primaryKey"] = primaryKey
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://{config.plugins.search.host}:{config.plugins.search.port}/indexes",
                json=payload,
                headers={"Authorization": f"Bearer {config.plugins.search.api_key}"}
            )
            response.raise_for_status()
            return response.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Meilisearch index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/meilisearch/indexes/{index_uid}")
async def meilisearch_get_index(index_uid: str):
    """Get Meilisearch index details."""
    config = get_config()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{config.plugins.search.host}:{config.plugins.search.port}/indexes/{index_uid}",
                headers={"Authorization": f"Bearer {config.plugins.search.api_key}"}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error getting Meilisearch index {index_uid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/meilisearch/indexes/{index_uid}")
async def meilisearch_delete_index(index_uid: str):
    """Delete a Meilisearch index."""
    config = get_config()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"http://{config.plugins.search.host}:{config.plugins.search.port}/indexes/{index_uid}",
                headers={"Authorization": f"Bearer {config.plugins.search.api_key}"}
            )
            response.raise_for_status()
            return {"status": "success", "message": f"Index {index_uid} deleted"}
    except Exception as e:
        logger.error(f"Error deleting Meilisearch index {index_uid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/meilisearch/indexes/{index_uid}")
async def meilisearch_update_index(index_uid: str, request: Request):
    """Update Meilisearch index settings (searchable/filterable attributes)."""
    config = get_config()
    
    try:
        body = await request.json()
        
        async with httpx.AsyncClient() as client:
            # Update searchable attributes if provided
            if "searchableAttributes" in body:
                response = await client.patch(
                    f"http://{config.plugins.search.host}:{config.plugins.search.port}/indexes/{index_uid}/settings/searchable-attributes",
                    json=body["searchableAttributes"],
                    headers={"Authorization": f"Bearer {config.plugins.search.api_key}"}
                )
                response.raise_for_status()
            
            # Update filterable attributes if provided
            if "filterableAttributes" in body:
                response = await client.patch(
                    f"http://{config.plugins.search.host}:{config.plugins.search.port}/indexes/{index_uid}/settings/filterable-attributes",
                    json=body["filterableAttributes"],
                    headers={"Authorization": f"Bearer {config.plugins.search.api_key}"}
                )
                response.raise_for_status()
            
            return {"status": "success", "message": f"Index {index_uid} updated"}
    except Exception as e:
        logger.error(f"Error updating Meilisearch index {index_uid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Cloud Volumes Management API Routes
# =============================================================================

@app.get("/api/cloud/volumes")
async def list_cloud_volumes():
    """List all configured cloud volumes."""
    try:
        from indexao.cloud_indexer import setup_default_volumes
        indexer = setup_default_volumes()
        
        volumes_data = []
        for name, volume in indexer.state.volumes.items():
            volumes_data.append({
                "name": volume.name,
                "mount_path": volume.mount_path,
                "index_name": volume.index_name,
                "enabled": volume.enabled,
                "is_mounted": indexer.is_mounted(volume),
                "total_files": volume.total_files,
                "indexed_files": volume.indexed_files,
                "last_scan": volume.last_scan,
                "progress": round(volume.indexed_files / volume.total_files * 100, 1) if volume.total_files > 0 else 0
            })
        
        return {"volumes": volumes_data}
    
    except Exception as e:
        logger.error(f"Error listing cloud volumes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cloud/volumes")
async def add_cloud_volume(request: Request):
    """Add a new cloud volume."""
    try:
        from indexao.cloud_indexer import CloudIndexer
        from pathlib import Path
        
        body = await request.json()
        name = body.get("name")
        mount_path = body.get("mount_path")
        index_name = body.get("index_name")
        
        if not all([name, mount_path, index_name]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Validate path exists
        if not Path(mount_path).exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {mount_path}")
        
        indexer = CloudIndexer()
        volume = indexer.add_volume(
            name=name,
            mount_path=mount_path,
            index_name=index_name,
            file_patterns=body.get("file_patterns"),
            exclude_patterns=body.get("exclude_patterns")
        )
        
        return {
            "status": "success",
            "volume": {
                "name": volume.name,
                "mount_path": volume.mount_path,
                "index_name": volume.index_name
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding cloud volume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cloud/volumes/{volume_name}/scan")
async def scan_cloud_volume(volume_name: str):
    """Trigger a scan of a specific cloud volume (asynchronous)."""
    try:
        from indexao.cloud_indexer import setup_default_volumes
        
        # Check if scan already running
        with _scan_lock:
            if volume_name in _active_scans:
                return {
                    "status": "already_running",
                    "message": f"Scan already in progress for {volume_name}",
                    "scan_info": _active_scans[volume_name]
                }
        
        indexer = setup_default_volumes()
        
        volume = indexer.state.volumes.get(volume_name)
        if not volume:
            raise HTTPException(status_code=404, detail=f"Volume not found: {volume_name}")
        
        if not indexer.is_mounted(volume):
            raise HTTPException(status_code=400, detail=f"Volume not mounted: {volume_name}")
        
        # Mark scan as active
        with _scan_lock:
            _active_scans[volume_name] = {
                "started_at": datetime.now().isoformat(),
                "status": "running",
                "progress": 0,
                "total": volume.total_files
            }
        
        # Start scan in background thread
        def run_scan():
            try:
                logger.info(f"Starting background scan for {volume_name}")
                result = indexer.index_volume_progressive(volume)
                
                with _scan_lock:
                    _active_scans[volume_name]["status"] = "completed"
                    _active_scans[volume_name]["completed_at"] = datetime.now().isoformat()
                    _active_scans[volume_name]["result"] = result
                
                logger.info(f"✓ Background scan completed for {volume_name}: {result}")
            except Exception as e:
                logger.error(f"Error in background scan for {volume_name}: {e}")
                with _scan_lock:
                    _active_scans[volume_name]["status"] = "error"
                    _active_scans[volume_name]["error"] = str(e)
        
        thread = threading.Thread(target=run_scan, daemon=True)
        thread.start()
        
        return {
            "status": "started",
            "message": f"Scan started for {volume_name}",
            "volume": volume_name,
            "scan_info": _active_scans[volume_name]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scanning cloud volume {volume_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cloud/volumes/{volume_name}/scan/status")
async def get_scan_status(volume_name: str):
    """Get the status of an ongoing or completed scan."""
    with _scan_lock:
        if volume_name not in _active_scans:
            return {
                "status": "no_scan",
                "message": "No scan in progress or completed recently"
            }
        return _active_scans[volume_name]


@app.delete("/api/cloud/volumes/{volume_name}")
async def delete_cloud_volume(volume_name: str):
    """Remove a cloud volume from configuration."""
    try:
        from indexao.cloud_indexer import CloudIndexer
        indexer = CloudIndexer()
        
        if volume_name not in indexer.state.volumes:
            raise HTTPException(status_code=404, detail=f"Volume not found: {volume_name}")
        
        del indexer.state.volumes[volume_name]
        indexer.state.save()
        
        return {"status": "success", "message": f"Volume {volume_name} removed"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cloud volume {volume_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/browse")
async def browse_system(path: str = "."):
    """List directories for browsing."""
    try:
        from pathlib import Path
        import os
        
        # Security: Basic check to prevent escaping if needed? 
        # For a local tool running as user, we usually want access to all user files.
        
        if path == "." or path == "":
            p = Path.home()
        else:
            p = Path(path).resolve()
            
        if not p.exists():
             raise HTTPException(status_code=404, detail="Path does not exist")
        
        if not p.is_dir():
             p = p.parent

        items = []
        try:
            # Add parent navigation
            if p.parent != p:
                 items.append({
                    "name": "..",
                    "path": str(p.parent),
                    "type": "dir"
                })

            for entry in os.scandir(p):
                if entry.is_dir() and not entry.name.startswith('.'):
                    items.append({
                        "name": entry.name,
                        "path": entry.path,
                        "type": "dir"
                    })
        except PermissionError:
             pass
            
        items.sort(key=lambda x: x['name'].lower())
        
        return {
            "current": str(p),
            "items": items
        }
    except Exception as e:
        logger.error(f"Browse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Real-Time Monitoring API
# ============================================================================

@app.get("/api/monitoring/realtime")
async def get_realtime_monitoring():
    """Get comprehensive real-time monitoring data."""
    try:
        from indexao.database import DocumentDatabase
        
        # Meilisearch status
        meilisearch_data = {}
        meilisearch_url = "http://localhost:7700"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Health check
                health_resp = await client.get(f"{meilisearch_url}/health")
                meilisearch_data["status"] = "available" if health_resp.status_code == 200 else "unavailable"
                meilisearch_data["url"] = meilisearch_url
                
                # Version
                version_resp = await client.get(f"{meilisearch_url}/version")
                if version_resp.status_code == 200:
                    version_data = version_resp.json()
                    meilisearch_data["version"] = version_data.get("pkgVersion", "N/A")
                
                # Indexes with stats
                indexes_resp = await client.get(f"{meilisearch_url}/indexes")
                indexes = []
                total_docs = 0
                
                if indexes_resp.status_code == 200:
                    indexes_data = indexes_resp.json()
                    for idx in indexes_data.get("results", []):
                        stats_resp = await client.get(f"{meilisearch_url}/indexes/{idx['uid']}/stats")
                        if stats_resp.status_code == 200:
                            stats = stats_resp.json()
                            idx["numberOfDocuments"] = stats.get("numberOfDocuments", 0)
                            idx["isIndexing"] = stats.get("isIndexing", False)
                            total_docs += idx["numberOfDocuments"]
                        indexes.append(idx)
                
                meilisearch_data["indexes"] = indexes
                meilisearch_data["total_documents"] = total_docs
        except Exception as e:
            logger.error(f"Error getting Meilisearch data: {e}")
            meilisearch_data["status"] = "error"
            meilisearch_data["error"] = str(e)
        
        # Queue statistics
        db = DocumentDatabase()
        queue_stats = {}
        try:
            with db._connection() as conn:
                # Global stats
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count
                    FROM index_queue
                    GROUP BY status
                """)
                global_stats = {"total": 0, "done": 0, "pending": 0, "processing": 0, "error": 0}
                for row in cursor:
                    status = row["status"]
                    count = row["count"]
                    global_stats[status] = count
                    global_stats["total"] += count
                
                # Per volume stats
                cursor = conn.execute("""
                    SELECT volume, status, COUNT(*) as count
                    FROM index_queue
                    GROUP BY volume, status
                    ORDER BY volume
                """)
                by_volume = {}
                for row in cursor:
                    volume = row["volume"]
                    status = row["status"]
                    count = row["count"]
                    
                    if volume not in by_volume:
                        by_volume[volume] = {"total": 0, "done": 0, "pending": 0, "processing": 0, "error": 0}
                    
                    by_volume[volume][status] = count
                    by_volume[volume]["total"] += count
                
                queue_stats = {
                    **global_stats,
                    "by_volume": by_volume
                }
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            queue_stats["error"] = str(e)
        
        # Active scans
        active_scans = {}
        with _scan_lock:
            active_scans = {k: v for k, v in _active_scans.items() if v.get("status") == "running"}
        
        return {
            "meilisearch": meilisearch_data,
            "indexes": meilisearch_data.get("indexes", []),
            "total_documents": meilisearch_data.get("total_documents", 0),
            "queue": queue_stats,
            "active_scans": active_scans,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in realtime monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Framework Management API Routes
# ============================================================================

@app.get("/api/frameworks/status")
async def get_frameworks_status():
    """Get status of all managed frameworks (JS/CSS libraries)."""
    try:
        manager = get_framework_manager()
        status = manager.get_status()
        return {"frameworks": status}
    except Exception as e:
        logger.error(f"Error getting frameworks status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/frameworks/download")
async def download_frameworks(frameworks: Optional[list] = None):
    """
    Download frameworks from CDN to local storage.
    
    Args:
        frameworks: List of framework keys to download (None = all)
    """
    try:
        manager = get_framework_manager()
        
        if frameworks:
            # Download specific frameworks
            results = {}
            for fw_key in frameworks:
                results[fw_key] = manager.download_framework(fw_key)
        else:
            # Download all
            results = manager.download_all()
        
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        return {
            "status": "success" if success_count == total_count else "partial",
            "downloaded": success_count,
            "total": total_count,
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Error downloading frameworks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/frameworks/check-updates")
async def check_framework_updates():
    """Check which frameworks need updates."""
    try:
        manager = get_framework_manager()
        needs_update = manager.check_updates()
        
        return {
            "needs_update": needs_update,
            "count": len(needs_update)
        }
    
    except Exception as e:
        logger.error(f"Error checking framework updates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: Optional[str] = None, port: Optional[int] = None, reload: bool = None):
    """
    Run the web server.
    
    Args:
        host: Host to bind to (overrides config)
        port: Port to bind to (overrides config)
        reload: Enable auto-reload on code changes (overrides config)
    """
    # Ensure config is loaded
    try:
        config = get_config()
    except RuntimeError:
        config = load_config()
        
    final_host = host or config.api.host
    final_port = port or config.api.port
    final_reload = reload if reload is not None else config.api.reload

    logger.info(f"Starting web server on http://{final_host}:{final_port}")
    uvicorn.run(
        "indexao.webui:app",
        host=final_host,
        port=final_port,
        reload=final_reload,
        log_level=config.logging.level.lower()
    )


if __name__ == "__main__":
    # Development mode - configuration loaded automatically
    run_server(reload=True)
