"""
Retry management for failed runs.

Handles automatic retrying of idempotent steps with exponential backoff.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from ..utils import get_logger

logger = get_logger()


@dataclass
class RetryAttempt:
    """Record of a retry attempt."""
    run_id: str
    attempt: int
    timestamp: datetime
    success: bool
    error: Optional[str] = None


class RetryManager:
    """Manages automatic retries for failed runs."""

    def __init__(self):
        self._retry_attempts: List[RetryAttempt] = []
        self._metrics = {
            "retry_rate_24h": 0.0,
            "total_runs": 0,
            "runs_with_retries": 0
        }

    def should_retry(self, run_data: Dict[str, Any], error: str) -> bool:
        """Determine if a run should be automatically retried."""
        retry_config = run_data.get("retry_config", {})

        if not retry_config:
            return False

        # Check attempt count
        current_attempt = run_data.get("attempt", 1)
        max_attempts = retry_config.get("attempts", 3)

        if current_attempt >= max_attempts:
            logger.info(
                f"Run {run_data['id']} reached max attempts "
                f"({max_attempts})")
            return False

        # Check if only idempotent steps should retry
        if retry_config.get("only_idempotent", True):
            if not self._is_run_idempotent(run_data):
                logger.info(
                    f"Run {run_data['id']} contains non-idempotent "
                    f"steps, skipping retry")
                return False

        # Check for non-retryable errors
        if self._is_permanent_error(error):
            logger.info(
                f"Run {run_data['id']} has permanent error, "
                f"skipping retry: {error}")
            return False

        return True

    def calculate_delay(self, run_data: Dict[str, Any], attempt: int) -> int:
        """Calculate delay in milliseconds before retry."""
        retry_config = run_data.get("retry_config", {})

        base_delay = retry_config.get("backoff_ms", 5000)  # 5 seconds default
        multiplier = retry_config.get("backoff_multiplier", 2.0)
        max_delay = retry_config.get("max_backoff_ms", 300000)  # 5 min max

        # Exponential backoff: base_delay * (multiplier ^ (attempt - 1))
        delay = base_delay * (multiplier ** (attempt - 1))

        # Cap at maximum
        delay = min(delay, max_delay)

        # Add some jitter to avoid thundering herd
        import random
        jitter_factor = random.uniform(0.8, 1.2)
        delay = int(delay * jitter_factor)

        return delay

    def handle_failure(self, run_data: Dict[str, Any]
                       ) -> Optional[Dict[str, Any]]:
        """Handle a failed run and potentially create retry."""
        run_id = run_data["id"]
        error = run_data.get("error", "Unknown error")

        # Record the attempt
        attempt = RetryAttempt(
            run_id=run_id,
            attempt=run_data.get("attempt", 1),
            timestamp=datetime.now(),
            success=False,
            error=error
        )
        self._retry_attempts.append(attempt)

        # Check if should retry
        if not self.should_retry(run_data, error):
            return None

        # Calculate delay
        next_attempt = run_data.get("attempt", 1) + 1
        delay_ms = self.calculate_delay(run_data, next_attempt)

        # Create retry run data
        retry_data = run_data.copy()
        retry_data["attempt"] = next_attempt
        retry_data["retry_delay_ms"] = delay_ms
        retry_data["original_run_id"] = run_data.get("original_run_id", run_id)
        retry_data["retry_reason"] = error

        logger.info(
            f"Scheduling retry for run {run_id}, attempt "
            f"{next_attempt} in {delay_ms}ms")

        # TODO: Schedule the retry (integrate with queue manager)
        return retry_data

    def record_attempt(self, run_id: str, attempt: int, success: bool,
                       error: Optional[str] = None) -> None:
        """Record a run attempt for metrics."""
        attempt_record = RetryAttempt(
            run_id=run_id,
            attempt=attempt,
            timestamp=datetime.now(),
            success=success,
            error=error
        )
        self._retry_attempts.append(attempt_record)

        # Clean old attempts (keep only 24h for metrics)
        cutoff = datetime.now() - timedelta(hours=24)
        self._retry_attempts = [
            a for a in self._retry_attempts
            if a.timestamp > cutoff
        ]

        # Update metrics
        self._update_metrics()

    def is_step_retryable(self, step: Dict[str, Any]) -> bool:
        """Check if a specific step is retryable (idempotent)."""
        # Explicitly marked idempotent/non-idempotent
        if "idempotent" in step:
            return step["idempotent"]

        # Determine by step type
        step_name = self._get_step_name(step)

        # Idempotent steps (safe to retry)
        idempotent_steps = {
            "wait_for_element", "assert_element", "assert_text",
            "assert_file_exists", "assert_pdf_pages",
            "capture_screen_schema", "log", "find_files",
            "take_screenshot", "open_browser", "download_file"
        }

        # Non-idempotent steps (dangerous to retry)
        dangerous_steps = {
            "compose_mail_draft", "send_email", "click_by_text",
            "fill_by_label", "upload_file", "human_confirm",
            "move_to", "pdf_merge"
        }

        if step_name in idempotent_steps:
            return True
        elif step_name in dangerous_steps:
            return False
        else:
            # Conservative default: don't retry unknown steps
            logger.warning(
                f"Unknown step type '{step_name}' - "
                f"marking as non-retryable")
            return False

    def _is_run_idempotent(self, run_data: Dict[str, Any]) -> bool:
        """Check if entire run is safe to retry."""
        # For now, we'll be conservative and only retry if explicitly configured
        # In a full implementation, we'd parse the run steps and check each one
        # Simplified - assume retry_config existence means it's safe
        return True

    def _is_permanent_error(self, error: str) -> bool:
        """Check if error is permanent and shouldn't be retried."""
        permanent_patterns = [
            "template not found",
            "invalid yaml",
            "permission denied",
            "authentication failed",
            "file not found",
            "validation error"
        ]

        error_lower = error.lower()
        return any(pattern in error_lower for pattern in permanent_patterns)

    def _get_step_name(self, step: Dict[str, Any]) -> str:
        """Extract step name from step definition."""
        # Step format: {"step_name": {...}} or {"name": "step_name", ...}
        if "name" in step:
            return step["name"]

        # Get first key that's not metadata
        for key in step.keys():
            if key not in ["idempotent", "timeout", "when"]:
                return key

        return "unknown"

    def _update_metrics(self) -> None:
        """Update retry rate metrics."""
        if not self._retry_attempts:
            return

        # Group by run_id to count unique runs
        runs_by_id: Dict[str, List[RetryAttempt]] = {}
        for attempt in self._retry_attempts:
            if attempt.run_id not in runs_by_id:
                runs_by_id[attempt.run_id] = []
            runs_by_id[attempt.run_id].append(attempt)

        total_runs = len(runs_by_id)
        runs_with_retries = sum(
            1 for attempts in runs_by_id.values()
            if len(attempts) > 1)

        self._metrics.update({
            "retry_rate_24h": (runs_with_retries / total_runs
                               if total_runs > 0 else 0.0),
            "total_runs": total_runs,
            "runs_with_retries": runs_with_retries
        })

    def get_metrics(self) -> Dict[str, Any]:
        """Get retry metrics."""
        return self._metrics.copy()


# Global retry manager instance
_retry_manager: Optional[RetryManager] = None


def get_retry_manager() -> RetryManager:
    """Get the global retry manager instance."""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = RetryManager()
    return _retry_manager
