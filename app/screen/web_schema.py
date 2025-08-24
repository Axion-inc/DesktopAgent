"""
Web screen schema capture using Playwright accessibility tree.

This module provides web page accessibility schema capture functionality
for the Verifier system and Planner L1.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
from datetime import datetime


def capture_web_screen_schema(page_context, target: str = "page") -> Dict[str, Any]:
    """
    Capture web page accessibility schema using Playwright.
    
    Args:
        page_context: Active Playwright page context
        target: "page" for full page accessibility tree
        
    Returns:
        Dictionary containing accessibility hierarchy
    """
    
    schema = {
        "platform": "web",
        "target": target,
        "timestamp": datetime.now().isoformat(),
        "elements": [],
        "version": "0.1.0"
    }
    
    try:
        if page_context and hasattr(page_context, 'accessibility'):
            # Get accessibility tree from Playwright
            ax_tree = page_context.accessibility.snapshot()
            if ax_tree:
                schema["elements"] = [_convert_ax_node_to_element(ax_tree)]
        
        # Fallback: basic DOM structure if accessibility API not available
        if not schema["elements"] and page_context:
            try:
                # Get basic page info
                title = page_context.title()
                url = page_context.url
                
                schema["elements"] = [{
                    "role": "WebPage",
                    "label": title,
                    "value": url,
                    "bounds": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                    "children": []  # Would contain detailed elements from DOM
                }]
                
                schema["implementation_notes"] = [
                    "Using fallback implementation",
                    "Full accessibility tree not available", 
                    "Consider using page.accessibility.snapshot() for detailed tree"
                ]
            except Exception:
                pass
        
    except Exception as e:
        schema["error"] = str(e)
        schema["elements"] = []
    
    return schema


def _convert_ax_node_to_element(ax_node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Playwright accessibility node to our element format.
    
    Args:
        ax_node: Node from Playwright accessibility tree
        
    Returns:
        Element in our schema format
    """
    element = {
        "role": ax_node.get("role", ""),
        "label": ax_node.get("name", ""),
        "value": ax_node.get("value", ""),
    }
    
    # Add bounds if available
    if "boundingBox" in ax_node:
        bbox = ax_node["boundingBox"]
        element["bounds"] = {
            "x": bbox.get("x", 0),
            "y": bbox.get("y", 0), 
            "width": bbox.get("width", 0),
            "height": bbox.get("height", 0)
        }
    
    # Recursively convert children
    children = []
    for child in ax_node.get("children", []):
        children.append(_convert_ax_node_to_element(child))
    element["children"] = children
    
    return element


def find_web_elements_by_text(schema: Dict[str, Any], text: str, role: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find web elements in schema by text and optionally by role.
    
    Args:
        schema: Web schema from capture_web_screen_schema
        text: Text to search for in element labels/values
        role: Optional role filter (e.g., "button", "textbox")
        
    Returns:
        List of matching elements
    """
    matches = []
    
    def search_recursive(elements: List[Dict[str, Any]]):
        for element in elements:
            element_text = element.get("label", "") or element.get("value", "")
            element_role = element.get("role", "").lower()
            
            # Normalize role for comparison
            role_normalized = role.lower() if role else None
            
            # Check if element matches text and role criteria
            text_matches = text.lower() in element_text.lower()
            role_matches = role_normalized is None or element_role == role_normalized
            
            if text_matches and role_matches:
                matches.append(element)
            
            # Recursively search children
            if element.get("children"):
                search_recursive(element["children"])
    
    search_recursive(schema.get("elements", []))
    return matches


def count_web_elements_by_criteria(schema: Dict[str, Any], text: Optional[str] = None, role: Optional[str] = None) -> int:
    """
    Count web elements matching criteria in schema.
    
    Args:
        schema: Web schema from capture_web_screen_schema
        text: Optional text to search for
        role: Optional role filter
        
    Returns:
        Count of matching elements
    """
    count = 0
    
    def count_recursive(elements: List[Dict[str, Any]]):
        nonlocal count
        for element in elements:
            element_text = element.get("label", "") or element.get("value", "")
            element_role = element.get("role", "").lower()
            
            # Normalize role for comparison
            role_normalized = role.lower() if role else None
            
            # Check if element matches criteria
            text_matches = text is None or text.lower() in element_text.lower()
            role_matches = role_normalized is None or element_role == role_normalized
            
            if text_matches and role_matches:
                count += 1
            
            # Recursively count children
            if element.get("children"):
                count_recursive(element["children"])
    
    count_recursive(schema.get("elements", []))
    return count