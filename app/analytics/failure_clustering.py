"""
Enhanced failure clustering with recommended actions and trend analysis.

Provides intelligent grouping of failures and actionable recommendations.
"""

import re
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

@dataclass
class FailureCluster:
    """Represents a cluster of similar failures."""
    cluster_key: str
    display_name: str
    count: int
    sample_errors: List[str]
    recommended_actions: List[str]
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    trend_3d: List[int]  # Count for each of the last 3 days
    affected_templates: List[str]
    first_seen: datetime
    last_seen: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster": self.cluster_key,
            "display_name": self.display_name,
            "count": self.count,
            "sample_errors": self.sample_errors,
            "recommended_actions": self.recommended_actions,
            "severity": self.severity,
            "trend_3d": self.trend_3d,
            "affected_templates": self.affected_templates,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat()
        }

class FailureClusterAnalyzer:
    """Advanced failure clustering with actionable insights."""

    # Enhanced clustering rules with recommended actions
    CLUSTER_RULES = {
        "NO_FILES_FOUND": {
            "patterns": [
                r"no files found",
                r"0 files match",
                r"empty directory",
                r"file not found"
            ],
            "display_name": "Files Not Found",
            "severity": "MEDIUM",
            "actions": [
                "Check if the source directory path is correct",
                "Verify file patterns in find_files step",
                "Ensure files exist before running the plan",
                "Consider using broader search patterns"
            ]
        },

        "PERMISSION_BLOCKED": {
            "patterns": [
                r"permission denied",
                r"access denied",
                r"not authorized",
                r"forbidden",
                r"authentication failed"
            ],
            "display_name": "Permission Denied",
            "severity": "HIGH",
            "actions": [
                "Grant Screen Recording permission in System Preferences",
                "Enable Automation permissions for Terminal",
                "Check file/folder access permissions",
                "Verify RBAC user roles and permissions"
            ]
        },

        "WEB_ELEMENT_NOT_FOUND": {
            "patterns": [
                r"element not found",
                r"locator.*not found",
                r"selector.*not found",
                r"timeout.*element",
                r"click.*failed"
            ],
            "display_name": "Web Element Not Found",
            "severity": "HIGH",
            "actions": [
                "Check if website layout has changed",
                "Verify CSS selectors and text labels",
                "Increase timeout values in web steps",
                "Use more specific or alternative locators",
                "Enable browser debugging to inspect elements"
            ]
        },

        "PDF_PARSE_ERROR": {
            "patterns": [
                r"pdf.*corrupt",
                r"pdf.*parse.*error",
                r"pypdf.*error",
                r"pdf.*invalid"
            ],
            "display_name": "PDF Processing Error",
            "severity": "MEDIUM",
            "actions": [
                "Verify PDF files are not corrupted",
                "Check if PDFs are password-protected",
                "Update PyPDF2 library to latest version",
                "Try alternative PDF processing tools"
            ]
        },

        "NETWORK_ERROR": {
            "patterns": [
                r"connection.*refused",
                r"network.*timeout",
                r"dns.*resolution.*failed",
                r"connection.*reset",
                r"ssl.*error"
            ],
            "display_name": "Network Connection Error",
            "severity": "MEDIUM",
            "actions": [
                "Check internet connection",
                "Verify target website is accessible",
                "Check proxy settings if applicable",
                "Retry with exponential backoff",
                "Consider network firewall restrictions"
            ]
        },

        "MAIL_COMPOSITION_ERROR": {
            "patterns": [
                r"mail.*compose.*failed",
                r"applescript.*mail.*error",
                r"mail.*not.*authorized"
            ],
            "display_name": "Email Composition Failed",
            "severity": "HIGH",
            "actions": [
                "Launch Mail.app manually first",
                "Check Mail.app automation permissions",
                "Verify email account is configured",
                "Check AppleScript automation settings"
            ]
        },

        "HITL_TIMEOUT": {
            "patterns": [
                r"human.*confirm.*timeout",
                r"approval.*timeout",
                r"hitl.*timeout"
            ],
            "display_name": "Human Approval Timeout",
            "severity": "MEDIUM",
            "actions": [
                "Increase HITL timeout values",
                "Set up approval notifications",
                "Configure auto-approval for safe operations",
                "Review approval workflow efficiency"
            ]
        },

        "RESOURCE_EXHAUSTED": {
            "patterns": [
                r"out of memory",
                r"disk.*full",
                r"no space left",
                r"resource.*unavailable"
            ],
            "display_name": "System Resources Exhausted",
            "severity": "CRITICAL",
            "actions": [
                "Free up disk space",
                "Close other applications to free memory",
                "Check system resource usage",
                "Consider processing files in batches"
            ]
        }
    }

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or str(Path.home() / ".desktop-agent" / "failure_analysis.db")
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize failure analysis database."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS failure_clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cluster_key TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    run_id INTEGER,
                    template TEXT,
                    step_name TEXT,
                    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT 0
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_cluster_occurred
                ON failure_clusters(cluster_key, occurred_at)
            ''')

    def analyze_error(self, error_message: str, run_id: Optional[int] = None,
                     template: Optional[str] = None, step_name: Optional[str] = None) -> str:
        """Analyze an error and return its cluster key."""
        error_lower = error_message.lower()

        # Find matching cluster
        for cluster_key, rule in self.CLUSTER_RULES.items():
            for pattern in rule["patterns"]:
                if re.search(pattern, error_lower):
                    # Store in database
                    self._record_error(cluster_key, error_message, run_id, template, step_name)
                    return cluster_key

        # Generic cluster for unclassified errors
        generic_key = "UNKNOWN_ERROR"
        self._record_error(generic_key, error_message, run_id, template, step_name)
        return generic_key

    def _record_error(self, cluster_key: str, error_message: str, run_id: Optional[int],
                     template: Optional[str], step_name: Optional[str]):
        """Record error in database for analysis."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT INTO failure_clusters
                (cluster_key, error_message, run_id, template, step_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (cluster_key, error_message, run_id, template, step_name))

    def get_top_failure_clusters(self, limit: int = 10, days: int = 7) -> List[FailureCluster]:
        """Get top failure clusters with recommendations."""
        cutoff = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get cluster counts and samples
            cursor = conn.execute('''
                SELECT
                    cluster_key,
                    COUNT(*) as count,
                    GROUP_CONCAT(DISTINCT template) as templates,
                    MIN(occurred_at) as first_seen,
                    MAX(occurred_at) as last_seen,
                    error_message
                FROM failure_clusters
                WHERE occurred_at >= ?
                GROUP BY cluster_key
                ORDER BY count DESC
                LIMIT ?
            ''', (cutoff.isoformat(), limit))

            clusters = []
            for row in cursor:
                cluster_key = row['cluster_key']

                # Get sample errors
                sample_cursor = conn.execute('''
                    SELECT DISTINCT error_message FROM failure_clusters
                    WHERE cluster_key = ? AND occurred_at >= ?
                    LIMIT 3
                ''', (cluster_key, cutoff.isoformat()))
                sample_errors = [r[0] for r in sample_cursor.fetchall()]

                # Get 3-day trend
                trend_3d = self._get_trend_data(conn, cluster_key, 3)

                # Get cluster rule or create default
                rule = self.CLUSTER_RULES.get(cluster_key, {
                    "display_name": cluster_key.replace("_", " ").title(),
                    "severity": "MEDIUM",
                    "actions": ["Review error details and logs", "Check recent system changes"]
                })

                cluster = FailureCluster(
                    cluster_key=cluster_key,
                    display_name=rule["display_name"],
                    count=row['count'],
                    sample_errors=sample_errors,
                    recommended_actions=rule["actions"],
                    severity=rule["severity"],
                    trend_3d=trend_3d,
                    affected_templates=row['templates'].split(',') if row['templates'] else [],
                    first_seen=datetime.fromisoformat(row['first_seen']),
                    last_seen=datetime.fromisoformat(row['last_seen'])
                )
                clusters.append(cluster)

            return clusters

    def _get_trend_data(self, conn, cluster_key: str, days: int) -> List[int]:
        """Get daily counts for trend analysis."""
        trend = []

        for i in range(days):
            day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            cursor = conn.execute('''
                SELECT COUNT(*) FROM failure_clusters
                WHERE cluster_key = ? AND occurred_at >= ? AND occurred_at < ?
            ''', (cluster_key, day_start.isoformat(), day_end.isoformat()))

            count = cursor.fetchone()[0]
            trend.append(count)

        return trend[::-1]  # Reverse to get chronological order

    def mark_cluster_resolved(self, cluster_key: str, days_lookback: int = 7) -> int:
        """Mark a cluster as resolved (for tracking fix effectiveness)."""
        cutoff = datetime.now() - timedelta(days=days_lookback)

        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.execute('''
                UPDATE failure_clusters
                SET resolved = 1
                WHERE cluster_key = ? AND occurred_at >= ?
            ''', (cluster_key, cutoff.isoformat()))

            return cursor.rowcount

    def get_cluster_details(self, cluster_key: str, limit: int = 50) -> Dict[str, Any]:
        """Get detailed information about a specific cluster."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get recent occurrences
            cursor = conn.execute('''
                SELECT * FROM failure_clusters
                WHERE cluster_key = ?
                ORDER BY occurred_at DESC
                LIMIT ?
            ''', (cluster_key, limit))

            occurrences = [dict(row) for row in cursor.fetchall()]

            # Get statistics
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_count,
                    COUNT(DISTINCT template) as affected_templates,
                    COUNT(DISTINCT run_id) as affected_runs,
                    MIN(occurred_at) as first_seen,
                    MAX(occurred_at) as last_seen
                FROM failure_clusters
                WHERE cluster_key = ?
            ''', (cluster_key,))

            stats = dict(cursor.fetchone())

            rule = self.CLUSTER_RULES.get(cluster_key, {})

            return {
                "cluster_key": cluster_key,
                "display_name": rule.get("display_name", cluster_key),
                "severity": rule.get("severity", "MEDIUM"),
                "recommended_actions": rule.get("actions", []),
                "statistics": stats,
                "recent_occurrences": occurrences[:10],  # Last 10 for display
                "all_occurrences": occurrences
            }

    def cleanup_old_records(self, days: int = 90) -> int:
        """Clean up old failure records."""
        cutoff = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.execute('''
                DELETE FROM failure_clusters
                WHERE occurred_at < ?
            ''', (cutoff.isoformat(),))

            return cursor.rowcount

# Global analyzer instance
_failure_analyzer = None

def get_failure_analyzer() -> FailureClusterAnalyzer:
    """Get the global failure analyzer instance."""
    global _failure_analyzer
    if _failure_analyzer is None:
        _failure_analyzer = FailureClusterAnalyzer()
    return _failure_analyzer

def analyze_error(error_message: str, **kwargs) -> str:
    """Convenience function to analyze an error."""
    return get_failure_analyzer().analyze_error(error_message, **kwargs)
