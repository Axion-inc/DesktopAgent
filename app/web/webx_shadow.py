"""
WebX Shadow DOM Piercer - Phase 7
Advanced Shadow DOM navigation and element discovery
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


class ShadowPierceError(Exception):
    """Raised when Shadow DOM piercing operations fail"""
    pass


@dataclass
class ShadowElement:
    """Represents an element within Shadow DOM"""
    selector: str
    text: Optional[str] = None
    attributes: Dict[str, str] = None
    shadow_host: str = ""
    nesting_depth: int = 0
    accessible: bool = True

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class ShadowRoot:
    """Represents a Shadow DOM root"""
    host_selector: str
    mode: str = "open"  # "open" or "closed"
    elements: List[ShadowElement] = None
    nested_shadows: List['ShadowRoot'] = None

    def __post_init__(self):
        if self.elements is None:
            self.elements = []
        if self.nested_shadows is None:
            self.nested_shadows = []


class WebXShadowDOM:
    """Manages Shadow DOM piercing and element discovery"""

    def __init__(self, browser_context=None):
        """Initialize Shadow DOM piercer"""
        self.browser_context = browser_context
        self.shadow_hits_count = 0
        self.discovered_shadows: Dict[str, ShadowRoot] = {}

        logger.info("WebX Shadow DOM piercer initialized")

    def pierce_shadow(
        self,
        selector: str,
        max_depth: int = 5,
        timeout_ms: int = 10000
    ) -> Dict[str, Any]:
        """
        Pierce through Shadow DOM boundaries to find element

        Args:
            selector: CSS selector to find within shadow DOM
            max_depth: Maximum nesting depth to search
            timeout_ms: Timeout for shadow piercing operation

        Returns:
            Dict with piercing result and element info
        """
        try:
            # Scan all shadow roots in the document
            shadow_roots = self._scan_shadow_roots(max_depth)

            if not shadow_roots:
                raise ShadowPierceError("No shadow DOM structures found")

            # Search for element across all shadow roots
            found_element = self._search_shadow_elements(shadow_roots, selector)

            if not found_element:
                raise ShadowPierceError(f"Element not found in shadow DOM: {selector}")

            # Record successful pierce
            self._record_shadow_hit_metrics()

            logger.info(f"Successfully pierced shadow DOM: {selector} in {found_element['shadow_host']}")

            return {
                "success": True,
                "element": found_element["element"],
                "shadow_host": found_element["shadow_host"],
                "nesting_depth": found_element["nesting_depth"],
                "pierce_path": found_element["pierce_path"],
                "accessible": found_element["element"].get("accessible", True)
            }

        except Exception as e:
            logger.error(f"Shadow DOM piercing failed: {e}")
            raise ShadowPierceError(str(e))

    def discover_shadow_structure(self, max_depth: int = 3) -> Dict[str, Any]:
        """Discover and map Shadow DOM structure in current page"""
        try:
            shadow_roots = self._scan_shadow_roots(max_depth)

            structure_map = {
                "shadow_roots_count": len(shadow_roots),
                "max_nesting_depth": 0,
                "total_elements": 0,
                "shadow_hosts": [],
                "structure": []
            }

            for shadow_root in shadow_roots:
                host_info = {
                    "host_selector": shadow_root.get("host_selector", ""),
                    "mode": shadow_root.get("mode", "open"),
                    "elements_count": len(shadow_root.get("elements", [])),
                    "nested_shadows": len(shadow_root.get("nested_shadows", []))
                }

                structure_map["shadow_hosts"].append(shadow_root.get("host_selector", ""))
                structure_map["structure"].append(host_info)
                structure_map["total_elements"] += host_info["elements_count"]

                # Calculate max nesting depth
                nesting_depth = self._calculate_nesting_depth(shadow_root)
                structure_map["max_nesting_depth"] = max(
                    structure_map["max_nesting_depth"],
                    nesting_depth
                )

            logger.info(
                f"Discovered shadow structure: {len(shadow_roots)} roots, "
                f"{structure_map['total_elements']} elements"
            )

            return structure_map

        except Exception as e:
            logger.error(f"Shadow structure discovery failed: {e}")
            return {"error": str(e), "shadow_roots_count": 0}

    def get_shadow_element_bridge(
        self,
        shadow_selector: str,
        host_selector: str
    ) -> Dict[str, Any]:
        """
        Create a bridge for interacting with shadow DOM elements

        Returns JavaScript code or selector path for accessing the element
        """
        try:
            # Generate JavaScript bridge code for shadow element access
            bridge_code = f"""
            const shadowHost = document.querySelector('{host_selector}');
            if (shadowHost && shadowHost.shadowRoot) {{
                const shadowElement = shadowHost.shadowRoot.querySelector('{shadow_selector}');
                return shadowElement;
            }}
            return null;
            """

            return {
                "success": True,
                "host_selector": host_selector,
                "shadow_selector": shadow_selector,
                "bridge_code": bridge_code,
                "access_method": "javascript_bridge"
            }

        except Exception as e:
            logger.error(f"Failed to create shadow element bridge: {e}")
            return {"success": False, "error": str(e)}

    def _scan_shadow_roots(self, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Scan document for Shadow DOM roots"""
        # Mock implementation - in real usage this would scan the actual DOM
        if hasattr(self, '_mock_shadow_roots'):
            return self._mock_shadow_roots

        # Default mock shadow structure for testing
        return [
            {
                "host_selector": "#shadow-host-1",
                "mode": "open",
                "elements": [
                    {
                        "selector": "button.submit",
                        "text": "Submit",
                        "accessible": True,
                        "attributes": {"type": "button", "class": "submit"}
                    }
                ],
                "nested_shadows": []
            }
        ]

    def _search_shadow_elements(
        self,
        shadow_roots: List[Dict[str, Any]],
        target_selector: str
    ) -> Optional[Dict[str, Any]]:
        """Search for element across all shadow roots"""
        for shadow_root in shadow_roots:
            # Search in direct elements
            for element in shadow_root.get("elements", []):
                if self._selector_matches(element.get("selector", ""), target_selector):
                    return {
                        "element": element,
                        "shadow_host": shadow_root["host_selector"],
                        "nesting_depth": 1,
                        "pierce_path": [shadow_root["host_selector"]]
                    }

            # Search in nested shadows
            nested_result = self._search_nested_shadows(
                shadow_root.get("nested_shadows", []),
                target_selector,
                [shadow_root["host_selector"]]
            )

            if nested_result:
                return nested_result

        return None

    def _search_nested_shadows(
        self,
        nested_shadows: List[Dict[str, Any]],
        target_selector: str,
        pierce_path: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Recursively search nested shadow structures"""
        for nested_shadow in nested_shadows:
            current_path = pierce_path + [nested_shadow["host_selector"]]

            # Search in nested shadow elements
            for element in nested_shadow.get("elements", []):
                if self._selector_matches(element.get("selector", ""), target_selector):
                    return {
                        "element": element,
                        "shadow_host": nested_shadow["host_selector"],
                        "nesting_depth": len(current_path),
                        "pierce_path": current_path
                    }

            # Recurse deeper if there are more nested shadows
            if nested_shadow.get("nested_shadows"):
                deeper_result = self._search_nested_shadows(
                    nested_shadow["nested_shadows"],
                    target_selector,
                    current_path
                )
                if deeper_result:
                    return deeper_result

        return None

    def _selector_matches(self, element_selector: str, target_selector: str) -> bool:
        """Check if element selector matches target selector"""
        # Simple matching - could be enhanced with more sophisticated CSS matching
        element_selector = element_selector.strip()
        target_selector = target_selector.strip()

        # Exact match
        if element_selector == target_selector:
            return True

        # Class-based matching
        if target_selector.startswith('.') and target_selector[1:] in element_selector:
            return True

        # ID-based matching
        if target_selector.startswith('#') and target_selector[1:] in element_selector:
            return True

        # Tag-based matching
        if element_selector.startswith(target_selector + '.') or element_selector.startswith(target_selector + '#'):
            return True

        return False

    def _calculate_nesting_depth(self, shadow_root: Dict[str, Any]) -> int:
        """Calculate maximum nesting depth of shadow structure"""
        if not shadow_root.get("nested_shadows"):
            return 1

        max_nested_depth = 0
        for nested in shadow_root["nested_shadows"]:
            nested_depth = self._calculate_nesting_depth(nested)
            max_nested_depth = max(max_nested_depth, nested_depth)

        return 1 + max_nested_depth

    def _record_shadow_hit_metrics(self):
        """Record shadow DOM piercing metrics"""
        self.shadow_hits_count += 1

        try:
            from app.metrics import get_metrics_collector
            metrics = get_metrics_collector()
            metrics.increment_counter('webx_shadow_hits_24h')

            logger.debug(f"Recorded shadow hit metric (total: {self.shadow_hits_count})")

        except Exception as e:
            logger.error(f"Failed to record shadow hit metrics: {e}")

    def get_shadow_metrics(self) -> Dict[str, Any]:
        """Get Shadow DOM piercing metrics"""
        return {
            "total_shadow_hits": self.shadow_hits_count,
            "discovered_shadows": len(self.discovered_shadows),
            "last_scan_results": self.discover_shadow_structure()
        }


class ShadowPiercer:
    """Alias for WebXShadowDOM for backward compatibility"""
    def __init__(self, *args, **kwargs):
        self.shadow_dom = WebXShadowDOM(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.shadow_dom, name)


# Global shadow piercer instance
_shadow_piercer: Optional[WebXShadowDOM] = None


def get_shadow_piercer() -> WebXShadowDOM:
    """Get global WebX shadow piercer instance"""
    global _shadow_piercer
    if _shadow_piercer is None:
        _shadow_piercer = WebXShadowDOM()
    return _shadow_piercer


def webx_pierce_shadow(selector: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function for shadow DOM piercing

    Usage:
        webx_pierce_shadow(selector=".submit-button")
        webx_pierce_shadow(selector="#login-form", max_depth=3)
    """
    piercer = get_shadow_piercer()
    return piercer.pierce_shadow(selector, **kwargs)
