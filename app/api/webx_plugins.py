"""
WebX Plugin Marketplace API
REST API endpoints for plugin management and marketplace functionality
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional, Dict
from pydantic import BaseModel
import tempfile
from pathlib import Path

from ..webx.plugin_manager import get_plugin_manager, PluginMetadata
from ..security.rbac import require_role, get_current_user
from ..utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webx/plugins", tags=["WebX Plugins"])


# Request/Response Models
class PluginSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    verified_only: bool = False
    limit: int = 20


class PluginInstallRequest(BaseModel):
    plugin_id: str
    version: Optional[str] = None


class PluginMetadataResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str
    author: str
    license: str
    homepage: str
    repository: str
    keywords: List[str]
    capabilities: List[str]
    security_level: str
    min_webx_version: str
    max_webx_version: Optional[str]
    dependencies: Dict[str, str]
    created_at: str
    updated_at: str
    download_count: int
    rating: float
    review_count: int
    verified: bool

    @classmethod
    def from_metadata(cls, metadata: PluginMetadata):
        return cls(**metadata.__dict__)


class PluginListResponse(BaseModel):
    plugins: List[PluginMetadataResponse]
    total_count: int
    page: int
    per_page: int


class PluginOperationResponse(BaseModel):
    success: bool
    message: str
    plugin_id: str
    version: Optional[str] = None


# Plugin Discovery Endpoints

@router.get("/", response_model=PluginListResponse)
async def list_plugins(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    verified_only: bool = False,
    current_user=Depends(get_current_user)
):
    """List available plugins in the marketplace"""
    try:
        plugin_manager = get_plugin_manager()

        # Get all plugins
        all_plugins = plugin_manager.registry.list_plugins(
            category=category,
            verified_only=verified_only
        )

        # Pagination
        total_count = len(all_plugins)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_plugins = all_plugins[start_idx:end_idx]

        # Convert to response model
        plugin_responses = [PluginMetadataResponse.from_metadata(p) for p in page_plugins]

        return PluginListResponse(
            plugins=plugin_responses,
            total_count=total_count,
            page=page,
            per_page=per_page
        )

    except Exception as e:
        logger.error(f"Failed to list plugins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=PluginListResponse)
async def search_plugins(
    request: PluginSearchRequest,
    current_user=Depends(get_current_user)
):
    """Search for plugins by query"""
    try:
        plugin_manager = get_plugin_manager()

        # Perform search
        search_results = plugin_manager.search_plugins(request.query)

        # Apply filters
        if request.category:
            search_results = [p for p in search_results if request.category in p.keywords]

        if request.verified_only:
            search_results = [p for p in search_results if p.verified]

        # Apply limit
        if request.limit:
            search_results = search_results[:request.limit]

        # Convert to response model
        plugin_responses = [PluginMetadataResponse.from_metadata(p) for p in search_results]

        return PluginListResponse(
            plugins=plugin_responses,
            total_count=len(search_results),
            page=1,
            per_page=len(search_results)
        )

    except Exception as e:
        logger.error(f"Plugin search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plugin_id}", response_model=PluginMetadataResponse)
async def get_plugin_info(
    plugin_id: str,
    current_user=Depends(get_current_user)
):
    """Get detailed information about a specific plugin"""
    try:
        plugin_manager = get_plugin_manager()

        plugin_metadata = plugin_manager.get_plugin_info(plugin_id)
        if not plugin_metadata:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

        return PluginMetadataResponse.from_metadata(plugin_metadata)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plugin info for {plugin_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Plugin Installation Endpoints

@router.get("/installed", response_model=List[PluginMetadataResponse])
async def list_installed_plugins(
    current_user=Depends(get_current_user)
):
    """List all installed plugins"""
    try:
        plugin_manager = get_plugin_manager()

        installed_plugins = plugin_manager.list_installed_plugins()
        plugin_responses = [PluginMetadataResponse.from_metadata(p.metadata) for p in installed_plugins]

        return plugin_responses

    except Exception as e:
        logger.error(f"Failed to list installed plugins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install", response_model=PluginOperationResponse)
@require_role(["admin", "editor"])
async def install_plugin(
    request: PluginInstallRequest,
    current_user=Depends(get_current_user)
):
    """Install a plugin from the marketplace"""
    try:
        plugin_manager = get_plugin_manager()

        result = await plugin_manager.install_plugin(request.plugin_id, request.version)

        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])

        return PluginOperationResponse(
            success=result['success'],
            message=result['message'],
            plugin_id=result['plugin_id'],
            version=result.get('installed_version')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plugin installation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{plugin_id}", response_model=PluginOperationResponse)
@require_role(["admin", "editor"])
async def uninstall_plugin(
    plugin_id: str,
    current_user=Depends(get_current_user)
):
    """Uninstall a plugin"""
    try:
        plugin_manager = get_plugin_manager()

        result = await plugin_manager.uninstall_plugin(plugin_id)

        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])

        return PluginOperationResponse(
            success=result['success'],
            message=result['message'],
            plugin_id=result['plugin_id']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plugin uninstallation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{plugin_id}/update", response_model=PluginOperationResponse)
@require_role(["admin", "editor"])
async def update_plugin(
    plugin_id: str,
    current_user=Depends(get_current_user)
):
    """Update a plugin to the latest version"""
    try:
        plugin_manager = get_plugin_manager()

        result = await plugin_manager.update_plugin(plugin_id)

        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])

        return PluginOperationResponse(
            success=result['success'],
            message=result['message'],
            plugin_id=result['plugin_id'],
            version=result.get('new_version')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plugin update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Plugin Development Endpoints

@router.post("/upload", response_model=PluginOperationResponse)
@require_role(["admin"])
async def upload_plugin(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    """Upload and register a new plugin (admin only)"""
    try:
        plugin_manager = get_plugin_manager()

        # Validate file type
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Plugin must be a ZIP file")

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = Path(temp_file.name)

        try:
            # Validate plugin package
            validation = plugin_manager.security.validate_plugin_package(temp_path)
            if not validation['valid']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Plugin validation failed: {', '.join(validation['issues'])}"
                )

            # Register plugin
            success = plugin_manager.registry.register_plugin(validation['metadata'], temp_path)
            if not success:
                raise HTTPException(status_code=400, detail="Failed to register plugin")

            return PluginOperationResponse(
                success=True,
                message=f"Plugin {validation['metadata'].name} registered successfully",
                plugin_id=validation['metadata'].id,
                version=validation['metadata'].version
            )

        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plugin upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plugin_id}/download")
@require_role(["admin", "editor"])
async def download_plugin(
    plugin_id: str,
    version: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """Download plugin package file"""
    try:
        plugin_manager = get_plugin_manager()

        # Get plugin metadata
        plugin_metadata = plugin_manager.get_plugin_info(plugin_id)
        if not plugin_metadata:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

        # Use latest version if not specified
        if not version:
            version = plugin_metadata.version

        # Get package path
        package_path = plugin_manager.registry.get_plugin_package_path(plugin_id, version)
        if not package_path:
            raise HTTPException(
                status_code=404,
                detail=f"Plugin package not found: {plugin_id} v{version}"
            )

        # Increment download count
        plugin_manager.registry.increment_download_count(plugin_id)

        return FileResponse(
            path=package_path,
            filename=f"{plugin_id}-{version}.zip",
            media_type="application/zip"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plugin download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Plugin Runtime Endpoints

@router.get("/{plugin_id}/files")
async def get_plugin_files(
    plugin_id: str,
    current_user=Depends(get_current_user)
):
    """Get plugin JavaScript files for injection into extension"""
    try:
        plugin_manager = get_plugin_manager()

        if not plugin_manager.is_plugin_installed(plugin_id):
            raise HTTPException(status_code=404, detail=f"Plugin not installed: {plugin_id}")

        js_files = plugin_manager.get_plugin_files_for_injection(plugin_id)

        return JSONResponse({
            "plugin_id": plugin_id,
            "files": js_files
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plugin files for {plugin_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_plugin_categories(
    current_user=Depends(get_current_user)
):
    """Get all available plugin categories"""
    try:
        plugin_manager = get_plugin_manager()

        # Get all plugins and extract categories
        all_plugins = plugin_manager.list_available_plugins()
        categories = set()

        for plugin in all_plugins:
            categories.update(plugin.keywords)

        return JSONResponse({
            "categories": sorted(list(categories))
        })

    except Exception as e:
        logger.error(f"Failed to get plugin categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Plugin Statistics Endpoints

@router.get("/stats/overview")
@require_role(["admin"])
async def get_plugin_stats(
    current_user=Depends(get_current_user)
):
    """Get plugin marketplace statistics (admin only)"""
    try:
        plugin_manager = get_plugin_manager()

        all_plugins = plugin_manager.list_available_plugins()
        installed_plugins = plugin_manager.list_installed_plugins()

        # Calculate statistics
        total_plugins = len(all_plugins)
        verified_plugins = len([p for p in all_plugins if p.verified])
        total_downloads = sum(p.download_count for p in all_plugins)
        average_rating = (
            sum(p.rating for p in all_plugins if p.rating > 0)
            / max(1, len([p for p in all_plugins if p.rating > 0]))
        )

        # Security level distribution
        security_levels = {}
        for plugin in all_plugins:
            level = plugin.security_level
            security_levels[level] = security_levels.get(level, 0) + 1

        # Top categories
        categories = {}
        for plugin in all_plugins:
            for keyword in plugin.keywords:
                categories[keyword] = categories.get(keyword, 0) + 1
        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]

        return JSONResponse({
            "marketplace": {
                "total_plugins": total_plugins,
                "verified_plugins": verified_plugins,
                "total_downloads": total_downloads,
                "average_rating": round(average_rating, 2),
                "security_level_distribution": security_levels,
                "top_categories": dict(top_categories)
            },
            "installation": {
                "installed_plugins": len(installed_plugins),
                "installed_plugin_ids": [p.metadata.id for p in installed_plugins]
            }
        })

    except Exception as e:
        logger.error(f"Failed to get plugin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
