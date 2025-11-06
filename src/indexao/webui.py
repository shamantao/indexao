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
    
    Args:
        file: Uploaded file
    
    Returns:
        Upload status and file info
    """
    try:
        config = get_config()
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check file extension
        allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".txt"}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type {file_ext} not allowed. Allowed: {allowed_extensions}"
            )
        
        # Save file to input directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = Path(config.input_dir) / safe_filename
        
        # Write file
        content = await file.read()
        file_path.write_bytes(content)
        
        logger.info(f"Uploaded file: {file_path} ({len(content)} bytes)")
        
        return {
            "status": "success",
            "filename": safe_filename,
            "original_filename": file.filename,
            "size_bytes": len(content),
            "path": str(file_path),
            "message": "File uploaded successfully. Processing will start shortly."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/files")
async def list_files() -> Dict[str, Any]:
    """List uploaded files in input directory."""
    try:
        config = get_config()
        input_dir = Path(config.input_dir)
        
        files = []
        if input_dir.exists():
            for file_path in input_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        "filename": file_path.name,
                        "size_bytes": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "extension": file_path.suffix
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
