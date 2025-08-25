"""
Resume functionality for interrupted runs.

Provides capability to pause, resume, and recover runs from any interruption point,
maintaining full execution history and state consistency.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class RunStatus(Enum):
    """Enhanced run status with pause/resume support."""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"  # New status for HITL or manual pause
    PAUSED_HITL = "paused_hitl"  # Paused waiting for human confirmation
    PAUSED_ERROR = "paused_error"  # Paused due to error requiring intervention
    RESUMED = "resumed"  # Resuming from pause
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ResumePoint:
    """Represents a point where a run can be resumed."""
    run_id: int
    step_index: int  # Index of the step to resume from
    step_name: str
    state_snapshot: Dict[str, Any]  # Runner state at this point
    created_at: datetime
    reason: str  # Why the run was paused (hitl, error, manual, etc.)
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step_index": self.step_index,
            "step_name": self.step_name,
            "state_snapshot": self.state_snapshot,
            "created_at": self.created_at.isoformat(),
            "reason": self.reason,
            "user_id": self.user_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResumePoint':
        return cls(
            run_id=data["run_id"],
            step_index=data["step_index"],
            step_name=data["step_name"],
            state_snapshot=data["state_snapshot"],
            created_at=datetime.fromisoformat(data["created_at"]),
            reason=data["reason"],
            user_id=data.get("user_id")
        )


class ResumeManager:
    """Manages run pause/resume functionality."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or str(Path.home() / ".desktop-agent" / "resume.db")
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # Metrics
        self.metrics = {
            "resumes_24h": 0,
            "hitl_pauses_24h": 0,
            "manual_pauses_24h": 0,
            "error_pauses_24h": 0,
            "successful_resumes_24h": 0,
            "failed_resumes_24h": 0
        }
    
    def _init_db(self):
        """Initialize the resume database."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS resume_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    step_index INTEGER NOT NULL,
                    step_name TEXT NOT NULL,
                    state_snapshot TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resumed_at TIMESTAMP,
                    success BOOLEAN,
                    UNIQUE(run_id)  -- Only one resume point per run
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pause_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    step_index INTEGER NOT NULL,
                    pause_reason TEXT NOT NULL,
                    paused_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resumed_at TIMESTAMP,
                    user_id TEXT
                )
            ''')
    
    def create_resume_point(self, run_id: int, step_index: int, step_name: str, 
                           runner_state: Dict[str, Any], reason: str, 
                           user_id: Optional[str] = None) -> ResumePoint:
        """Create a resume point for a run."""
        resume_point = ResumePoint(
            run_id=run_id,
            step_index=step_index,
            step_name=step_name,
            state_snapshot=runner_state,
            created_at=datetime.now(),
            reason=reason,
            user_id=user_id
        )
        
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO resume_points 
                (run_id, step_index, step_name, state_snapshot, reason, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                run_id, step_index, step_name, 
                json.dumps(runner_state), reason, user_id
            ))
            
            # Also record in pause history
            conn.execute('''
                INSERT INTO pause_history (run_id, step_index, pause_reason, user_id)
                VALUES (?, ?, ?, ?)
            ''', (run_id, step_index, reason, user_id))
        
        # Update metrics
        if reason == "hitl":
            self.metrics["hitl_pauses_24h"] += 1
        elif reason == "manual":
            self.metrics["manual_pauses_24h"] += 1
        elif reason == "error":
            self.metrics["error_pauses_24h"] += 1
        
        return resume_point
    
    def get_resume_point(self, run_id: int) -> Optional[ResumePoint]:
        """Get the resume point for a run."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM resume_points WHERE run_id = ?
            ''', (run_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return ResumePoint(
                run_id=row['run_id'],
                step_index=row['step_index'],
                step_name=row['step_name'],
                state_snapshot=json.loads(row['state_snapshot']),
                created_at=datetime.fromisoformat(row['created_at']),
                reason=row['reason'],
                user_id=row['user_id']
            )
    
    def resume_run(self, run_id: int, user_id: Optional[str] = None) -> bool:
        """Mark a run as resumed and clear its resume point."""
        resume_point = self.get_resume_point(run_id)
        if not resume_point:
            return False
        
        with sqlite3.connect(self.storage_path) as conn:
            # Mark resume point as resumed
            conn.execute('''
                UPDATE resume_points 
                SET resumed_at = CURRENT_TIMESTAMP, success = 1
                WHERE run_id = ?
            ''', (run_id,))
            
            # Update pause history
            conn.execute('''
                UPDATE pause_history 
                SET resumed_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND resumed_at IS NULL
            ''', (run_id,))
        
        self.metrics["resumes_24h"] += 1
        self.metrics["successful_resumes_24h"] += 1
        return True
    
    def cancel_resume(self, run_id: int, user_id: Optional[str] = None) -> bool:
        """Cancel a paused run (mark as failed)."""
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.execute('''
                UPDATE resume_points 
                SET resumed_at = CURRENT_TIMESTAMP, success = 0
                WHERE run_id = ?
            ''', (run_id,))
            
            if cursor.rowcount > 0:
                self.metrics["failed_resumes_24h"] += 1
                return True
        
        return False
    
    def list_paused_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all paused runs waiting for resume."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT rp.*, r.name as run_name, r.template as template
                FROM resume_points rp
                LEFT JOIN runs r ON rp.run_id = r.id
                WHERE rp.resumed_at IS NULL
                ORDER BY rp.created_at DESC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_pause_history(self, run_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pause/resume history."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = '''
                SELECT ph.*, r.name as run_name, r.template as template
                FROM pause_history ph
                LEFT JOIN runs r ON ph.run_id = r.id
            '''
            params = []
            
            if run_id:
                query += ' WHERE ph.run_id = ?'
                params.append(run_id)
            
            query += ' ORDER BY ph.paused_at DESC LIMIT ?'
            params.append(limit)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_resume_points(self, days: int = 30) -> int:
        """Clean up old resume points."""
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = cutoff - timedelta(days=days)
        
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.execute('''
                DELETE FROM resume_points 
                WHERE created_at < ? AND resumed_at IS NOT NULL
            ''', (cutoff.isoformat(),))
            
            deleted = cursor.rowcount
            
            # Also cleanup old pause history
            conn.execute('''
                DELETE FROM pause_history 
                WHERE paused_at < ?
            ''', (cutoff.isoformat(),))
        
        return deleted
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get resume-related metrics."""
        # Reset daily metrics if needed
        now = datetime.now()
        
        return {
            **self.metrics,
            "paused_runs_current": len(self.list_paused_runs()),
            "resume_success_rate_24h": self._calculate_success_rate()
        }
    
    def _calculate_success_rate(self) -> float:
        """Calculate resume success rate."""
        total = self.metrics["successful_resumes_24h"] + self.metrics["failed_resumes_24h"]
        if total == 0:
            return 1.0
        return round(self.metrics["successful_resumes_24h"] / total, 2)


# Enhanced Runner with resume support
class ResumableRunner:
    """Extended Runner class with pause/resume capabilities."""
    
    def __init__(self, plan: Dict[str, Any], variables: Dict[str, Any], 
                 dry_run: bool = False, run_id: Optional[int] = None,
                 resume_point: Optional[ResumePoint] = None):
        # Import the base Runner
        from app.dsl.runner import Runner
        
        self.base_runner = Runner(plan, variables, dry_run)
        self.run_id = run_id
        self.resume_point = resume_point
        self.resume_manager = get_resume_manager()
        
        # If resuming, restore state
        if resume_point:
            self.base_runner.state = resume_point.state_snapshot.get("runner_state", {})
            self.base_runner.step_results = resume_point.state_snapshot.get("step_results", [])
            self.base_runner.step_diffs = resume_point.state_snapshot.get("step_diffs", [])
    
    def execute_with_resume_support(self, steps: List[Dict[str, Any]], start_from: int = 0) -> List[Dict[str, Any]]:
        """Execute steps with resume support."""
        results = []
        
        # Determine starting point
        start_index = start_from
        if self.resume_point:
            start_index = self.resume_point.step_index
            # Copy previous results up to resume point
            results = self.base_runner.step_results[:start_index]
        
        # Execute remaining steps
        for i in range(start_index, len(steps)):
            step = steps[i]
            action = list(step.keys())[0]
            params = step[action]
            
            # Check for human_confirm steps that need pause
            if action == "human_confirm" and not params.get("auto_approve", False):
                # Create resume point before HITL step
                if self.run_id:
                    self._create_resume_point(i, action, "hitl")
                    # Update run status to PAUSED_HITL
                    self._update_run_status(RunStatus.PAUSED_HITL)
                    
                    return {
                        "status": "paused_hitl",
                        "message": params.get("message", "Waiting for human confirmation"),
                        "resume_point": i,
                        "results": results
                    }
            
            try:
                # Execute the step
                result = self.base_runner.execute_step_with_diff(action, params)
                results.append(result)
                
                # Check for critical errors that should pause
                if isinstance(result, dict) and result.get("status") in ["critical_error", "permission_denied"]:
                    if self.run_id:
                        self._create_resume_point(i + 1, action, "error")
                        self._update_run_status(RunStatus.PAUSED_ERROR)
                        
                        return {
                            "status": "paused_error",
                            "message": f"Critical error in step {i}: {result.get('error', 'Unknown error')}",
                            "resume_point": i + 1,
                            "results": results
                        }
                
            except Exception as e:
                # Handle unexpected errors
                error_result = {
                    "status": "error", 
                    "error": str(e),
                    "step_index": i,
                    "action": action
                }
                results.append(error_result)
                
                # Create resume point for manual intervention
                if self.run_id:
                    self._create_resume_point(i + 1, action, "error")
                    self._update_run_status(RunStatus.PAUSED_ERROR)
                    
                    return {
                        "status": "paused_error",
                        "message": f"Unexpected error in step {i}: {str(e)}",
                        "resume_point": i + 1,
                        "results": results
                    }
        
        # All steps completed successfully
        if self.run_id and self.resume_point:
            # Mark resume as successful
            self.resume_manager.resume_run(self.run_id)
            self._update_run_status(RunStatus.SUCCESS)
        
        return {
            "status": "completed",
            "results": results
        }
    
    def _create_resume_point(self, step_index: int, step_name: str, reason: str):
        """Create a resume point."""
        if not self.run_id:
            return
        
        state_snapshot = {
            "runner_state": self.base_runner.state,
            "step_results": self.base_runner.step_results,
            "step_diffs": self.base_runner.step_diffs,
            "variables": self.base_runner.vars
        }
        
        self.resume_manager.create_resume_point(
            run_id=self.run_id,
            step_index=step_index,
            step_name=step_name,
            runner_state=state_snapshot,
            reason=reason
        )
    
    def _update_run_status(self, status: RunStatus):
        """Update run status in database."""
        if not self.run_id:
            return
        
        try:
            from app.models import get_conn
            conn = get_conn()
            conn.execute(
                "UPDATE runs SET status = ? WHERE id = ?",
                (status.value, self.run_id)
            )
            conn.commit()
        except Exception as e:
            print(f"Failed to update run status: {e}")


# Global resume manager
_resume_manager = None

def get_resume_manager() -> ResumeManager:
    """Get the global resume manager instance."""
    global _resume_manager
    if _resume_manager is None:
        _resume_manager = ResumeManager()
    return _resume_manager