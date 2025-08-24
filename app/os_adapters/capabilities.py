from __future__ import annotations

from typing import Dict, Set
from .base import Capability


class CapabilityMap:
    """Manages OS capability negotiation and fallback strategies."""
    
    # Define all known capabilities across platforms
    ALL_CAPABILITIES = {
        "mail_compose", "mail_attach", "mail_save_draft",
        "preview_files", "screenshot", "screen_schema",
        "fs_operations", "pdf_operations", "permissions_check",
        "ax_api_access", "applescript_automation"
    }
    
    # Platform-specific capability definitions
    PLATFORM_CAPABILITIES = {
        "macos": {
            "mail_compose": Capability("mail_compose", True, "Via AppleScript/Mail.app"),
            "mail_attach": Capability("mail_attach", True, "Via AppleScript"),
            "mail_save_draft": Capability("mail_save_draft", True, "Via AppleScript"),
            "preview_files": Capability("preview_files", True, "Via /usr/bin/open"),
            "screenshot": Capability("screenshot", True, "Via screencapture command"),
            "screen_schema": Capability("screen_schema", True, "Via macOS Accessibility API"),
            "fs_operations": Capability("fs_operations", True, "Native filesystem access"),
            "pdf_operations": Capability("pdf_operations", True, "Via PyPDF2/pypdf"),
            "permissions_check": Capability("permissions_check", True, "Via System Preferences check"),
            "ax_api_access": Capability("ax_api_access", True, "macOS AX API available"),
            "applescript_automation": Capability("applescript_automation", True, "AppleScript via osascript")
        },
        "windows": {
            "mail_compose": Capability("mail_compose", False, "Future: Via Outlook COM/PowerShell"),
            "mail_attach": Capability("mail_attach", False, "Future: Via Outlook COM"),
            "mail_save_draft": Capability("mail_save_draft", False, "Future: Via Outlook COM"),
            "preview_files": Capability("preview_files", False, "Future: Via shell execute"),
            "screenshot": Capability("screenshot", False, "Future: Via Windows API/PIL"),
            "screen_schema": Capability("screen_schema", False, "Future: Via UI Automation API"),
            "fs_operations": Capability("fs_operations", False, "Future: Native filesystem access"),
            "pdf_operations": Capability("pdf_operations", False, "Future: Via PyPDF2/pypdf"),
            "permissions_check": Capability("permissions_check", False, "Future: Via Windows Settings check"),
            "ax_api_access": Capability("ax_api_access", False, "Future: Windows UI Automation"),
            "applescript_automation": Capability("applescript_automation", False, "N/A on Windows")
        }
    }
    
    def __init__(self, platform: str):
        self.platform = platform.lower()
        self.capabilities = self.PLATFORM_CAPABILITIES.get(self.platform, {})
    
    def get_capability(self, name: str) -> Capability:
        """Get capability info for specified feature."""
        return self.capabilities.get(name, Capability(name, False, "Unknown capability"))
    
    def is_available(self, name: str) -> bool:
        """Check if capability is available on current platform."""
        cap = self.get_capability(name)
        return cap.available
    
    def get_available_capabilities(self) -> Set[str]:
        """Get set of all available capability names."""
        return {name for name, cap in self.capabilities.items() if cap.available}
    
    def get_unavailable_capabilities(self) -> Set[str]:
        """Get set of all unavailable capability names."""
        return {name for name, cap in self.capabilities.items() if not cap.available}
    
    def get_fallback_strategy(self, capability: str) -> str:
        """Get fallback strategy when capability is unavailable."""
        fallback_strategies = {
            "mail_compose": "Create .eml template file and log draft suggestion",
            "mail_attach": "List attachment paths in draft template",
            "mail_save_draft": "Save .eml template to desktop/drafts folder",
            "preview_files": "Log file path for manual opening",
            "screenshot": "Skip screenshot capture step",
            "screen_schema": "Return empty schema structure",
            "fs_operations": "Log filesystem operation request",
            "pdf_operations": "Log PDF operation request",
            "permissions_check": "Assume permissions granted and warn",
            "ax_api_access": "Skip accessibility-based operations",
            "applescript_automation": "Use PowerShell/COM alternatives where possible"
        }
        
        return fallback_strategies.get(capability, "Log operation as TODO item")
    
    def apply_fallback(self, capability: str, operation_details: Dict) -> Dict:
        """Apply fallback strategy for unavailable capability.
        
        Args:
            capability: Name of unavailable capability
            operation_details: Details about the attempted operation
            
        Returns:
            Dictionary with fallback result and metadata
        """
        strategy = self.get_fallback_strategy(capability)
        
        return {
            "fallback_applied": True,
            "original_capability": capability,
            "fallback_strategy": strategy,
            "operation_details": operation_details,
            "result": "operation_logged_as_todo",
            "message": f"Capability '{capability}' not available on {self.platform}. {strategy}"
        }


def get_platform_capability_map(platform: str) -> CapabilityMap:
    """Factory function to get capability map for specified platform."""
    return CapabilityMap(platform)