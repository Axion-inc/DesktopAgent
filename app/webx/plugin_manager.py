"""
WebX Plugin Manager
Handles plugin registration, distribution, and lifecycle management
"""

import json
import os
import hashlib
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import zipfile
import requests
from dataclasses import dataclass, asdict

from ..config import get_config
from ..utils.logging import get_logger
from ..security.secrets import get_secrets_manager

logger = get_logger(__name__)


@dataclass
class PluginMetadata:
    """Plugin metadata structure"""
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
    max_webx_version: Optional[str] = None
    dependencies: Dict[str, str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    download_count: int = 0
    rating: float = 0.0
    review_count: int = 0
    verified: bool = False
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = {}
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at


@dataclass
class PluginPackage:
    """Plugin package with metadata and content"""
    metadata: PluginMetadata
    content_hash: str
    file_size: int
    manifest: Dict[str, Any]
    files: List[str]
    signed: bool = False
    signature: Optional[str] = None


class PluginSecurity:
    """Plugin security and validation"""
    
    def __init__(self):
        self.allowed_capabilities = [
            'dom:read', 'dom:write', 'form:fill', 'click:elements',
            'file:upload', 'screenshot', 'navigation', 'iframe:access',
            'shadow:dom', 'clipboard', 'network', 'storage', 'notifications'
        ]
        
        self.security_levels = {
            'minimal': ['dom:read'],
            'standard': ['dom:read', 'dom:write', 'form:fill', 'click:elements', 'storage'],
            'elevated': self.allowed_capabilities,
            'system': self.allowed_capabilities  # + system-specific capabilities
        }
    
    def validate_plugin_metadata(self, metadata: PluginMetadata) -> List[str]:
        """Validate plugin metadata and return list of issues"""
        issues = []
        
        # Required fields
        required_fields = ['id', 'name', 'version', 'author', 'capabilities', 'security_level']
        for field in required_fields:
            if not getattr(metadata, field):
                issues.append(f"Missing required field: {field}")
        
        # Version format validation
        if metadata.version and not self._is_valid_version(metadata.version):
            issues.append(f"Invalid version format: {metadata.version}")
        
        # Capabilities validation
        for capability in metadata.capabilities:
            if capability not in self.allowed_capabilities:
                issues.append(f"Unknown capability: {capability}")
        
        # Security level validation
        if metadata.security_level not in self.security_levels:
            issues.append(f"Invalid security level: {metadata.security_level}")
        else:
            # Check if capabilities match security level
            allowed_caps = self.security_levels[metadata.security_level]
            for capability in metadata.capabilities:
                if capability not in allowed_caps:
                    issues.append(f"Capability '{capability}' not allowed for security level '{metadata.security_level}'")
        
        return issues
    
    def _is_valid_version(self, version: str) -> bool:
        """Check if version follows semantic versioning"""
        import re
        pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?$'
        return bool(re.match(pattern, version))
    
    def calculate_content_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of plugin content"""
        return hashlib.sha256(content).hexdigest()
    
    def validate_plugin_package(self, package_path: Path) -> Dict[str, Any]:
        """Validate plugin package file"""
        validation_result = {
            'valid': False,
            'issues': [],
            'metadata': None,
            'content_hash': None,
            'file_size': 0
        }
        
        try:
            if not package_path.exists():
                validation_result['issues'].append("Package file does not exist")
                return validation_result
            
            validation_result['file_size'] = package_path.stat().st_size
            
            # Read and validate as ZIP file
            with zipfile.ZipFile(package_path, 'r') as zf:
                # Check for required files
                required_files = ['manifest.json', 'plugin.js']
                missing_files = []
                
                for required_file in required_files:
                    if required_file not in zf.namelist():
                        missing_files.append(required_file)
                
                if missing_files:
                    validation_result['issues'].extend([f"Missing required file: {f}" for f in missing_files])
                    return validation_result
                
                # Validate manifest.json
                try:
                    manifest_content = zf.read('manifest.json').decode('utf-8')
                    manifest = json.loads(manifest_content)
                    
                    # Create metadata from manifest
                    metadata = PluginMetadata(**manifest)
                    validation_result['metadata'] = metadata
                    
                    # Validate metadata
                    metadata_issues = self.validate_plugin_metadata(metadata)
                    validation_result['issues'].extend(metadata_issues)
                    
                except (json.JSONDecodeError, TypeError) as e:
                    validation_result['issues'].append(f"Invalid manifest.json: {e}")
                    return validation_result
                
                # Calculate content hash
                with open(package_path, 'rb') as f:
                    content = f.read()
                    validation_result['content_hash'] = self.calculate_content_hash(content)
                
                # Additional security checks
                for file_info in zf.infolist():
                    # Check for suspicious file paths
                    if '..' in file_info.filename or file_info.filename.startswith('/'):
                        validation_result['issues'].append(f"Suspicious file path: {file_info.filename}")
                    
                    # Check file sizes
                    if file_info.file_size > 10 * 1024 * 1024:  # 10MB limit per file
                        validation_result['issues'].append(f"File too large: {file_info.filename} ({file_info.file_size} bytes)")
                
                validation_result['valid'] = len(validation_result['issues']) == 0
                
        except zipfile.BadZipFile:
            validation_result['issues'].append("Invalid ZIP file")
        except Exception as e:
            validation_result['issues'].append(f"Validation error: {str(e)}")
        
        return validation_result


class PluginRegistry:
    """Plugin registry for marketplace functionality"""
    
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        self.plugins_file = self.registry_path / "plugins.json"
        self.packages_dir = self.registry_path / "packages"
        self.packages_dir.mkdir(exist_ok=True)
        
        self._plugins: Dict[str, PluginMetadata] = {}
        self._load_registry()
    
    def _load_registry(self):
        """Load plugin registry from disk"""
        if self.plugins_file.exists():
            try:
                with open(self.plugins_file, 'r') as f:
                    data = json.load(f)
                    for plugin_id, plugin_data in data.items():
                        self._plugins[plugin_id] = PluginMetadata(**plugin_data)
            except Exception as e:
                logger.error(f"Failed to load plugin registry: {e}")
    
    def _save_registry(self):
        """Save plugin registry to disk"""
        try:
            data = {plugin_id: asdict(metadata) for plugin_id, metadata in self._plugins.items()}
            with open(self.plugins_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save plugin registry: {e}")
    
    def register_plugin(self, metadata: PluginMetadata, package_path: Path) -> bool:
        """Register a new plugin in the registry"""
        try:
            # Validate plugin
            security = PluginSecurity()
            issues = security.validate_plugin_metadata(metadata)
            if issues:
                logger.error(f"Plugin validation failed: {issues}")
                return False
            
            # Copy package to registry
            package_dest = self.packages_dir / f"{metadata.id}-{metadata.version}.zip"
            package_dest.write_bytes(package_path.read_bytes())
            
            # Update metadata with current timestamp
            metadata.updated_at = datetime.now().isoformat()
            
            # Register plugin
            self._plugins[metadata.id] = metadata
            self._save_registry()
            
            logger.info(f"Plugin registered: {metadata.name} v{metadata.version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register plugin {metadata.id}: {e}")
            return False
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Get plugin metadata by ID"""
        return self._plugins.get(plugin_id)
    
    def list_plugins(self, category: Optional[str] = None, 
                    verified_only: bool = False) -> List[PluginMetadata]:
        """List all plugins with optional filtering"""
        plugins = list(self._plugins.values())
        
        if category:
            plugins = [p for p in plugins if category in p.keywords]
        
        if verified_only:
            plugins = [p for p in plugins if p.verified]
        
        # Sort by rating and download count
        plugins.sort(key=lambda p: (p.rating, p.download_count), reverse=True)
        return plugins
    
    def search_plugins(self, query: str) -> List[PluginMetadata]:
        """Search plugins by name, description, or keywords"""
        query_lower = query.lower()
        results = []
        
        for plugin in self._plugins.values():
            # Search in name, description, and keywords
            search_text = f"{plugin.name} {plugin.description} {' '.join(plugin.keywords)}".lower()
            if query_lower in search_text:
                results.append(plugin)
        
        # Sort by relevance (simple scoring)
        def relevance_score(plugin):
            score = 0
            if query_lower in plugin.name.lower():
                score += 10
            if query_lower in plugin.description.lower():
                score += 5
            for keyword in plugin.keywords:
                if query_lower in keyword.lower():
                    score += 3
            return score
        
        results.sort(key=relevance_score, reverse=True)
        return results
    
    def get_plugin_package_path(self, plugin_id: str, version: str) -> Optional[Path]:
        """Get path to plugin package file"""
        package_path = self.packages_dir / f"{plugin_id}-{version}.zip"
        return package_path if package_path.exists() else None
    
    def increment_download_count(self, plugin_id: str):
        """Increment plugin download counter"""
        if plugin_id in self._plugins:
            self._plugins[plugin_id].download_count += 1
            self._save_registry()


class PluginManager:
    """Main plugin manager for WebX system"""
    
    def __init__(self):
        self.config = get_config()
        self.security = PluginSecurity()
        
        # Setup directories
        self.plugin_dir = Path(self.config.get('webx', {}).get('plugin_directory', './webx-plugins'))
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry = PluginRegistry(self.plugin_dir / "registry")
        
        # Installed plugins
        self.installed_plugins: Dict[str, PluginPackage] = {}
        self._load_installed_plugins()
    
    def _load_installed_plugins(self):
        """Load installed plugins from disk"""
        installed_dir = self.plugin_dir / "installed"
        if installed_dir.exists():
            for plugin_dir in installed_dir.iterdir():
                if plugin_dir.is_dir():
                    try:
                        manifest_path = plugin_dir / "manifest.json"
                        if manifest_path.exists():
                            with open(manifest_path, 'r') as f:
                                manifest = json.load(f)
                                metadata = PluginMetadata(**manifest)
                                
                                # Create plugin package object
                                package = PluginPackage(
                                    metadata=metadata,
                                    content_hash="",  # Would be calculated
                                    file_size=0,
                                    manifest=manifest,
                                    files=list(plugin_dir.glob("*.js"))
                                )
                                
                                self.installed_plugins[metadata.id] = package
                    except Exception as e:
                        logger.error(f"Failed to load installed plugin from {plugin_dir}: {e}")
    
    def list_available_plugins(self) -> List[PluginMetadata]:
        """List all available plugins in registry"""
        return self.registry.list_plugins()
    
    def search_plugins(self, query: str) -> List[PluginMetadata]:
        """Search for plugins by query"""
        return self.registry.search_plugins(query)
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Get detailed plugin information"""
        return self.registry.get_plugin(plugin_id)
    
    def is_plugin_installed(self, plugin_id: str) -> bool:
        """Check if plugin is installed"""
        return plugin_id in self.installed_plugins
    
    def get_installed_plugin(self, plugin_id: str) -> Optional[PluginPackage]:
        """Get installed plugin package"""
        return self.installed_plugins.get(plugin_id)
    
    def list_installed_plugins(self) -> List[PluginPackage]:
        """List all installed plugins"""
        return list(self.installed_plugins.values())
    
    async def install_plugin(self, plugin_id: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Install plugin from registry"""
        result = {
            'success': False,
            'message': '',
            'plugin_id': plugin_id,
            'installed_version': None
        }
        
        try:
            # Get plugin metadata
            plugin_metadata = self.registry.get_plugin(plugin_id)
            if not plugin_metadata:
                result['message'] = f"Plugin not found: {plugin_id}"
                return result
            
            # Use latest version if not specified
            if not version:
                version = plugin_metadata.version
            
            # Check if already installed
            if self.is_plugin_installed(plugin_id):
                installed_plugin = self.installed_plugins[plugin_id]
                if installed_plugin.metadata.version == version:
                    result['message'] = f"Plugin {plugin_id} v{version} already installed"
                    result['success'] = True
                    result['installed_version'] = version
                    return result
            
            # Get package path
            package_path = self.registry.get_plugin_package_path(plugin_id, version)
            if not package_path:
                result['message'] = f"Plugin package not found: {plugin_id} v{version}"
                return result
            
            # Validate package
            validation = self.security.validate_plugin_package(package_path)
            if not validation['valid']:
                result['message'] = f"Plugin validation failed: {', '.join(validation['issues'])}"
                return result
            
            # Install plugin
            install_dir = self.plugin_dir / "installed" / plugin_id
            install_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract package
            with zipfile.ZipFile(package_path, 'r') as zf:
                zf.extractall(install_dir)
            
            # Update installed plugins
            package = PluginPackage(
                metadata=plugin_metadata,
                content_hash=validation['content_hash'],
                file_size=validation['file_size'],
                manifest=validation['metadata'].__dict__,
                files=[str(f) for f in install_dir.glob("*.js")]
            )
            
            self.installed_plugins[plugin_id] = package
            
            # Increment download count
            self.registry.increment_download_count(plugin_id)
            
            result['success'] = True
            result['message'] = f"Plugin {plugin_id} v{version} installed successfully"
            result['installed_version'] = version
            
            logger.info(f"Plugin installed: {plugin_id} v{version}")
            
        except Exception as e:
            result['message'] = f"Installation failed: {str(e)}"
            logger.error(f"Failed to install plugin {plugin_id}: {e}")
        
        return result
    
    async def uninstall_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstall plugin"""
        result = {
            'success': False,
            'message': '',
            'plugin_id': plugin_id
        }
        
        try:
            if not self.is_plugin_installed(plugin_id):
                result['message'] = f"Plugin not installed: {plugin_id}"
                return result
            
            # Remove installation directory
            install_dir = self.plugin_dir / "installed" / plugin_id
            if install_dir.exists():
                import shutil
                shutil.rmtree(install_dir)
            
            # Remove from installed plugins
            del self.installed_plugins[plugin_id]
            
            result['success'] = True
            result['message'] = f"Plugin {plugin_id} uninstalled successfully"
            
            logger.info(f"Plugin uninstalled: {plugin_id}")
            
        except Exception as e:
            result['message'] = f"Uninstallation failed: {str(e)}"
            logger.error(f"Failed to uninstall plugin {plugin_id}: {e}")
        
        return result
    
    async def update_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Update plugin to latest version"""
        result = {
            'success': False,
            'message': '',
            'plugin_id': plugin_id,
            'old_version': None,
            'new_version': None
        }
        
        try:
            if not self.is_plugin_installed(plugin_id):
                result['message'] = f"Plugin not installed: {plugin_id}"
                return result
            
            current_version = self.installed_plugins[plugin_id].metadata.version
            result['old_version'] = current_version
            
            # Get latest version from registry
            latest_metadata = self.registry.get_plugin(plugin_id)
            if not latest_metadata:
                result['message'] = f"Plugin not found in registry: {plugin_id}"
                return result
            
            if latest_metadata.version == current_version:
                result['message'] = f"Plugin {plugin_id} is already up to date (v{current_version})"
                result['success'] = True
                return result
            
            # Uninstall current version
            await self.uninstall_plugin(plugin_id)
            
            # Install latest version
            install_result = await self.install_plugin(plugin_id, latest_metadata.version)
            
            result['success'] = install_result['success']
            result['message'] = install_result['message']
            result['new_version'] = latest_metadata.version
            
        except Exception as e:
            result['message'] = f"Update failed: {str(e)}"
            logger.error(f"Failed to update plugin {plugin_id}: {e}")
        
        return result
    
    def get_plugin_files_for_injection(self, plugin_id: str) -> List[str]:
        """Get plugin JavaScript files for injection into extension"""
        if not self.is_plugin_installed(plugin_id):
            return []
        
        plugin = self.installed_plugins[plugin_id]
        js_files = []
        
        install_dir = self.plugin_dir / "installed" / plugin_id
        for js_file in install_dir.glob("*.js"):
            try:
                with open(js_file, 'r') as f:
                    js_files.append(f.read())
            except Exception as e:
                logger.error(f"Failed to read plugin file {js_file}: {e}")
        
        return js_files


# Global plugin manager instance
_plugin_manager = None

def get_plugin_manager() -> PluginManager:
    """Get global plugin manager instance"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager