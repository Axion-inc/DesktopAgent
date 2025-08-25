"""
Folder Watcher for Desktop Agent.

Provides file system watching capabilities to trigger plan execution based on file changes.
Integrates with the queue system for execution management.

Features:
- Watch multiple folders for file changes
- Pattern-based filtering (globs)
- Event-driven plan execution
- Debouncing to avoid duplicate triggers
- Integration with QueueManager
- Persistent watcher configuration
"""

import os
# import time
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import fnmatch


@dataclass
class WatchConfig:
    """Configuration for a folder watcher."""

    id: str
    name: str
    watch_path: str
    template: str  # Plan template to execute
    patterns: List[str] = None  # File patterns to match (e.g., ["*.pdf", "*.csv"])
    ignore_patterns: List[str] = None  # Patterns to ignore
    events: List[str] = None  # Events to watch: created, modified, deleted, moved
    debounce_ms: int = 5000  # Debounce delay in milliseconds
    queue: str = "default"
    priority: int = 5
    enabled: bool = True
    variables: Dict[str, Any] = None  # Variables to pass to template
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.patterns is None:
            self.patterns = ["*"]  # Match all files by default
        if self.ignore_patterns is None:
            self.ignore_patterns = []
        if self.events is None:
            self.events = ["created", "modified"]  # Default events
        if self.variables is None:
            self.variables = {}

    def matches_file(self, file_path: str) -> bool:
        """Check if a file path matches this watcher's patterns."""
        file_name = os.path.basename(file_path)

        # Check ignore patterns first
        for ignore_pattern in self.ignore_patterns:
            if fnmatch.fnmatch(file_name, ignore_pattern) or fnmatch.fnmatch(file_path, ignore_pattern):
                return False

        # Check inclusion patterns
        for pattern in self.patterns:
            if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(file_path, pattern):
                return True

        return False

    def validate(self) -> List[str]:
        """Validate watcher configuration."""
        errors = []

        if not self.id or not self.id.strip():
            errors.append("Watcher ID is required")

        if not self.name or not self.name.strip():
            errors.append("Watcher name is required")

        if not self.watch_path or not self.watch_path.strip():
            errors.append("Watch path is required")
        else:
            # Check if path exists
            path = Path(self.watch_path).expanduser()
            if not path.exists():
                errors.append(f"Watch path does not exist: {self.watch_path}")
            elif not path.is_dir():
                errors.append(f"Watch path is not a directory: {self.watch_path}")

        if not self.template or not self.template.strip():
            errors.append("Template path is required")

        if not isinstance(self.priority, int) or self.priority < 1 or self.priority > 9:
            errors.append("Priority must be an integer from 1 to 9")

        if not self.queue or not self.queue.strip():
            errors.append("Queue name is required")

        if not isinstance(self.debounce_ms, int) or self.debounce_ms < 0:
            errors.append("Debounce delay must be a non-negative integer")

        # Validate event types
        valid_events = {"created", "modified", "deleted", "moved"}
        for event in self.events:
            if event not in valid_events:
                errors.append(f"Invalid event type: {event} (valid: {', '.join(valid_events)})")

        return errors


