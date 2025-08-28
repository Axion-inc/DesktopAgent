"""
WebX Frame Management - Phase 7
Advanced iframe navigation and frame switching capabilities
"""

import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass


logger = logging.getLogger(__name__)


class FrameSwitchError(Exception):
    """Raised when frame switching operations fail"""
    pass


@dataclass
class FrameInfo:
    """Information about a browser frame"""
    url: str
    name: str
    index: int
    title: Optional[str] = None
    is_main_frame: bool = False
    parent_frame: Optional['FrameInfo'] = None


class WebXFrameManager:
    """Manages iframe selection and navigation"""

    def __init__(self, browser_context=None):
        """Initialize frame manager with browser context"""
        self.browser_context = browser_context
        self.current_frame: Optional[FrameInfo] = None
        self.frame_switch_count = 0

        logger.info("WebX Frame Manager initialized")

    def select_frame(
        self,
        by: str,
        value: Union[str, int],
        timeout_ms: int = 10000
    ) -> Dict[str, Any]:
        """
        Select iframe by URL, name, or index

        Args:
            by: Selection method ("url", "name", "index")
            value: URL pattern, frame name, or index number
            timeout_ms: Timeout for frame switching

        Returns:
            Dict with selection result and frame info
        """
        try:
            available_frames = self._get_available_frames()

            if not available_frames:
                raise FrameSwitchError("No frames available for selection")

            selected_frame = None

            if by == "url":
                selected_frame = self._find_frame_by_url(available_frames, str(value))
            elif by == "name":
                selected_frame = self._find_frame_by_name(available_frames, str(value))
            elif by == "index":
                selected_frame = self._find_frame_by_index(available_frames, int(value))
            else:
                raise FrameSwitchError(f"Invalid selection method: {by}")

            if not selected_frame:
                raise FrameSwitchError(f"Frame not found: {by}={value}")

            # Perform the actual frame switch
            switch_result = self._perform_frame_switch(selected_frame)

            if switch_result["success"]:
                self.current_frame = FrameInfo(**selected_frame)
                self._record_frame_switch_metrics()

                logger.info(f"Successfully switched to frame: {by}={value}")

                return {
                    "success": True,
                    "selected_frame": selected_frame,
                    "frame_index": selected_frame["index"],
                    "previous_frame": self.current_frame,
                    "switch_duration_ms": switch_result.get("duration_ms", 0)
                }
            else:
                raise FrameSwitchError(f"Frame switch failed: {switch_result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Frame selection failed: {e}")
            raise FrameSwitchError(str(e))

    def get_current_frame(self) -> Optional[Dict[str, Any]]:
        """Get information about currently selected frame"""
        if self.current_frame:
            return {
                "url": self.current_frame.url,
                "name": self.current_frame.name,
                "index": self.current_frame.index,
                "title": self.current_frame.title,
                "is_main_frame": self.current_frame.is_main_frame
            }
        return None

    def list_available_frames(self) -> List[Dict[str, Any]]:
        """List all available frames in current context"""
        try:
            frames = self._get_available_frames()
            logger.info(f"Found {len(frames)} available frames")
            return frames
        except Exception as e:
            logger.error(f"Failed to list frames: {e}")
            return []

    def switch_to_main_frame(self) -> Dict[str, Any]:
        """Switch back to main frame (exit all iframes)"""
        try:
            # Switch to main frame
            main_frame_info = {
                "url": "main",
                "name": "main",
                "index": -1,
                "is_main_frame": True
            }

            switch_result = self._perform_frame_switch(main_frame_info)

            if switch_result["success"]:
                self.current_frame = FrameInfo(**main_frame_info)
                self._record_frame_switch_metrics()

                logger.info("Switched to main frame")
                return {"success": True, "frame": "main"}
            else:
                raise FrameSwitchError("Failed to switch to main frame")

        except Exception as e:
            logger.error(f"Main frame switch failed: {e}")
            raise FrameSwitchError(str(e))

    def _get_available_frames(self) -> List[Dict[str, Any]]:
        """Get list of available frames from browser context"""
        # Mock implementation - in real usage this would query the browser
        if hasattr(self, '_mock_frames'):
            return self._mock_frames

        # Default mock frames for testing
        return [
            {
                "url": "https://example.com/main",
                "name": "main-frame",
                "index": 0,
                "title": "Main Frame",
                "is_main_frame": True
            }
        ]

    def _find_frame_by_url(self, frames: List[Dict], url_pattern: str) -> Optional[Dict]:
        """Find frame by URL pattern matching"""
        for frame in frames:
            frame_url = frame.get("url", "")
            if url_pattern.lower() in frame_url.lower():
                return frame
        return None

    def _find_frame_by_name(self, frames: List[Dict], name: str) -> Optional[Dict]:
        """Find frame by exact name match"""
        for frame in frames:
            if frame.get("name", "") == name:
                return frame
        return None

    def _find_frame_by_index(self, frames: List[Dict], index: int) -> Optional[Dict]:
        """Find frame by index"""
        for frame in frames:
            if frame.get("index", -1) == index:
                return frame
        return None

    def _perform_frame_switch(self, frame_info: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual browser frame switch operation"""
        # Mock implementation - in real usage this would interact with browser
        try:
            # Simulate frame switching delay
            import time
            start_time = time.time()

            # Mock frame switch operation
            if frame_info.get("index", 0) >= 0:
                # Valid frame switch
                end_time = time.time()
                duration_ms = int((end_time - start_time) * 1000)

                return {
                    "success": True,
                    "duration_ms": duration_ms,
                    "frame_url": frame_info.get("url", ""),
                    "frame_name": frame_info.get("name", "")
                }
            else:
                return {"success": False, "error": "Invalid frame index"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _record_frame_switch_metrics(self):
        """Record frame switching metrics"""
        self.frame_switch_count += 1

        try:
            from app.metrics import get_metrics_collector
            metrics = get_metrics_collector()
            metrics.increment_counter('webx_frame_switches_24h')

            logger.debug(f"Recorded frame switch metric (total: {self.frame_switch_count})")

        except Exception as e:
            logger.error(f"Failed to record frame switch metrics: {e}")

    def get_frame_metrics(self) -> Dict[str, Any]:
        """Get frame management metrics"""
        return {
            "total_switches": self.frame_switch_count,
            "current_frame": self.get_current_frame(),
            "available_frames": len(self.list_available_frames())
        }


# Global frame manager instance
_frame_manager: Optional[WebXFrameManager] = None


def get_frame_manager() -> WebXFrameManager:
    """Get global WebX frame manager instance"""
    global _frame_manager
    if _frame_manager is None:
        _frame_manager = WebXFrameManager()
    return _frame_manager


def webx_frame_select(by: str, value: Union[str, int], **kwargs) -> Dict[str, Any]:
    """
    Convenience function for frame selection

    Usage:
        webx_frame_select(by="url", value="partner.example.com")
        webx_frame_select(by="name", value="widget-frame")
        webx_frame_select(by="index", value=1)
    """
    frame_manager = get_frame_manager()
    return frame_manager.select_frame(by, value, **kwargs)
