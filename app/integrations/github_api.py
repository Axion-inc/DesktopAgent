"""
GitHub API Client - Phase 7
Direct GitHub API integration for advanced operations
"""

import json
import logging
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


@dataclass
class GitHubAPIConfig:
    """GitHub API configuration"""
    token: str = ""
    base_url: str = "https://api.github.com"
    owner: str = ""
    repo: str = ""
    timeout: int = 30
    
    def __post_init__(self):
        # Try to get token from environment if not provided
        if not self.token:
            self.token = os.getenv("GITHUB_TOKEN", "")


class GitHubAPIError(Exception):
    """GitHub API operation error"""
    pass


class GitHubAPIClient:
    """
    Direct GitHub API client for advanced operations
    Complements gh CLI for programmatic access
    """
    
    def __init__(self, config: GitHubAPIConfig):
        """Initialize GitHub API client"""
        self.config = config
        self.session = requests.Session()
        
        if not self.config.token:
            raise GitHubAPIError("GitHub API token required")
        
        self.session.headers.update({
            "Authorization": f"token {self.config.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DesktopAgent-Phase7/1.0"
        })
        
        logger.info("GitHub API client initialized")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Dict[str, Any] = None,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Make authenticated GitHub API request"""
        
        url = f"{self.config.base_url}/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.config.timeout
            )
            
            response.raise_for_status()
            
            if response.status_code == 204:  # No content
                return {"success": True}
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("message", str(e))
            except:
                error_detail = str(e)
            
            raise GitHubAPIError(f"GitHub API error: {error_detail}")
        
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"GitHub API request failed: {str(e)}")
    
    def get_repository_info(self) -> Dict[str, Any]:
        """Get repository information"""
        endpoint = f"repos/{self.config.owner}/{self.config.repo}"
        return self._make_request("GET", endpoint)
    
    def create_issue(
        self,
        title: str,
        body: str = "",
        labels: List[str] = None,
        assignees: List[str] = None,
        milestone: int = None
    ) -> Dict[str, Any]:
        """Create GitHub issue via API"""
        
        data = {
            "title": title,
            "body": body
        }
        
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        if milestone:
            data["milestone"] = milestone
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/issues"
        result = self._make_request("POST", endpoint, data)
        
        logger.info(f"Created GitHub issue via API: #{result.get('number', 'unknown')}")
        return result
    
    def create_pull_request(
        self,
        title: str,
        head: str,
        base: str,
        body: str = "",
        draft: bool = False
    ) -> Dict[str, Any]:
        """Create GitHub pull request via API"""
        
        data = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft
        }
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/pulls"
        result = self._make_request("POST", endpoint, data)
        
        logger.info(f"Created GitHub PR via API: #{result.get('number', 'unknown')}")
        return result
    
    def create_milestone(
        self,
        title: str,
        description: str = "",
        due_on: str = None,
        state: str = "open"
    ) -> Dict[str, Any]:
        """Create GitHub milestone via API"""
        
        data = {
            "title": title,
            "description": description,
            "state": state
        }
        
        if due_on:
            data["due_on"] = due_on
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/milestones"
        result = self._make_request("POST", endpoint, data)
        
        logger.info(f"Created GitHub milestone via API: {title}")
        return result
    
    def create_label(
        self,
        name: str,
        color: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """Create GitHub label via API"""
        
        data = {
            "name": name,
            "color": color.lstrip("#"),
            "description": description
        }
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/labels"
        result = self._make_request("POST", endpoint, data)
        
        logger.info(f"Created GitHub label via API: {name}")
        return result
    
    def list_issues(
        self,
        state: str = "open",
        labels: str = "",
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """List GitHub issues via API"""
        
        params = {
            "state": state,
            "per_page": per_page
        }
        
        if labels:
            params["labels"] = labels
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/issues"
        result = self._make_request("GET", endpoint, params=params)
        
        # Filter out pull requests (GitHub API includes PRs in issues)
        issues = [item for item in result if "pull_request" not in item]
        
        logger.info(f"Retrieved {len(issues)} GitHub issues via API")
        return issues
    
    def list_pull_requests(
        self,
        state: str = "open",
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """List GitHub pull requests via API"""
        
        params = {
            "state": state,
            "per_page": per_page
        }
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/pulls"
        result = self._make_request("GET", endpoint, params=params)
        
        logger.info(f"Retrieved {len(result)} GitHub PRs via API")
        return result
    
    def create_workflow_dispatch(
        self,
        workflow_id: str,
        ref: str = "main",
        inputs: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Trigger GitHub Actions workflow via API"""
        
        data = {
            "ref": ref
        }
        
        if inputs:
            data["inputs"] = inputs
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/actions/workflows/{workflow_id}/dispatches"
        result = self._make_request("POST", endpoint, data)
        
        logger.info(f"Triggered GitHub workflow via API: {workflow_id}")
        return result
    
    def get_workflow_runs(
        self,
        workflow_id: str = None,
        per_page: int = 10
    ) -> List[Dict[str, Any]]:
        """Get GitHub Actions workflow runs"""
        
        params = {"per_page": per_page}
        
        if workflow_id:
            endpoint = f"repos/{self.config.owner}/{self.config.repo}/actions/workflows/{workflow_id}/runs"
        else:
            endpoint = f"repos/{self.config.owner}/{self.config.repo}/actions/runs"
        
        result = self._make_request("GET", endpoint, params=params)
        
        workflow_runs = result.get("workflow_runs", [])
        logger.info(f"Retrieved {len(workflow_runs)} workflow runs via API")
        return workflow_runs
    
    def add_issue_comment(
        self,
        issue_number: int,
        body: str
    ) -> Dict[str, Any]:
        """Add comment to GitHub issue"""
        
        data = {"body": body}
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/issues/{issue_number}/comments"
        result = self._make_request("POST", endpoint, data)
        
        logger.info(f"Added comment to GitHub issue #{issue_number}")
        return result
    
    def update_issue_labels(
        self,
        issue_number: int,
        labels: List[str]
    ) -> Dict[str, Any]:
        """Update GitHub issue labels"""
        
        data = {"labels": labels}
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/issues/{issue_number}/labels"
        result = self._make_request("PUT", endpoint, data)
        
        logger.info(f"Updated labels for GitHub issue #{issue_number}")
        return result
    
    def close_issue(
        self,
        issue_number: int,
        comment: str = None
    ) -> Dict[str, Any]:
        """Close GitHub issue"""
        
        # Add comment if provided
        if comment:
            self.add_issue_comment(issue_number, comment)
        
        # Close the issue
        data = {"state": "closed"}
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/issues/{issue_number}"
        result = self._make_request("PATCH", endpoint, data)
        
        logger.info(f"Closed GitHub issue #{issue_number}")
        return result
    
    def create_branch(
        self,
        branch_name: str,
        base_ref: str = "main"
    ) -> Dict[str, Any]:
        """Create new branch via API"""
        
        # First, get the SHA of the base reference
        base_endpoint = f"repos/{self.config.owner}/{self.config.repo}/git/ref/heads/{base_ref}"
        base_result = self._make_request("GET", base_endpoint)
        base_sha = base_result["object"]["sha"]
        
        # Create the new branch
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        
        endpoint = f"repos/{self.config.owner}/{self.config.repo}/git/refs"
        result = self._make_request("POST", endpoint, data)
        
        logger.info(f"Created GitHub branch via API: {branch_name}")
        return result


