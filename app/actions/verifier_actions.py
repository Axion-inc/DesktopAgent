"""
Verifier actions for Phase 3 DSL commands.

This module implements the verification and assertion actions for the DSL.
"""

from __future__ import annotations

import time
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.screen.schema import capture_macos_screen_schema, find_elements_by_text, count_elements_by_criteria
from app.screen.web_schema import capture_web_screen_schema, find_web_elements_by_text, count_web_elements_by_criteria


class VerificationResult:
    """Result of a verification operation with retry capability."""
    
    def __init__(self, passed: bool, message: str, retry_attempted: bool = False, 
                 retry_successful: bool = False, details: Optional[Dict[str, Any]] = None):
        self.passed = passed
        self.message = message
        self.retry_attempted = retry_attempted
        self.retry_successful = retry_successful
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DSL result."""
        status = "PASS" if self.passed else "FAIL"
        if self.retry_attempted and self.retry_successful:
            status = "RETRY"  # Passed after retry
            
        return {
            "status": status,
            "passed": self.passed,
            "message": self.message,
            "retry_attempted": self.retry_attempted,
            "retry_successful": self.retry_successful,
            **self.details
        }


def wait_for_element(text: Optional[str] = None, role: Optional[str] = None, 
                    timeout_ms: int = 15000, where: str = "screen") -> Dict[str, Any]:
    """
    Wait for element to appear on screen or web page.
    
    Args:
        text: Text to search for in element
        role: Role/type of element (e.g., "button", "textbox") 
        timeout_ms: Maximum wait time in milliseconds
        where: "screen" for macOS screen, "web" for web page
        
    Returns:
        Dictionary with verification result
    """
    start_time = time.time()
    timeout_seconds = timeout_ms / 1000.0
    
    retry_attempted = False
    retry_successful = False
    
    while (time.time() - start_time) < timeout_seconds:
        try:
            if where == "web":
                # TODO: Get active web context from runner state
                schema = capture_web_screen_schema(None)  # Placeholder
                elements = find_web_elements_by_text(schema, text or "", role)
            else:
                schema = capture_macos_screen_schema("frontmost")
                elements = find_elements_by_text(schema, text or "", role)
            
            if elements:
                return VerificationResult(
                    passed=True,
                    message=f"Element found: {text} (role: {role})",
                    details={"elements_found": len(elements), "timeout_ms": timeout_ms}
                ).to_dict()
            
            time.sleep(0.5)  # Wait before retry
            
        except Exception as e:
            # Auto-retry: extend wait time once on exception
            if not retry_attempted and (time.time() - start_time) < (timeout_seconds * 0.7):
                retry_attempted = True
                timeout_seconds = timeout_seconds * 1.5  # Extend timeout
                continue
            break
    
    # Element not found - attempt one final retry with extended timeout
    if not retry_attempted:
        retry_attempted = True
        try:
            time.sleep(1.0)  # Brief pause before final attempt
            if where == "web":
                schema = capture_web_screen_schema(None)
                elements = find_web_elements_by_text(schema, text or "", role)
            else:
                schema = capture_macos_screen_schema("frontmost")
                elements = find_elements_by_text(schema, text or "", role)
            
            if elements:
                retry_successful = True
                return VerificationResult(
                    passed=True,
                    message=f"Element found after retry: {text} (role: {role})",
                    retry_attempted=retry_attempted,
                    retry_successful=retry_successful,
                    details={"elements_found": len(elements), "timeout_ms": timeout_ms}
                ).to_dict()
        except Exception:
            pass
    
    return VerificationResult(
        passed=False,
        message=f"Element not found within {timeout_ms}ms: {text} (role: {role})",
        retry_attempted=retry_attempted,
        retry_successful=retry_successful,
        details={"timeout_ms": timeout_ms}
    ).to_dict()


def assert_element(text: Optional[str] = None, role: Optional[str] = None,
                  count_gte: int = 1, where: str = "screen") -> Dict[str, Any]:
    """
    Assert that element(s) exist on screen or web page.
    
    Args:
        text: Text to search for in element
        role: Role/type of element
        count_gte: Minimum number of elements that must be found
        where: "screen" for macOS screen, "web" for web page
        
    Returns:
        Dictionary with verification result
    """
    retry_attempted = False
    retry_successful = False
    
    try:
        if where == "web":
            schema = capture_web_screen_schema(None)  # TODO: Get from runner state
            elements = find_web_elements_by_text(schema, text or "", role)
        else:
            schema = capture_macos_screen_schema("frontmost")
            elements = find_elements_by_text(schema, text or "", role)
        
        found_count = len(elements)
        
        if found_count >= count_gte:
            return VerificationResult(
                passed=True,
                message=f"Found {found_count} elements matching criteria (required: {count_gte})",
                details={"elements_found": found_count, "required_count": count_gte}
            ).to_dict()
        
        # Auto-retry: capture schema again and search nearby text
        retry_attempted = True
        time.sleep(0.5)
        
        if where == "web":
            schema = capture_web_screen_schema(None)
            # Try broader text search if original text was specific
            if text and len(text) > 3:
                broader_text = text[:len(text)//2]  # Use first half of text
                elements = find_web_elements_by_text(schema, broader_text, role)
        else:
            schema = capture_macos_screen_schema("frontmost")
            if text and len(text) > 3:
                broader_text = text[:len(text)//2]
                elements = find_elements_by_text(schema, broader_text, role)
        
        retry_count = len(elements)
        if retry_count >= count_gte:
            retry_successful = True
            return VerificationResult(
                passed=True,
                message=f"Found {retry_count} elements after retry (required: {count_gte})",
                retry_attempted=retry_attempted,
                retry_successful=retry_successful,
                details={"elements_found": retry_count, "required_count": count_gte}
            ).to_dict()
        
    except Exception as e:
        return VerificationResult(
            passed=False,
            message=f"Error during element assertion: {str(e)}",
            details={"error": str(e)}
        ).to_dict()
    
    return VerificationResult(
        passed=False,
        message=f"Found {found_count} elements, required {count_gte}",
        retry_attempted=retry_attempted,
        retry_successful=retry_successful,
        details={"elements_found": found_count, "required_count": count_gte}
    ).to_dict()


def assert_text(contains: str, where: str = "screen") -> Dict[str, Any]:
    """
    Assert that specific text appears on screen or web page.
    
    Args:
        contains: Text that must be present
        where: "screen" for macOS screen, "web" for web page
        
    Returns:
        Dictionary with verification result
    """
    retry_attempted = False
    retry_successful = False
    
    try:
        if where == "web":
            schema = capture_web_screen_schema(None)  # TODO: Get from runner state
            elements = find_web_elements_by_text(schema, contains)
        else:
            schema = capture_macos_screen_schema("frontmost")
            elements = find_elements_by_text(schema, contains)
        
        if elements:
            return VerificationResult(
                passed=True,
                message=f"Text found: '{contains}'",
                details={"text_found_in_elements": len(elements)}
            ).to_dict()
        
        # Auto-retry: capture schema again with slight delay
        retry_attempted = True
        time.sleep(0.5)
        
        if where == "web":
            schema = capture_web_screen_schema(None)
            elements = find_web_elements_by_text(schema, contains)
        else:
            schema = capture_macos_screen_schema("frontmost")
            elements = find_elements_by_text(schema, contains)
        
        if elements:
            retry_successful = True
            return VerificationResult(
                passed=True,
                message=f"Text found after retry: '{contains}'",
                retry_attempted=retry_attempted,
                retry_successful=retry_successful,
                details={"text_found_in_elements": len(elements)}
            ).to_dict()
        
    except Exception as e:
        return VerificationResult(
            passed=False,
            message=f"Error during text assertion: {str(e)}",
            details={"error": str(e)}
        ).to_dict()
    
    return VerificationResult(
        passed=False,
        message=f"Text not found: '{contains}'",
        retry_attempted=retry_attempted,
        retry_successful=retry_successful
    ).to_dict()


def assert_file_exists(path: str) -> Dict[str, Any]:
    """
    Assert that a file exists at the specified path.
    
    Args:
        path: Path to file that must exist
        
    Returns:
        Dictionary with verification result
    """
    expanded_path = Path(path).expanduser()
    
    if expanded_path.exists():
        return VerificationResult(
            passed=True,
            message=f"File exists: {path}",
            details={"path": str(expanded_path), "is_file": expanded_path.is_file()}
        ).to_dict()
    
    return VerificationResult(
        passed=False,
        message=f"File does not exist: {path}",
        details={"path": str(expanded_path)}
    ).to_dict()


def assert_pdf_pages(path: str, expected_pages: int) -> Dict[str, Any]:
    """
    Assert that a PDF file has the expected number of pages.
    
    Args:
        path: Path to PDF file
        expected_pages: Expected number of pages
        
    Returns:
        Dictionary with verification result
    """
    expanded_path = Path(path).expanduser()
    
    if not expanded_path.exists():
        return VerificationResult(
            passed=False,
            message=f"PDF file does not exist: {path}",
            details={"path": str(expanded_path)}
        ).to_dict()
    
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(expanded_path))
        actual_pages = len(reader.pages)
        
        if actual_pages == expected_pages:
            return VerificationResult(
                passed=True,
                message=f"PDF has expected {expected_pages} pages",
                details={"path": str(expanded_path), "actual_pages": actual_pages, "expected_pages": expected_pages}
            ).to_dict()
        
        return VerificationResult(
            passed=False,
            message=f"PDF has {actual_pages} pages, expected {expected_pages}",
            details={"path": str(expanded_path), "actual_pages": actual_pages, "expected_pages": expected_pages}
        ).to_dict()
        
    except ImportError:
        return VerificationResult(
            passed=False,
            message="PyPDF2 not installed. Run: pip install PyPDF2",
            details={"error": "Missing dependency"}
        ).to_dict()
    except Exception as e:
        return VerificationResult(
            passed=False,
            message=f"Error reading PDF: {str(e)}",
            details={"path": str(expanded_path), "error": str(e)}
        ).to_dict()


def capture_screen_schema(target: str = "frontmost") -> Dict[str, Any]:
    """
    Capture screen accessibility schema.
    
    Args:
        target: "frontmost" for active window, "screen" for full screen
        
    Returns:
        Dictionary with schema data and metadata
    """
    try:
        schema = capture_macos_screen_schema(target)
        
        return {
            "captured": True,
            "target": target,
            "element_count": len(schema.get("elements", [])),
            "schema": schema,
            "message": f"Screen schema captured for {target}"
        }
    except Exception as e:
        return {
            "captured": False,
            "target": target,
            "error": str(e),
            "message": f"Failed to capture screen schema: {str(e)}"
        }