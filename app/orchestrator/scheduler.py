"""
Cron Scheduler for Desktop Agent.

Provides scheduling capabilities to run plans automatically based on cron expressions.
Integrates with the queue system for execution management.

Features:
- Cron expression parsing and validation
- Schedule management (create, update, delete)
- Next run calculation
- Integration with QueueManager
- Persistent schedule storage
- Service control (start/stop/status)
"""

import os
import re
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass, asdict
import croniter
from croniter import croniter as CronIter


@dataclass
class Schedule:
    """Represents a scheduled task."""
    
    id: str
    name: str
    cron: str  # Cron expression
    template: str  # Path to plan template
    queue: str = "default"
    priority: int = 5
    enabled: bool = True
    variables: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = {}
        
        # Calculate next run time on creation
        self._update_next_run()
    
    def _update_next_run(self):
        """Update the next_run timestamp based on cron expression."""
        try:
            cron = CronIter(self.cron, datetime.now())
            self.next_run = cron.get_next(datetime)
        except Exception:
            self.next_run = None
    
    def should_run(self, now: Optional[datetime] = None) -> bool:
        """Check if the schedule should run now."""
        if not self.enabled:
            return False
        
        if now is None:
            now = datetime.now()
        
        if self.next_run is None:
            return False
            
        return now >= self.next_run
    
    def mark_executed(self, execution_time: Optional[datetime] = None):
        """Mark the schedule as executed and calculate next run."""
        if execution_time is None:
            execution_time = datetime.now()
            
        self.last_run = execution_time
        self._update_next_run()
    
    def validate(self) -> List[str]:
        """Validate schedule configuration."""
        errors = []
        
        if not self.id or not self.id.strip():
            errors.append("Schedule ID is required")
        
        if not self.name or not self.name.strip():
            errors.append("Schedule name is required")
        
        if not self.cron or not self.cron.strip():
            errors.append("Cron expression is required")
        else:
            # Validate cron expression
            try:
                CronIter(self.cron)
            except Exception as e:
                errors.append(f"Invalid cron expression: {e}")
        
        if not self.template or not self.template.strip():
            errors.append("Template path is required")
        
        if not isinstance(self.priority, int) or self.priority < 1 or self.priority > 9:
            errors.append("Priority must be an integer from 1 to 9")
        
        if not self.queue or not self.queue.strip():
            errors.append("Queue name is required")
        
        return errors


class CronParser:
    """Parser for cron expressions with validation."""
    
    # Special cron aliases
    ALIASES = {
        "@yearly": "0 0 1 1 *",
        "@annually": "0 0 1 1 *",
        "@monthly": "0 0 1 * *",
        "@weekly": "0 0 * * 0",
        "@daily": "0 0 * * *",
        "@midnight": "0 0 * * *",
        "@hourly": "0 * * * *"
    }
    
    def __init__(self):
        pass
    
    def parse(self, expression: str) -> 'ParsedCron':
        """Parse a cron expression and return a ParsedCron object."""
        # Handle special aliases
        if expression in self.ALIASES:
            expression = self.ALIASES[expression]
        
        return ParsedCron(expression)


class ParsedCron:
    """Represents a parsed cron expression."""
    
    def __init__(self, expression: str):
        self.expression = expression
        self._validate()
    
    def _validate(self):
        """Validate the cron expression."""
        try:
            CronIter(self.expression)
            self._valid = True
        except Exception as e:
            self._valid = False
            self._error = str(e)
    
    def is_valid(self) -> bool:
        """Check if the cron expression is valid."""
        return self._valid
    
    def next_run_time(self, from_time: datetime) -> datetime:
        """Calculate the next run time from the given time."""
        if not self.is_valid():
            raise ValueError(f"Invalid cron expression: {self.expression}")
        
        cron = CronIter(self.expression, from_time)
        return cron.get_next(datetime)
    
    def get_error(self) -> Optional[str]:
        """Get validation error message if any."""
        return getattr(self, '_error', None)