class GitHubMetricsCollector:
    """
    Collects GitHub-related metrics for Phase 7 monitoring
    """
    
    def __init__(self, api_client: GitHubAPIClient):
        """Initialize metrics collector"""
        self.api = api_client
        logger.info("GitHub metrics collector initialized")
    
    def collect_phase7_metrics(self) -> Dict[str, Any]:
        """Collect Phase 7 specific GitHub metrics"""
        
        metrics = {
            "github_issues_total": 0,
            "github_prs_total": 0,
            "github_l4_issues": 0,
            "github_policy_violations": 0,
            "github_patch_proposals": 0,
            "github_workflow_runs_24h": 0,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Count total issues
            all_issues = self.api.list_issues(state="all", per_page=100)
            metrics["github_issues_total"] = len(all_issues)
            
            # Count L4 autopilot related issues
            l4_issues = self.api.list_issues(labels="l4-autopilot", per_page=100)
            metrics["github_l4_issues"] = len(l4_issues)
            
            # Count policy violations
            policy_issues = self.api.list_issues(labels="policy-violation", per_page=100)
            metrics["github_policy_violations"] = len(policy_issues)
            
            # Count patch proposal PRs
            all_prs = self.api.list_pull_requests(state="all", per_page=100)
            metrics["github_prs_total"] = len(all_prs)
            
            patch_prs = [pr for pr in all_prs if "planner-l2" in [label.get("name", "") for label in pr.get("labels", [])]]
            metrics["github_patch_proposals"] = len(patch_prs)
            
            # Count recent workflow runs (approximate)
            workflow_runs = self.api.get_workflow_runs(per_page=50)
            recent_runs = [
                run for run in workflow_runs
                if datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")) > 
                   datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            ]
            metrics["github_workflow_runs_24h"] = len(recent_runs)
            
        except Exception as e:
            logger.error(f"Failed to collect GitHub metrics: {e}")
            metrics["error"] = str(e)
        
        logger.info("Collected GitHub metrics for Phase 7")
        return metrics