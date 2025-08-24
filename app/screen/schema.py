"""
macOS screen schema capture using Accessibility API.

This module provides screen accessibility schema capture functionality 
for the Verifier system and Planner L1.
"""

from __future__ import annotations

import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime


def capture_macos_screen_schema(target: str = "frontmost") -> Dict[str, Any]:
    """
    Capture macOS screen accessibility schema.
    
    Args:
        target: "frontmost" for active window, "screen" for full screen
        
    Returns:
        Dictionary containing accessibility hierarchy
        
    Note: This is a basic implementation. Full AX API integration would
    require PyObjC and Cocoa/ApplicationServices frameworks.
    """
    
    schema = {
        "platform": "macos",
        "target": target,
        "timestamp": datetime.now().isoformat(),
        "elements": [],
        "version": "0.1.0"
    }
    
    try:
        # Get basic window information using AppleScript
        if target == "frontmost":
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                set frontWindow to name of front window of application process frontApp
                return {frontApp, frontWindow}
            end tell
            '''
            result = subprocess.run(["osascript", "-e", script], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 2:
                    app_name = parts[0].strip()
                    window_name = parts[1].strip()
                    
                    schema["elements"] = [{
                        "role": "AXApplication",
                        "label": app_name,
                        "bounds": {"x": 0, "y": 0, "width": 1920, "height": 1080},  # Placeholder
                        "children": [{
                            "role": "AXWindow", 
                            "label": window_name,
                            "bounds": {"x": 100, "y": 100, "width": 800, "height": 600},  # Placeholder
                            "children": []  # Would contain detailed UI elements
                        }]
                    }]
        
        # Add implementation notes for future development
        schema["implementation_notes"] = [
            "This is a basic placeholder implementation",
            "Full implementation requires PyObjC integration",
            "Would use NSWorkspace, AXUIElementCreateSystemWide",
            "Would traverse AX hierarchy recursively",
            "Would extract roles, labels, values, bounds for all elements"
        ]
        
    except Exception as e:
        schema["error"] = str(e)
        schema["elements"] = []
    
    return schema


def find_elements_by_text(schema: Dict[str, Any], text: str, role: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find elements in schema by text and optionally by role.
    
    Args:
        schema: Screen schema from capture_macos_screen_schema
        text: Text to search for in element labels/values
        role: Optional role filter (e.g., "AXButton", "AXTextField")
        
    Returns:
        List of matching elements
    """
    matches = []
    
    def search_recursive(elements: List[Dict[str, Any]]):
        for element in elements:
            element_text = element.get("label", "") or element.get("value", "")
            element_role = element.get("role", "")
            
            # Check if element matches text and role criteria
            text_matches = text.lower() in element_text.lower()
            role_matches = role is None or element_role == role
            
            if text_matches and role_matches:
                matches.append(element)
            
            # Recursively search children
            if element.get("children"):
                search_recursive(element["children"])
    
    search_recursive(schema.get("elements", []))
    return matches


def count_elements_by_criteria(schema: Dict[str, Any], text: Optional[str] = None, role: Optional[str] = None) -> int:
    """
    Count elements matching criteria in schema.
    
    Args:
        schema: Screen schema from capture_macos_screen_schema
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
            element_role = element.get("role", "")
            
            # Check if element matches criteria
            text_matches = text is None or text.lower() in element_text.lower()
            role_matches = role is None or element_role == role
            
            if text_matches and role_matches:
                count += 1
            
            # Recursively count children
            if element.get("children"):
                count_recursive(element["children"])
    
    count_recursive(schema.get("elements", []))
    return count