class SchedulerService:
    """Main scheduler service that manages scheduled executions."""
    
    def __init__(self, storage_path: Optional[str] = None, check_interval: int = 60, config_file: Optional[str] = None):
        self.storage_path = storage_path or str(Path.home() / ".desktop-agent" / "scheduler.db")
        self.check_interval = check_interval  # seconds
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Initialize database
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # Load configuration if provided
        if config_file:
            self.load_config_file(config_file)
        
        # Metrics
        self.metrics = {
            "scheduled_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_check": None,
            "next_check": None
        }
    
    def _init_db(self):
        """Initialize the scheduler database."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    cron TEXT NOT NULL,
                    template TEXT NOT NULL,
                    queue TEXT DEFAULT 'default',
                    priority INTEGER DEFAULT 5,
                    enabled BOOLEAN DEFAULT 1,
                    variables TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_run TIMESTAMP,
                    next_run TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS schedule_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id TEXT NOT NULL,
                    run_id INTEGER,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    success BOOLEAN,
                    error_message TEXT,
                    FOREIGN KEY (schedule_id) REFERENCES schedules (id)
                )
            ''')
    
    def add_schedule(self, schedule: Schedule) -> None:
        """Add a new schedule."""
        # Validate schedule
        errors = schedule.validate()
        if errors:
            raise ValueError(f"Invalid schedule: {'; '.join(errors)}")
        
        schedule._update_next_run()
        
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO schedules 
                (id, name, cron, template, queue, priority, enabled, variables, 
                 updated_at, last_run, next_run)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            ''', (
                schedule.id, schedule.name, schedule.cron, schedule.template,
                schedule.queue, schedule.priority, schedule.enabled,
                json.dumps(schedule.variables),
                schedule.last_run, schedule.next_run
            ))
    
    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule by ID."""
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.execute('DELETE FROM schedules WHERE id = ?', (schedule_id,))
            return cursor.rowcount > 0
    
    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM schedules WHERE id = ?', (schedule_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_schedule(row)
    
    def list_schedules(self, enabled_only: bool = False) -> List[Schedule]:
        """List all schedules."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = 'SELECT * FROM schedules'
            if enabled_only:
                query += ' WHERE enabled = 1'
            query += ' ORDER BY next_run ASC'
            
            cursor = conn.execute(query)
            return [self._row_to_schedule(row) for row in cursor.fetchall()]
    
    def _row_to_schedule(self, row) -> Schedule:
        """Convert database row to Schedule object."""
        return Schedule(
            id=row['id'],
            name=row['name'],
            cron=row['cron'],
            template=row['template'],
            queue=row['queue'],
            priority=row['priority'],
            enabled=bool(row['enabled']),
            variables=json.loads(row['variables']) if row['variables'] else {},
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            last_run=datetime.fromisoformat(row['last_run']) if row['last_run'] else None,
            next_run=datetime.fromisoformat(row['next_run']) if row['next_run'] else None
        )
    
    def start(self) -> None:
        """Start the scheduler service."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("Scheduler service started")
    
    def stop(self) -> None:
        """Stop the scheduler service."""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)  # Wait up to 5 seconds
        print("Scheduler service stopped")
    
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self.running and self.thread and self.thread.is_alive()
    
    def _run_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                self._check_and_execute()
                self.metrics["last_check"] = datetime.now()
                self.metrics["next_check"] = datetime.now() + timedelta(seconds=self.check_interval)
                
            except Exception as e:
                print(f"Scheduler error: {e}")
            
            # Sleep in small increments so we can respond to stop() quickly
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _check_and_execute(self):
        """Check for schedules that need to run and execute them."""
        now = datetime.now()
        schedules = self.list_schedules(enabled_only=True)
        
        for schedule in schedules:
            if schedule.should_run(now):
                try:
                    self._execute_schedule(schedule)
                    schedule.mark_executed(now)
                    
                    # Update schedule in database
                    with sqlite3.connect(self.storage_path) as conn:
                        conn.execute('''
                            UPDATE schedules 
                            SET last_run = ?, next_run = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (schedule.last_run, schedule.next_run, schedule.id))
                    
                    self.metrics["successful_runs"] += 1
                    
                except Exception as e:
                    print(f"Failed to execute schedule {schedule.id}: {e}")
                    self._log_execution_error(schedule.id, str(e))
                    self.metrics["failed_runs"] += 1
                
                self.metrics["scheduled_runs"] += 1
    
    def _execute_schedule(self, schedule: Schedule):
        """Execute a scheduled task by adding it to the queue."""
        try:
            from app.orchestrator.queue import get_queue_manager
            queue_manager = get_queue_manager()
            
            # Create run request for the queue
            run_request = {
                "template": schedule.template,
                "variables": schedule.variables,
                "queue": schedule.queue,
                "priority": schedule.priority,
                "source": f"scheduler:{schedule.id}",
                "concurrency_tag": f"schedule_{schedule.id}"
            }
            
            # Add to queue
            run_id = queue_manager.enqueue_run(run_request)
            
            # Log execution
            self._log_execution_start(schedule.id, run_id)
            
            print(f"Scheduled run {run_id} added to queue {schedule.queue} for schedule {schedule.id}")
            
        except Exception as e:
            print(f"Failed to queue scheduled run for {schedule.id}: {e}")
            raise
    
    def _log_execution_start(self, schedule_id: str, run_id: int):
        """Log the start of a scheduled execution."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT INTO schedule_executions (schedule_id, run_id)
                VALUES (?, ?)
            ''', (schedule_id, run_id))
    
    def _log_execution_error(self, schedule_id: str, error_message: str):
        """Log an execution error."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT INTO schedule_executions 
                (schedule_id, completed_at, success, error_message)
                VALUES (?, CURRENT_TIMESTAMP, 0, ?)
            ''', (schedule_id, error_message))

    def load_config_file(self, config_file: str) -> None:
        """Load schedules from YAML configuration file."""
        try:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            if 'schedules' in config:
                for schedule_data in config['schedules']:
                    schedule = Schedule(
                        id=schedule_data['id'],
                        name=schedule_data['name'],
                        cron=schedule_data['cron'],
                        template=schedule_data['template'],
                        queue=schedule_data.get('queue', 'default'),
                        priority=schedule_data.get('priority', 5),
                        enabled=schedule_data.get('enabled', True),
                        variables=schedule_data.get('variables', {}),
                    )
                    
                    # Validate and add schedule
                    errors = schedule.validate()
                    if errors:
                        print(f"Invalid schedule {schedule.id}: {'; '.join(errors)}")
                        continue
                        
                    self.add_schedule(schedule)
                    
            print(f"Loaded {len(config.get('schedules', []))} schedules from {config_file}")
            
        except Exception as e:
            print(f"Failed to load schedule config from {config_file}: {e}")
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get scheduler metrics."""
        return {
            **self.metrics,
            "is_running": self.is_running(),
            "schedules_count": len(self.list_schedules()),
            "enabled_schedules": len(self.list_schedules(enabled_only=True))
        }
    
    def get_execution_history(self, schedule_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = '''
                SELECT e.*, s.name as schedule_name 
                FROM schedule_executions e 
                JOIN schedules s ON e.schedule_id = s.id
            '''
            params = []
            
            if schedule_id:
                query += ' WHERE e.schedule_id = ?'
                params.append(schedule_id)
            
            query += ' ORDER BY e.started_at DESC LIMIT ?'
            params.append(limit)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


# Global scheduler service
_scheduler_service = None

def get_scheduler() -> SchedulerService:
    """Get the global scheduler service instance."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service


def start_scheduler():
    """Start the scheduler service."""
    get_scheduler().start()

def start_scheduler_with_config(config_file: str):
    """Start the scheduler service with configuration file.""" 
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService(config_file=config_file)
    _scheduler_service.start()


def stop_scheduler():
    """Stop the scheduler service."""
    get_scheduler().stop()


def is_scheduler_running() -> bool:
    """Check if the scheduler is running."""
    return get_scheduler().is_running()


# Convenience classes for backward compatibility
CronScheduler = SchedulerService