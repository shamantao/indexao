"""API Routes for Document Processing Pipeline

Endpoints pour traiter des documents via le pipeline OCR → Search.
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from indexao.adapters.ocr import TesseractOCR, MockOCRAdapter
from indexao.adapters.search import MeilisearchAdapter, MockSearchAdapter
from indexao.pipeline import DocumentProcessor


router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# Global processor instance (initialized on startup)
_processor: Optional[DocumentProcessor] = None


class ProcessDirectoryRequest(BaseModel):
    """Requête pour traiter un répertoire"""
    directory: str
    language: str = "fra+eng+chi_tra"
    recursive: bool = True
    filter_pattern: Optional[str] = None


class ProcessFileRequest(BaseModel):
    """Requête pour traiter un fichier unique"""
    file_path: str
    language: str = "fra+eng+chi_tra"


def initialize_processor(use_real_adapters: bool = True):
    """Initialise le processeur global.
    
    Args:
        use_real_adapters: True = Tesseract + Meilisearch, False = Mocks
    """
    global _processor
    
    if use_real_adapters:
        ocr = TesseractOCR()
        search = MeilisearchAdapter(index_name="indexao_documents")
    else:
        ocr = MockOCRAdapter()
        search = MockSearchAdapter()
    
    _processor = DocumentProcessor(ocr_adapter=ocr, search_adapter=search)


@router.get("/status")
async def get_pipeline_status():
    """Vérifie le statut du pipeline."""
    if _processor is None:
        raise HTTPException(status_code=503, detail="Pipeline non initialisé")
    
    stats = _processor.get_statistics()
    
    return {
        "status": "ready",
        "ocr_engine": _processor.ocr.name,
        "search_backend": _processor.search.name,
        "statistics": stats
    }


@router.post("/process/directory")
async def process_directory(
    request: ProcessDirectoryRequest,
    background_tasks: BackgroundTasks
):
    """Traite tous les documents d'un répertoire.
    
    Process en background avec callback de progression.
    """
    if _processor is None:
        raise HTTPException(status_code=503, detail="Pipeline non initialisé")
    
    directory = Path(request.directory)
    
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=404, detail=f"Répertoire introuvable: {request.directory}")
    
    # Fonction de traitement en background
    def process_in_background():
        results = _processor.process_directory(
            directory=directory,
            language=request.language,
            recursive=request.recursive,
            filter_pattern=request.filter_pattern
        )
        # TODO: Sauvegarder les résultats ou notifier via WebSocket
        print(f"Traitement terminé: {results}")
    
    # Lancer en background
    background_tasks.add_task(process_in_background)
    
    return {
        "status": "processing",
        "message": f"Traitement de {request.directory} lancé en arrière-plan",
        "directory": str(directory)
    }


@router.post("/process/file")
async def process_file(request: ProcessFileRequest):
    """Traite un fichier unique."""
    if _processor is None:
        raise HTTPException(status_code=503, detail="Pipeline non initialisé")
    
    file_path = Path(request.file_path)
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Fichier introuvable: {request.file_path}")
    
    # Traiter le fichier
    success = _processor.process_file(file_path, language=request.language)
    
    if success:
        return {
            "status": "success",
            "message": f"Fichier {file_path.name} traité et indexé",
            "file": str(file_path)
        }
    else:
        raise HTTPException(status_code=500, detail="Échec du traitement")


@router.get("/statistics")
async def get_statistics():
    """Récupère les statistiques de l'index."""
    if _processor is None:
        raise HTTPException(status_code=503, detail="Pipeline non initialisé")
    
    return _processor.get_statistics()
