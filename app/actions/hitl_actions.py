"""
Human-in-the-Loop (HITL) actions for Phase 4.

Provides human confirmation and intervention capabilities during run execution.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

from ..models import get_conn
from ..utils import get_logger

logger = get_logger()


def human_confirm(message: str, timeout_ms: int = 600000, auto_approve: bool = False) -> Dict[str, Any]:
    """
    Request human confirmation during run execution.
    
    This pauses the run and waits for human input via the UI.
    
    Args:
        message: The confirmation message to display to the user
        timeout_ms: Timeout in milliseconds (default 10 minutes)
        auto_approve: If True, automatically approve after a short delay (for testing)
    
    Returns:
        Dict with confirmation result
    """
    logger.info(f"Requesting human confirmation: {message}")
    
    if auto_approve:
        logger.info("Auto-approving confirmation for testing")
        time.sleep(1)  # Brief delay to simulate user decision
        return {
            "confirmed": True,
            "response_time_ms": 1000,
            "message": message,
            "auto_approved": True
        }
    
    # Create confirmation record in database
    conn = get_conn()
    cur = conn.cursor()
    
    confirmation_id = _create_confirmation_record(cur, message, timeout_ms)
    
    # Wait for human response or timeout
    start_time = time.time()
    timeout_seconds = timeout_ms / 1000.0
    
    while time.time() - start_time < timeout_seconds:
        # Check if confirmation has been responded to
        cur.execute("""
            SELECT status, response, responded_at 
            FROM human_confirmations 
            WHERE id = ?
        """, (confirmation_id,))
        
        row = cur.fetchone()
        if row and row["status"] != "pending":
            response_time_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "confirmed": row["status"] == "approved",
                "response_time_ms": response_time_ms,
                "message": message,
                "user_response": row["response"],
                "responded_at": row["responded_at"]
            }
            
            logger.info(f"Human confirmation {row['status']}: {message}")
            return result
        
        # Poll every second
        time.sleep(1.0)
    
    # Timeout reached
    _update_confirmation_status(cur, confirmation_id, "timeout", "Timed out after {}ms".format(timeout_ms))
    conn.commit()
    conn.close()
    
    logger.warning(f"Human confirmation timed out: {message}")
    return {
        "confirmed": False,
        "response_time_ms": timeout_ms,
        "message": message,
        "timeout": True,
        "error": f"No response within {timeout_ms}ms"
    }


def _create_confirmation_record(cur, message: str, timeout_ms: int) -> str:
    """Create a human confirmation record in the database."""
    confirmation_id = f"confirm_{int(time.time() * 1000)}"
    timeout_at = datetime.now() + timedelta(milliseconds=timeout_ms)
    
    # Ensure the table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS human_confirmations (
            id TEXT PRIMARY KEY,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded_at TIMESTAMP,
            timeout_at TIMESTAMP,
            run_id TEXT
        )
    """)
    
    cur.execute("""
        INSERT INTO human_confirmations (id, message, timeout_at)
        VALUES (?, ?, ?)
    """, (confirmation_id, message, timeout_at))
    
    cur.connection.commit()
    return confirmation_id


def _update_confirmation_status(cur, confirmation_id: str, status: str, response: Optional[str] = None):
    """Update the status of a human confirmation."""
    cur.execute("""
        UPDATE human_confirmations 
        SET status = ?, response = ?, responded_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, response, confirmation_id))
    cur.connection.commit()


def get_pending_confirmations() -> list:
    """Get all pending human confirmations."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, message, created_at, timeout_at, run_id
        FROM human_confirmations 
        WHERE status = 'pending' AND timeout_at > CURRENT_TIMESTAMP
        ORDER BY created_at ASC
    """)
    
    confirmations = []
    for row in cur.fetchall():
        confirmations.append({
            "id": row["id"],
            "message": row["message"],
            "created_at": row["created_at"],
            "timeout_at": row["timeout_at"],
            "run_id": row["run_id"]
        })
    
    conn.close()
    return confirmations


def respond_to_confirmation(confirmation_id: str, approved: bool, response: str = "") -> bool:
    """Respond to a human confirmation request."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if confirmation exists and is still pending
    cur.execute("""
        SELECT status, timeout_at FROM human_confirmations 
        WHERE id = ?
    """, (confirmation_id,))
    
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    
    if row["status"] != "pending":
        logger.warning(f"Confirmation {confirmation_id} already has status: {row['status']}")
        conn.close()
        return False
    
    # Check if timed out
    if datetime.fromisoformat(row["timeout_at"]) < datetime.now():
        logger.warning(f"Confirmation {confirmation_id} has timed out")
        _update_confirmation_status(cur, confirmation_id, "timeout", "Timed out")
        conn.close()
        return False
    
    # Update with response
    status = "approved" if approved else "denied"
    _update_confirmation_status(cur, confirmation_id, status, response)
    
    logger.info(f"Confirmation {confirmation_id} {status}: {response}")
    conn.close()
    return True


def get_confirmation_metrics() -> Dict[str, Any]:
    """Get HITL confirmation metrics."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS human_confirmations (
            id TEXT PRIMARY KEY,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded_at TIMESTAMP,
            timeout_at TIMESTAMP,
            run_id TEXT
        )
    """)
    
    # Get metrics for last 24 hours
    cur.execute("""
        SELECT 
            COUNT(*) as total_confirmations,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied,
            SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeouts
        FROM human_confirmations 
        WHERE created_at >= datetime('now', '-1 day')
    """)
    
    row = cur.fetchone()
    
    metrics = {
        "hitl_interventions_24h": row["total_confirmations"] or 0,
        "hitl_approved_24h": row["approved"] or 0,
        "hitl_denied_24h": row["denied"] or 0,
        "hitl_timeouts_24h": row["timeouts"] or 0
    }
    
    # Calculate approval rate
    if metrics["hitl_interventions_24h"] > 0:
        metrics["hitl_approval_rate_24h"] = metrics["hitl_approved_24h"] / metrics["hitl_interventions_24h"]
    else:
        metrics["hitl_approval_rate_24h"] = 0.0
    
    conn.close()
    return metrics