"""
Search API Routes for Indexao
Uses Meilisearch adapter for multilingual search
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging

from .adapters.search import MeilisearchAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# Global search adapter instance (initialized at startup)
_search_adapter: Optional[MeilisearchAdapter] = None


def initialize_search_adapter(host: str = "http://localhost:7700", api_key: Optional[str] = None, index_name: str = "documents"):
    """
    Initialize the global search adapter instance
    
    Args:
        host: Meilisearch server URL
        api_key: Optional Meilisearch API key
        index_name: Name of the index to search
    """
    global _search_adapter
    
    try:
        _search_adapter = MeilisearchAdapter(
            host=host,
            api_key=api_key,
            index_name=index_name
        )
        logger.info(f"✓ Search adapter initialized (Meilisearch at {host})")
    except Exception as e:
        logger.error(f"✗ Failed to initialize search adapter: {e}")
        raise


def get_search_adapter() -> MeilisearchAdapter:
    """Get the global search adapter instance"""
    if _search_adapter is None:
        raise HTTPException(
            status_code=503,
            detail="Search service not initialized"
        )
    return _search_adapter


@router.get("/")
async def search_documents(
    query: str = Query(..., description="Search query"),
    language: Optional[str] = Query(None, description="Filter by language: fr, en, zh-TW"),
    limit: int = Query(25, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Results offset for pagination")
):
    """
    Search documents using Meilisearch
    
    Supports multilingual search across FR, EN, ZH-TW documents
    
    Example:
        GET /api/search?query=contract&language=en&limit=10
    """
    try:
        adapter = get_search_adapter()
        
        # Build filters
        filters = []
        if language:
            filters.append(f'language = "{language}"')
        
        filter_str = " AND ".join(filters) if filters else None
        
        # Perform search (NOT async)
        results = adapter.search(
            query=query,
            limit=limit,
            offset=offset,
            language=language
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document/{doc_id}")
async def get_document(doc_id: str):
    """
    Get a specific document by ID
    
    Useful for copying full text or viewing document details
    """
    try:
        adapter = get_search_adapter()
        document = adapter.get_document(doc_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_search_stats():
    """
    Get index statistics
    
    Returns total document count and breakdown by language
    """
    try:
        adapter = get_search_adapter()
        
        # Get all documents to compute stats (NOT async)
        all_docs = adapter.search(query="", limit=10000)
        
        stats = {
            "total_documents": len(all_docs),
            "by_language": {
                "fr": 0,
                "en": 0,
                "zh-TW": 0
            }
        }
        
        for doc in all_docs:
            lang = doc.language if hasattr(doc, 'language') else "unknown"
            if lang in stats["by_language"]:
                stats["by_language"][lang] += 1
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/index")
async def clear_index():
    """
    Clear all documents from the search index
    
    WARNING: This will delete all indexed documents!
    """
    try:
        adapter = get_search_adapter()
        
        # Delete all documents
        all_docs = adapter.search(query="", limit=10000)
        
        deleted_count = 0
        for doc in all_docs:
            doc_id = doc.doc_id if hasattr(doc, 'doc_id') else None
            if doc_id:
                adapter.delete_document(doc_id)
                deleted_count += 1
        
        return {
            "status": "success",
            "deleted_documents": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Failed to clear index: {e}")
        raise HTTPException(status_code=500, detail=str(e))
