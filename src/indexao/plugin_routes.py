"""Plugin API Routes - REST endpoints for plugin management"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from indexao.logger import get_logger
from indexao.plugin_manager import PluginManager, PluginMetadata

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/plugins", tags=["plugins"])

# Global plugin manager instance (will be set by main.py)
_plugin_manager: Optional[PluginManager] = None


def set_plugin_manager(manager: PluginManager):
    """Set global plugin manager instance"""
    global _plugin_manager
    _plugin_manager = manager


def get_plugin_manager() -> PluginManager:
    """Get plugin manager instance"""
    if _plugin_manager is None:
        raise RuntimeError("Plugin manager not initialized")
    return _plugin_manager


# Request/Response Models
class SwitchRequest(BaseModel):
    """Request to switch adapter"""
    adapter_type: str
    adapter_name: str


class PluginInfo(BaseModel):
    """Plugin information"""
    name: str
    type: str
    version: str
    description: str
    enabled: bool
    priority: int


class ActiveAdapter(BaseModel):
    """Active adapter info"""
    type: str
    name: Optional[str]


# API Endpoints

@router.get("/", response_model=List[PluginInfo])
async def list_plugins(adapter_type: Optional[str] = None):
    """
    List all available plugins
    
    Args:
        adapter_type: Optional filter by type (ocr, translator, search)
    
    Returns:
        List of plugin metadata
    
    Example:
        GET /api/plugins
        GET /api/plugins?adapter_type=ocr
    """
    try:
        manager = get_plugin_manager()
        
        # Discover plugins
        types_filter = [adapter_type] if adapter_type else None
        plugins = manager.discover_plugins(adapter_types=types_filter)
        
        # Convert to response model
        return [
            PluginInfo(
                name=p.name,
                type=p.type,
                version=p.version,
                description=p.description,
                enabled=p.enabled,
                priority=p.priority
            )
            for p in plugins
        ]
    
    except Exception as e:
        logger.error(f"Failed to list plugins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=List[ActiveAdapter])
async def get_active_adapters():
    """
    Get currently active adapters
    
    Returns:
        List of active adapters per type
    
    Example:
        GET /api/plugins/active
        Response: [
            {"type": "ocr", "name": "tesseract"},
            {"type": "translator", "name": "mock"},
            {"type": "search", "name": null}
        ]
    """
    try:
        manager = get_plugin_manager()
        active = manager.list_active()
        
        return [
            ActiveAdapter(type=adapter_type, name=name)
            for adapter_type, name in active.items()
        ]
    
    except Exception as e:
        logger.error(f"Failed to get active adapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{adapter_type}/active", response_model=ActiveAdapter)
async def get_active_adapter(adapter_type: str):
    """
    Get active adapter for specific type
    
    Args:
        adapter_type: Type (ocr, translator, search)
    
    Returns:
        Active adapter info
    
    Example:
        GET /api/plugins/ocr/active
        Response: {"type": "ocr", "name": "tesseract"}
    """
    if adapter_type not in ['ocr', 'translator', 'search']:
        raise HTTPException(status_code=400, detail=f"Invalid adapter_type: {adapter_type}")
    
    try:
        manager = get_plugin_manager()
        active = manager.list_active()
        
        return ActiveAdapter(
            type=adapter_type,
            name=active.get(adapter_type)
        )
    
    except Exception as e:
        logger.error(f"Failed to get active adapter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch")
async def switch_adapter(request: SwitchRequest):
    """
    Switch to different adapter (hot-swap)
    
    Args:
        request: Switch request with type and name
    
    Returns:
        Success message
    
    Example:
        POST /api/plugins/switch
        Body: {"adapter_type": "ocr", "adapter_name": "tesseract"}
        Response: {"status": "success", "message": "Switched to ocr/tesseract"}
    """
    if request.adapter_type not in ['ocr', 'translator', 'search']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid adapter_type: {request.adapter_type}"
        )
    
    try:
        manager = get_plugin_manager()
        
        # Check if adapter exists in registry
        available = manager.list_available(request.adapter_type)
        if request.adapter_name not in available:
            # Try to load it dynamically
            logger.info(f"Adapter not registered, attempting dynamic load: {request.adapter_type}/{request.adapter_name}")
            try:
                manager.load_adapter(
                    request.adapter_type,
                    request.adapter_name,
                    auto_register=True,
                    fallback_to_mock=True
                )
            except Exception as load_error:
                raise HTTPException(
                    status_code=404,
                    detail=f"Adapter not found and failed to load: {request.adapter_name}"
                )
        else:
            # Switch to existing adapter
            manager.switch(request.adapter_type, request.adapter_name)
        
        logger.info(f"Switched to {request.adapter_type}/{request.adapter_name}")
        
        return {
            "status": "success",
            "message": f"Switched to {request.adapter_type}/{request.adapter_name}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch adapter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/registered")
async def get_registered_adapters():
    """
    Get all registered adapters (in memory)
    
    Returns:
        Dict of registered adapters by type
    
    Example:
        GET /api/plugins/registered
        Response: {
            "ocr": ["mock", "tesseract"],
            "translator": ["mock"],
            "search": []
        }
    """
    try:
        manager = get_plugin_manager()
        
        registered = {
            'ocr': manager.list_available('ocr'),
            'translator': manager.list_available('translator'),
            'search': manager.list_available('search')
        }
        
        return registered
    
    except Exception as e:
        logger.error(f"Failed to get registered adapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_switch_history(adapter_type: Optional[str] = None):
    """
    Get adapter switch history
    
    Args:
        adapter_type: Optional filter by type
    
    Returns:
        List of switch events
    
    Example:
        GET /api/plugins/history
        GET /api/plugins/history?adapter_type=ocr
    """
    try:
        manager = get_plugin_manager()
        history = manager.get_switch_history(adapter_type=adapter_type)
        
        return {"history": history}
    
    except Exception as e:
        logger.error(f"Failed to get switch history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
