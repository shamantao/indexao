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

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from indexao.config import load_config, get_config, Config
from indexao.logger import get_logger
from indexao.upload_handler import UploadHandler, UploadError
from indexao.scanner import FileScanner, scan_directory
from indexao.processor import DocumentProcessor, ProcessingStatus
from indexao.database import DocumentDatabase
from indexao.models.document import ProcessingStatus as DocStatus
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


@app.on_event("startup")
async def startup_event():
    """Initialize configuration on startup."""
    try:
        logger.info("Starting Indexao Web UI...")
        config = load_config()
        logger.info(f"Configuration loaded: {config}")
        
        # Create required directories
        Path(config.input_dir).mkdir(parents=True, exist_ok=True)
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        Path(config.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize upload handler
        app.state.upload_handler = UploadHandler(config)
        
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
            initialize_search_adapter(
                host=f"http://{config.plugins.search.host}:{config.plugins.search.port}",
                api_key=config.plugins.search.api_key,
                index_name=config.plugins.search.index_name
            )
            logger.info("✓ Search API initialized (Meilisearch)")
        except Exception as e:
            logger.warning(f"Failed to initialize search API: {e}")
        
        logger.info("✓ Web UI ready")
    except Exception as e:
        logger.error(f"Failed to start Web UI: {e}")
        raise


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with upload interface."""
    config = get_config()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Indexao - Document Indexing",
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
        "config": config
    })


@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request):
    """Documents list page."""
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "title": "Documents - Indexao"
    })


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Search page."""
    return templates.TemplateResponse("search.html", {
        "request": request,
        "title": "Search - Indexao"
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
    Upload a document for indexing.
    
    Uses UploadHandler to validate, process, and queue files.
    
    Args:
        file: Uploaded file
    
    Returns:
        Upload result with document ID and metadata
    """
    temp_file = None
    try:
        # Validate filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Save to temporary file
        config = get_config()
        temp_dir = Path(config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        temp_file = temp_dir / f"upload_{datetime.now().timestamp()}_{file.filename}"
        content = await file.read()
        temp_file.write_bytes(content)
        
        logger.info(f"Received upload: {file.filename} ({len(content)} bytes)")
        
        # Process upload using UploadHandler
        upload_handler: UploadHandler = app.state.upload_handler
        result = upload_handler.handle_upload(temp_file, file.filename)
        
        return {
            "status": "success",
            "document_id": result['document_id'],
            "filename": result['metadata']['original_filename'],
            "size_bytes": result['metadata']['size_bytes'],
            "mime_type": result['metadata']['mime_type'],
            "checksum": result['metadata']['checksum'][:16],  # Short version
            "message": result['message']
        }
    
    except UploadError as e:
        logger.warning(f"Upload validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    finally:
        # Clean up temp file if it still exists
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


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
        db = DocumentDatabase("data/indexao.db")
        
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
        db = DocumentDatabase("data/indexao.db")
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
        db = DocumentDatabase("data/indexao.db")
        
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


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Run the web server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload on code changes
    """
    logger.info(f"Starting web server on http://{host}:{port}")
    uvicorn.run(
        "indexao.webui:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    # Development mode
    run_server(host="127.0.0.1", port=8000, reload=True)
