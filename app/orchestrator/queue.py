"""
Queue management for run orchestration.

Provides priority queuing, concurrency control, and run lifecycle management.
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from queue import PriorityQueue
from collections import defaultdict
import sqlite3
import logging

from ..models import get_conn
from ..utils import get_logger

logger = get_logger()


@dataclass
class QueuedRun:
    """Represents a queued run with priority and metadata."""
    id: str
    template: str
    priority: int  # 1 (low) to 9 (high)
    queue: str
    concurrency_tag: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    retry_config: Optional[Dict[str, Any]] = None
    enqueued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    user_id: Optional[str] = None
    
    def __post_init__(self):
        if self.enqueued_at is None:
            self.enqueued_at = datetime.now()
    
    def __lt__(self, other):
        # Higher priority first, then FIFO for same priority
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority = lower in PriorityQueue
        return self.enqueued_at < other.enqueued_at


@dataclass 
class QueueConfig:
    """Configuration for a queue."""
    name: str
    max_concurrent: int = 2
    max_queued: int = 100
    enabled: bool = True


class RunQueue:
    """Individual queue for managing runs."""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self._queue = PriorityQueue(maxsize=config.max_queued)
        self._running: Dict[str, QueuedRun] = {}
        self._lock = threading.RLock()
        
    def enqueue(self, run: QueuedRun) -> None:
        """Add run to queue."""
        with self._lock:
            if self._queue.full():
                raise RuntimeError(f"Queue '{self.config.name}' is full")
            
            self._queue.put(run)
            logger.info(f"Enqueued run {run.id} in queue {self.config.name} with priority {run.priority}")
    
    def dequeue(self) -> Optional[QueuedRun]:
        """Get next run from queue if concurrency allows."""
        with self._lock:
            if len(self._running) >= self.config.max_concurrent:
                return None  # At concurrency limit
            
            if self._queue.empty():
                return None  # No runs waiting
            
            run = self._queue.get()
            run.started_at = datetime.now()
            self._running[run.id] = run
            
            logger.info(f"Dequeued run {run.id} from queue {self.config.name}")
            return run
    
    def complete(self, run_id: str) -> None:
        """Mark run as completed and remove from running."""
        with self._lock:
            if run_id in self._running:
                del self._running[run_id]
                logger.info(f"Completed run {run_id} in queue {self.config.name}")
    
    def size(self) -> int:
        """Total size (queued + running)."""
        return self._queue.qsize() + len(self._running)
    
    def get_running(self) -> List[QueuedRun]:
        """Get currently running runs."""
        with self._lock:
            return list(self._running.values())
    
    def get_queued(self) -> List[QueuedRun]:
        """Get queued runs (not started yet)."""
        with self._lock:
            queued = []
            temp_queue = []
            
            # Extract all items to inspect
            while not self._queue.empty():
                run = self._queue.get()
                temp_queue.append(run)
                queued.append(run)
            
            # Put them back
            for run in temp_queue:
                self._queue.put(run)
            
            return queued


class QueueManager:
    """Manages multiple queues and concurrency control."""
    
    def __init__(self, config_file: Optional[str] = None):
        self._queues: Dict[str, RunQueue] = {}
        self._tag_limits: Dict[str, int] = {}
        self._tag_running: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()
        self._metrics = {
            "queue_depth_peak_24h": 0,
            "runs_per_hour_24h": 0,
            "completed_runs": []
        }
        
        # Create default queue
        self.create_queue("default", max_concurrent=2, max_queued=50)
        
        if config_file:
            self.load_config(config_file)
    
    def create_queue(self, name: str, max_concurrent: int = 2, max_queued: int = 50) -> RunQueue:
        """Create a new queue."""
        config = QueueConfig(
            name=name,
            max_concurrent=max_concurrent,
            max_queued=max_queued
        )
        queue = RunQueue(config)
        self._queues[name] = queue
        
        logger.info(f"Created queue '{name}' with max_concurrent={max_concurrent}")
        return queue
    
    def get_queue(self, name: str) -> Optional[RunQueue]:
        """Get queue by name."""
        return self._queues.get(name)
    
    def list_queues(self) -> List[str]:
        """List all queue names."""
        return list(self._queues.keys())
    
    def set_tag_limit(self, tag: str, limit: int) -> None:
        """Set concurrency limit for a tag."""
        self._tag_limits[tag] = limit
        logger.info(f"Set concurrency limit for tag '{tag}': {limit}")
    
    def get_tag_limit(self, tag: str) -> int:
        """Get concurrency limit for a tag."""
        return self._tag_limits.get(tag, 999)  # No limit by default
    
    def enqueue(self, queue_name: str, run_data: Dict[str, Any]) -> str:
        """Enqueue a run."""
        queue = self.get_queue(queue_name)
        if not queue:
            raise ValueError(f"Queue '{queue_name}' not found")
        
        # Generate run ID
        run_id = f"run_{int(time.time() * 1000)}_{run_data.get('template', 'unknown')}"
        
        # Create queued run
        run = QueuedRun(
            id=run_id,
            template=run_data["template"],
            priority=run_data.get("priority", 5),
            queue=queue_name,
            concurrency_tag=run_data.get("concurrency_tag"),
            variables=run_data.get("variables"),
            retry_config=run_data.get("retry_config"),
            user_id=run_data.get("user_id")
        )
        
        queue.enqueue(run)
        self._update_peak_depth()
        
        return run_id
    
    def dequeue_next(self) -> Optional[QueuedRun]:
        """Get next available run considering all constraints."""
        with self._lock:
            for queue_name, queue in self._queues.items():
                run = queue.dequeue()
                if not run:
                    continue
                
                # Check concurrency tag limit
                if run.concurrency_tag:
                    tag_limit = self.get_tag_limit(run.concurrency_tag)
                    current_count = self._tag_running[run.concurrency_tag]
                    
                    if current_count >= tag_limit:
                        # Put back in queue - tag limit reached
                        queue._running.pop(run.id, None)  # Remove from running
                        queue.enqueue(run)  # Put back in queue
                        continue
                    
                    # Increment tag counter
                    self._tag_running[run.concurrency_tag] += 1
                
                return run
            
            return None  # No runs available
    
    def complete_run(self, run_id: str, run: QueuedRun) -> None:
        """Mark run as completed."""
        queue = self.get_queue(run.queue)
        if queue:
            queue.complete(run_id)
        
        # Decrement tag counter
        if run.concurrency_tag:
            self._tag_running[run.concurrency_tag] -= 1
            if self._tag_running[run.concurrency_tag] <= 0:
                del self._tag_running[run.concurrency_tag]
        
        # Record completion for metrics
        self._metrics["completed_runs"].append({
            "run_id": run_id,
            "completed_at": datetime.now(),
            "queue": run.queue,
            "priority": run.priority
        })
        
        # Clean old completions (keep only 24h)
        cutoff = datetime.now() - timedelta(hours=24)
        self._metrics["completed_runs"] = [
            c for c in self._metrics["completed_runs"] 
            if c["completed_at"] > cutoff
        ]
    
    def get_running_by_tag(self, tag: str) -> List[QueuedRun]:
        """Get runs currently running with specific tag."""
        running = []
        for queue in self._queues.values():
            for run in queue.get_running():
                if run.concurrency_tag == tag:
                    running.append(run)
        return running
    
    def get_queued_by_tag(self, tag: str) -> List[QueuedRun]:
        """Get runs queued with specific tag."""
        queued = []
        for queue in self._queues.values():
            for run in queue.get_queued():
                if run.concurrency_tag == tag:
                    queued.append(run)
        return queued
    
    def pause_queue(self, queue_name: str) -> bool:
        """Pause a queue (requires appropriate permissions)."""
        # TODO: Add RBAC check here
        queue = self.get_queue(queue_name)
        if queue:
            queue.config.enabled = False
            logger.info(f"Paused queue '{queue_name}'")
            return True
        return False
    
    def load_config(self, config_file: str) -> None:
        """Load configuration from YAML file."""
        try:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Create configured queues
            if "queues" in config:
                for name, queue_config in config["queues"].items():
                    self.create_queue(
                        name=name,
                        max_concurrent=queue_config.get("max_concurrent", 2),
                        max_queued=queue_config.get("max_queued", 50)
                    )
            
            # Set concurrency tag limits
            if "concurrency_tags" in config:
                for tag, limit in config["concurrency_tags"].items():
                    self.set_tag_limit(tag, limit)
            
            logger.info(f"Loaded queue configuration from {config_file}")
            
        except Exception as e:
            logger.error(f"Failed to load queue config: {e}")
            raise
    
    def _update_peak_depth(self) -> None:
        """Update peak queue depth metric."""
        total_depth = sum(queue.size() for queue in self._queues.values())
        self._metrics["queue_depth_peak_24h"] = max(
            self._metrics["queue_depth_peak_24h"],
            total_depth
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get queue metrics."""
        # Calculate runs per hour
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        recent_completions = [
            c for c in self._metrics["completed_runs"]
            if c["completed_at"] > hour_ago
        ]
        
        self._metrics["runs_per_hour_24h"] = len(recent_completions)
        
        return self._metrics.copy()


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """Get the global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager


def init_queue_manager(config_file: Optional[str] = None) -> QueueManager:
    """Initialize the global queue manager."""
    global _queue_manager
    _queue_manager = QueueManager(config_file)
    return _queue_manager