class WatcherEventHandler(FileSystemEventHandler):
    """Event handler for file system changes."""

    def __init__(self, watcher_service: 'WatcherService'):
        self.watcher_service = watcher_service
        self.last_events: Dict[str, datetime] = {}  # For debouncing
        super().__init__()

    def on_created(self, event):
        if not event.is_directory:
            self._handle_event('created', event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._handle_event('modified', event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._handle_event('deleted', event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._handle_event('moved', event.dest_path)

    def _handle_event(self, event_type: str, file_path: str):
        """Handle a file system event."""
        now = datetime.now()

        # Find matching watchers
        matching_watchers = []
        for watcher_config in self.watcher_service.list_watchers(enabled_only=True):
            if (
                event_type in watcher_config.events
                and self._path_is_in_watch_dir(file_path, watcher_config.watch_path)
                and watcher_config.matches_file(file_path)
            ):
                matching_watchers.append(watcher_config)

        # Process each matching watcher
        for config in matching_watchers:
            self._process_event(config, event_type, file_path, now)

    def _path_is_in_watch_dir(self, file_path: str, watch_path: str) -> bool:
        """Check if a file path is within a watched directory."""
        try:
            file_path = os.path.abspath(file_path)
            watch_path = os.path.abspath(os.path.expanduser(watch_path))
            return file_path.startswith(watch_path)
        except Exception:
            return False

    def _process_event(self, config: WatchConfig, event_type: str, file_path: str, event_time: datetime):
        """Process an event for a specific watcher config."""
        # Create debounce key
        debounce_key = f"{config.id}:{file_path}:{event_type}"

        # Check if we should debounce this event
        if debounce_key in self.last_events:
            time_since_last = (event_time - self.last_events[debounce_key]).total_seconds() * 1000
            if time_since_last < config.debounce_ms:
                return  # Skip this event due to debouncing

        # Record this event
        self.last_events[debounce_key] = event_time

        # Execute the trigger
        try:
            self.watcher_service._execute_trigger(config, event_type, file_path)
        except Exception as e:
            print(f"Failed to execute watcher trigger: {e}")


class WatcherService:
    """Main watcher service that manages file system watching."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or str(Path.home() / ".desktop-agent" / "watcher.db")
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[WatcherEventHandler] = None
        self.running = False
        self.watched_paths: Set[str] = set()

        # Initialize database
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Metrics
        self.metrics = {
            "events_processed": 0,
            "triggers_executed": 0,
            "successful_triggers": 0,
            "failed_triggers": 0,
            "last_event": None
        }

    def _init_db(self):
        """Initialize the watcher database."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS watchers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    watch_path TEXT NOT NULL,
                    template TEXT NOT NULL,
                    patterns TEXT DEFAULT '["*"]',
                    ignore_patterns TEXT DEFAULT '[]',
                    events TEXT DEFAULT '["created", "modified"]',
                    debounce_ms INTEGER DEFAULT 5000,
                    queue TEXT DEFAULT 'default',
                    priority INTEGER DEFAULT 5,
                    enabled BOOLEAN DEFAULT 1,
                    variables TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS watcher_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    watcher_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    run_id INTEGER,
                    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN,
                    error_message TEXT,
                    FOREIGN KEY (watcher_id) REFERENCES watchers (id)
                )
            ''')

    def add_watcher(self, config: WatchConfig) -> None:
        """Add a new file watcher."""
        # Validate configuration
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid watcher config: {'; '.join(errors)}")

        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO watchers
                (id, name, watch_path, template, patterns, ignore_patterns, events,
                 debounce_ms, queue, priority, enabled, variables, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                config.id, config.name, config.watch_path, config.template,
                json.dumps(config.patterns), json.dumps(config.ignore_patterns),
                json.dumps(config.events), config.debounce_ms,
                config.queue, config.priority, config.enabled,
                json.dumps(config.variables)
            ))

        # If service is running, update watched paths
        if self.running:
            self._update_watched_paths()

    def remove_watcher(self, watcher_id: str) -> bool:
        """Remove a watcher by ID."""
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.execute('DELETE FROM watchers WHERE id = ?', (watcher_id,))
            removed = cursor.rowcount > 0

        # Update watched paths if service is running
        if self.running:
            self._update_watched_paths()

        return removed

    def get_watcher(self, watcher_id: str) -> Optional[WatchConfig]:
        """Get a watcher by ID."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM watchers WHERE id = ?', (watcher_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_config(row)

    def list_watchers(self, enabled_only: bool = False) -> List[WatchConfig]:
        """List all watchers."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row

            query = 'SELECT * FROM watchers'
            if enabled_only:
                query += ' WHERE enabled = 1'
            query += ' ORDER BY name'

            cursor = conn.execute(query)
            return [self._row_to_config(row) for row in cursor.fetchall()]

    def _row_to_config(self, row) -> WatchConfig:
        """Convert database row to WatchConfig object."""
        return WatchConfig(
            id=row['id'],
            name=row['name'],
            watch_path=row['watch_path'],
            template=row['template'],
            patterns=json.loads(row['patterns']) if row['patterns'] else ["*"],
            ignore_patterns=json.loads(row['ignore_patterns']) if row['ignore_patterns'] else [],
            events=json.loads(row['events']) if row['events'] else ["created", "modified"],
            debounce_ms=row['debounce_ms'],
            queue=row['queue'],
            priority=row['priority'],
            enabled=bool(row['enabled']),
            variables=json.loads(row['variables']) if row['variables'] else {},
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

    def start(self) -> None:
        """Start the watcher service."""
        if self.running:
            return

        self.observer = Observer()
        self.event_handler = WatcherEventHandler(self)

        self._update_watched_paths()

        self.observer.start()
        self.running = True
        print("Watcher service started")

    def stop(self) -> None:
        """Stop the watcher service."""
        if not self.running:
            return

        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        self.event_handler = None
        self.running = False
        self.watched_paths.clear()
        print("Watcher service stopped")

    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self.running and self.observer and self.observer.is_alive()

    def _update_watched_paths(self):
        """Update the set of watched paths based on current configuration."""
        if not self.observer or not self.event_handler:
            return

        # Get all unique watch paths from enabled watchers
        current_paths = set()
        for config in self.list_watchers(enabled_only=True):
            try:
                expanded_path = os.path.abspath(os.path.expanduser(config.watch_path))
                if os.path.exists(expanded_path):
                    current_paths.add(expanded_path)
            except Exception as e:
                print(f"Failed to expand watch path: {e}")

        # Remove old watches
        for path in self.watched_paths - current_paths:
            try:
                self.observer.unschedule_all()  # Simple approach: unschedule all and re-add
            except Exception:
                pass

        # Add new watches
        if current_paths:
            try:
                self.observer.unschedule_all()  # Clear all first
                for path in current_paths:
                    self.observer.schedule(self.event_handler, path, recursive=True)
                print(f"Watching {len(current_paths)} directories")
            except Exception as e:
                print(f"Error setting up watches: {e}")

        self.watched_paths = current_paths

    def _execute_trigger(self, config: WatchConfig, event_type: str, file_path: str):
        """Execute a trigger by queuing the associated plan."""
        self.metrics["triggers_executed"] += 1

        try:
            from app.orchestrator.queue import get_queue_manager
            queue_manager = get_queue_manager()

            # Create variables for the plan including file information
            variables = dict(config.variables)
            variables.update({
                "trigger_file": file_path,
                "trigger_event": event_type,
                "trigger_time": datetime.now().isoformat(),
                "trigger_filename": os.path.basename(file_path),
                "trigger_dirname": os.path.dirname(file_path)
            })

            # Create run request for the queue
            run_request = {
                "template": config.template,
                "variables": variables,
                "queue": config.queue,
                "priority": config.priority,
                "source": f"watcher:{config.id}",
                "concurrency_tag": f"watcher_{config.id}"
            }

            # Add to queue
            run_id = queue_manager.enqueue_run(run_request)

            # Log the trigger
            self._log_trigger(config.id, event_type, file_path, run_id, True)

            self.metrics["successful_triggers"] += 1
            self.metrics["last_event"] = datetime.now()

            print(f"File trigger: {event_type} {file_path} -> queued run {run_id} for watcher {config.id}")

        except Exception as e:
            self._log_trigger(config.id, event_type, file_path, None, False, str(e))
            self.metrics["failed_triggers"] += 1
            raise

    def _log_trigger(self, watcher_id: str, event_type: str, file_path: str,
                     run_id: Optional[int], success: bool, error_message: Optional[str] = None):
        """Log a trigger event."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT INTO watcher_events
                (watcher_id, event_type, file_path, run_id, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (watcher_id, event_type, file_path, run_id, success, error_message))

    def get_metrics(self) -> Dict[str, Any]:
        """Get watcher metrics."""
        return {
            **self.metrics,
            "is_running": self.is_running(),
            "watchers_count": len(self.list_watchers()),
            "enabled_watchers": len(self.list_watchers(enabled_only=True)),
            "watched_paths_count": len(self.watched_paths),
            "watched_paths": list(self.watched_paths)
        }

    def get_event_history(self, watcher_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get event history."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row

            query = '''
                SELECT e.*, w.name as watcher_name
                FROM watcher_events e
                JOIN watchers w ON e.watcher_id = w.id
            '''
            params = []

            if watcher_id:
                query += ' WHERE e.watcher_id = ?'
                params.append(watcher_id)

            query += ' ORDER BY e.triggered_at DESC LIMIT ?'
            params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


# Global watcher service
_watcher_service = None


def get_watcher() -> WatcherService:
    """Get the global watcher service instance."""
    global _watcher_service
    if _watcher_service is None:
        _watcher_service = WatcherService()
    return _watcher_service


def start_watcher():
    """Start the watcher service."""
    get_watcher().start()


def stop_watcher():
    """Stop the watcher service."""
    get_watcher().stop()


def is_watcher_running() -> bool:
    """Check if the watcher is running."""
    return get_watcher().is_running()
