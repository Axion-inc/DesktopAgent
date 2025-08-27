"""
GitHub Integration Module - Phase 7
Handles GitHub CLI/API operations for milestone, issue, PR management
"""

from .github_api import GitHubAPIClient
from .github_cli import GitHubCLIWrapper

__all__ = ['GitHubAPIClient', 'GitHubCLIWrapper']