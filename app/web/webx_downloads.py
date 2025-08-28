"""
WebX Download Manager - Phase 7
Advanced download monitoring and verification capabilities
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class DownloadVerificationError(Exception):
    """Raised when download verification fails"""
    pass


@dataclass
class DownloadInfo:
    """Information about a download operation"""
    file_path: str
    file_name: str
    file_size: int
    download_url: Optional[str] = None
    mime_type: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verified: bool = False

    @property
    def download_duration(self) -> Optional[float]:
        """Calculate download duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class WebXDownloadManager:
    """Manages download operations and verification"""

    def __init__(self, browser_context=None):
        """Initialize download manager"""
        self.browser_context = browser_context
        self.downloads: Dict[str, DownloadInfo] = {}
        self.active_downloads: List[str] = []
        self.completed_downloads: List[str] = []

        logger.info("WebX Download Manager initialized")

    def wait_for_download(
        self,
        to: str,
        timeout_ms: int = 30000,
        expected_filename: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Wait for download to complete and verify file

        Args:
            to: Download directory path
            timeout_ms: Maximum time to wait for download
            expected_filename: Expected filename (optional)
            min_size: Minimum expected file size in bytes
            max_size: Maximum expected file size in bytes

        Returns:
            Dict with download result and file information
        """
        try:
            download_dir = Path(to)
            if not download_dir.exists():
                download_dir.mkdir(parents=True, exist_ok=True)

            # Track start time if needed for additional metrics
            _ = time.time()
            timeout_seconds = timeout_ms / 1000.0

            logger.info(f"Waiting for download in {download_dir} (timeout: {timeout_seconds}s)")

            # Monitor downloads
            download_info = self._monitor_downloads(
                download_dir,
                timeout_seconds,
                expected_filename,
                min_size,
                max_size
            )

            if not download_info["completed"]:
                if download_info.get("timeout"):
                    raise DownloadVerificationError(
                        f"Download timeout after {timeout_seconds}s in {download_dir}"
                    )
                else:
                    raise DownloadVerificationError(
                        f"Download failed: {download_info.get('error', 'Unknown error')}"
                    )

            # Verify downloaded file
            file_path = download_info["file_path"]
            verification_result = self._verify_download(
                file_path,
                min_size,
                max_size
            )

            if not verification_result["valid"]:
                raise DownloadVerificationError(
                    f"Download verification failed: {verification_result['error']}"
                )

            # Record successful download
            download_record = DownloadInfo(
                file_path=file_path,
                file_name=Path(file_path).name,
                file_size=verification_result["file_size"],
                completed_at=datetime.now(timezone.utc),
                verified=True
            )

            self.downloads[file_path] = download_record
            self.completed_downloads.append(file_path)

            logger.info(f"Download completed and verified: {file_path}")

            return {
                "success": True,
                "file_path": file_path,
                "file_name": download_record.file_name,
                "file_size": download_record.file_size,
                "download_duration": download_info.get("download_duration", 0),
                "verified": True,
                "verification_details": verification_result
            }

        except Exception as e:
            logger.error(f"Download operation failed: {e}")
            raise DownloadVerificationError(str(e))

    def assert_file_exists(
        self,
        file_path: str,
        min_size: Optional[int] = None,
        max_age_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Assert that file exists and meets criteria

        Args:
            file_path: Path to file to verify
            min_size: Minimum file size in bytes
            max_age_seconds: Maximum file age in seconds

        Returns:
            Dict with assertion results
        """
        try:
            file_obj = Path(file_path)

            # Check existence
            if not file_obj.exists():
                return {
                    "success": False,
                    "file_exists": False,
                    "error": f"File does not exist: {file_path}"
                }

            # Get file stats
            file_stats = file_obj.stat()
            file_size = file_stats.st_size
            file_mtime = file_stats.st_mtime

            # Check size requirement
            size_valid = True
            if min_size is not None and file_size < min_size:
                size_valid = False

            # Check age requirement
            age_valid = True
            file_age_seconds = time.time() - file_mtime
            if max_age_seconds is not None and file_age_seconds > max_age_seconds:
                age_valid = False

            success = size_valid and age_valid

            result = {
                "success": success,
                "file_exists": True,
                "file_path": str(file_obj.absolute()),
                "file_size": file_size,
                "file_age_seconds": file_age_seconds,
                "size_valid": size_valid,
                "age_valid": age_valid
            }

            if not success:
                errors = []
                if not size_valid:
                    errors.append(f"File size {file_size} below minimum {min_size}")
                if not age_valid:
                    errors.append(f"File age {file_age_seconds:.1f}s exceeds maximum {max_age_seconds}s")
                result["error"] = "; ".join(errors)

            logger.info(f"File assertion {'passed' if success else 'failed'}: {file_path}")
            return result

        except Exception as e:
            logger.error(f"File assertion error: {e}")
            return {
                "success": False,
                "file_exists": False,
                "error": str(e)
            }

    def get_download_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent download history"""
        recent_downloads = []

        for file_path in self.completed_downloads[-limit:]:
            download_info = self.downloads.get(file_path)
            if download_info:
                recent_downloads.append({
                    "file_path": download_info.file_path,
                    "file_name": download_info.file_name,
                    "file_size": download_info.file_size,
                    "completed_at": download_info.completed_at.isoformat() if download_info.completed_at else None,
                    "download_duration": download_info.download_duration,
                    "verified": download_info.verified
                })

        return recent_downloads

    def clean_old_downloads(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """Clean old downloads from tracking"""
        current_time = datetime.now(timezone.utc)
        cleaned_count = 0

        downloads_to_remove = []

        for file_path, download_info in self.downloads.items():
            if download_info.completed_at:
                age_hours = (current_time - download_info.completed_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    downloads_to_remove.append(file_path)

        for file_path in downloads_to_remove:
            del self.downloads[file_path]
            if file_path in self.completed_downloads:
                self.completed_downloads.remove(file_path)
            cleaned_count += 1

        logger.info(f"Cleaned {cleaned_count} old downloads (older than {max_age_hours}h)")

        return {
            "cleaned_count": cleaned_count,
            "remaining_downloads": len(self.downloads)
        }

    def _monitor_downloads(
        self,
        download_dir: Path,
        timeout_seconds: float,
        expected_filename: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Monitor directory for download completion"""
        start_time = time.time()
        initial_files = set(download_dir.glob("*"))

        while time.time() - start_time < timeout_seconds:
            current_files = set(download_dir.glob("*"))
            new_files = current_files - initial_files

            for new_file in new_files:
                if new_file.is_file():
                    # Check if filename matches expectation
                    if expected_filename and new_file.name != expected_filename:
                        continue

                    # Check if file is still being written (size changing)
                    if self._is_file_stable(new_file):
                        file_size = new_file.stat().st_size

                        # Check size constraints
                        if min_size and file_size < min_size:
                            continue
                        if max_size and file_size > max_size:
                            continue

                        # File looks complete
                        download_duration = time.time() - start_time

                        return {
                            "completed": True,
                            "file_path": str(new_file),
                            "file_size": file_size,
                            "download_duration": download_duration
                        }

            # Short sleep to avoid busy waiting
            time.sleep(0.5)

        # Timeout reached
        return {"completed": False, "timeout": True}

    def _is_file_stable(self, file_path: Path, stability_checks: int = 3) -> bool:
        """Check if file size is stable (not being written to)"""
        if not file_path.exists():
            return False

        try:
            previous_size = file_path.stat().st_size

            for _ in range(stability_checks):
                time.sleep(0.2)  # 200ms between checks
                current_size = file_path.stat().st_size

                if current_size != previous_size:
                    return False  # File is still being written

                previous_size = current_size

            return True  # File size is stable

        except (OSError, IOError):
            return False

    def _verify_download(
        self,
        file_path: str,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Verify downloaded file meets requirements"""
        try:
            file_obj = Path(file_path)

            if not file_obj.exists():
                return {"valid": False, "error": "File does not exist"}

            file_size = file_obj.stat().st_size

            # Size validation
            if min_size and file_size < min_size:
                return {
                    "valid": False,
                    "error": f"File size {file_size} below minimum {min_size}",
                    "file_size": file_size
                }

            if max_size and file_size > max_size:
                return {
                    "valid": False,
                    "error": f"File size {file_size} exceeds maximum {max_size}",
                    "file_size": file_size
                }

            # Additional validation could be added here
            # (file type verification, content validation, etc.)

            return {
                "valid": True,
                "file_size": file_size,
                "file_type": file_obj.suffix,
                "verification_passed": True
            }

        except Exception as e:
            return {"valid": False, "error": str(e)}


# Global download manager instance
_download_manager: Optional[WebXDownloadManager] = None


def get_download_manager() -> WebXDownloadManager:
    """Get global WebX download manager instance"""
    global _download_manager
    if _download_manager is None:
        _download_manager = WebXDownloadManager()
    return _download_manager


def webx_wait_for_download(to: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function for download waiting

    Usage:
        webx_wait_for_download(to="/tmp", timeout_ms=30000)
        webx_wait_for_download(to="/downloads", expected_filename="report.pdf")
    """
    download_manager = get_download_manager()
    return download_manager.wait_for_download(to, **kwargs)


def assert_file_exists(file_path: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function for file existence assertion

    Usage:
        assert_file_exists("/tmp/report.pdf", min_size=1024)
        assert_file_exists("/downloads/data.csv", max_age_seconds=300)
    """
    download_manager = get_download_manager()
    return download_manager.assert_file_exists(file_path, **kwargs)
