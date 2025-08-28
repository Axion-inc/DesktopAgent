"""
GitHub CLI Integration - Phase 7
Wrapper for gh CLI commands to manage GitHub resources
"""

import json
import logging
import subprocess
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class GitHubResource:
    """Represents a GitHub resource (Issue, PR, Milestone, etc.)"""
    resource_type: str  # "issue", "pr", "milestone", "label"
    id: str
    title: str
    state: str = "open"
    url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None


class GitHubCLIError(Exception):
    """GitHub CLI operation error"""
    pass


class GitHubCLIWrapper:
    """
    Wrapper for GitHub CLI (gh) operations
    Provides programmatic access to GitHub resources via gh commands
    """

    def __init__(self, repo_path: str = None, auth_token: str = None):
        """Initialize GitHub CLI wrapper"""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.auth_token = auth_token
        self._verify_gh_cli()
        logger.info("GitHub CLI wrapper initialized")

    def _verify_gh_cli(self):
        """Verify that gh CLI is installed and authenticated"""
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise GitHubCLIError("gh CLI not found or not working")

            # Check authentication
            auth_result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.repo_path
            )
            if auth_result.returncode != 0:
                logger.warning("gh CLI not authenticated - some operations may fail")

        except subprocess.TimeoutExpired:
            raise GitHubCLIError("gh CLI command timed out")
        except FileNotFoundError:
            raise GitHubCLIError("gh CLI not installed")

    def _run_gh_command(self, args: List[str], input_data: str = None) -> Dict[str, Any]:
        """Execute gh CLI command and return parsed result"""
        cmd = ["gh"] + args

        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.repo_path
            )

            if result.returncode != 0:
                raise GitHubCLIError(f"gh command failed: {result.stderr}")

            # Try to parse JSON output
            try:
                return json.loads(result.stdout) if result.stdout.strip() else {}
            except json.JSONDecodeError:
                return {"output": result.stdout, "success": True}

        except subprocess.TimeoutExpired:
            raise GitHubCLIError("gh CLI command timed out")
        except Exception as e:
            raise GitHubCLIError(f"gh CLI error: {str(e)}")

    def create_issue(
        self,
        title: str,
        body: str = "",
        labels: List[str] = None,
        assignees: List[str] = None,
        milestone: str = None
    ) -> GitHubResource:
        """Create a new GitHub issue"""

        args = ["issue", "create", "--title", title, "--body", body]

        if labels:
            args.extend(["--label", ",".join(labels)])
        if assignees:
            args.extend(["--assignee", ",".join(assignees)])
        if milestone:
            args.extend(["--milestone", milestone])

        # Add JSON output for parsing
        args.extend(["--json", "number,title,url,state"])

        result = self._run_gh_command(args)

        issue_resource = GitHubResource(
            resource_type="issue",
            id=str(result.get("number", "")),
            title=result.get("title", title),
            state=result.get("state", "open"),
            url=result.get("url", ""),
            metadata={
                "labels": labels or [],
                "assignees": assignees or [],
                "milestone": milestone
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"Created GitHub issue #{issue_resource.id}: {title}")
        return issue_resource

    def create_pull_request(
        self,
        title: str,
        body: str = "",
        base: str = "main",
        head: str = None,
        labels: List[str] = None,
        reviewers: List[str] = None,
        draft: bool = False
    ) -> GitHubResource:
        """Create a new GitHub pull request"""

        args = ["pr", "create", "--title", title, "--body", body, "--base", base]

        if head:
            args.extend(["--head", head])
        if labels:
            args.extend(["--label", ",".join(labels)])
        if reviewers:
            args.extend(["--reviewer", ",".join(reviewers)])
        if draft:
            args.append("--draft")

        # Add JSON output for parsing
        args.extend(["--json", "number,title,url,state"])

        result = self._run_gh_command(args)

        pr_resource = GitHubResource(
            resource_type="pr",
            id=str(result.get("number", "")),
            title=result.get("title", title),
            state=result.get("state", "open"),
            url=result.get("url", ""),
            metadata={
                "base": base,
                "head": head,
                "labels": labels or [],
                "reviewers": reviewers or [],
                "draft": draft
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"Created GitHub PR #{pr_resource.id}: {title}")
        return pr_resource

    def create_milestone(
        self,
        title: str,
        description: str = "",
        due_date: str = None,
        state: str = "open"
    ) -> GitHubResource:
        """Create a new GitHub milestone"""

        # Note: gh CLI milestone creation may require API calls
        # For now, we'll use the API-style approach through gh api
        milestone_data = {
            "title": title,
            "description": description,
            "state": state
        }

        if due_date:
            milestone_data["due_on"] = due_date

        args = ["api", "repos/:owner/:repo/milestones", "--method", "POST"]

        result = self._run_gh_command(args, json.dumps(milestone_data))

        milestone_resource = GitHubResource(
            resource_type="milestone",
            id=str(result.get("number", "")),
            title=result.get("title", title),
            state=result.get("state", state),
            url=result.get("html_url", ""),
            metadata={
                "description": description,
                "due_date": due_date
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"Created GitHub milestone #{milestone_resource.id}: {title}")
        return milestone_resource

    def create_label(
        self,
        name: str,
        color: str = "0969da",
        description: str = ""
    ) -> GitHubResource:
        """Create a new GitHub label"""

        label_data = {
            "name": name,
            "color": color.lstrip("#"),
            "description": description
        }

        args = ["api", "repos/:owner/:repo/labels", "--method", "POST"]

        result = self._run_gh_command(args, json.dumps(label_data))

        label_resource = GitHubResource(
            resource_type="label",
            id=result.get("id", ""),
            title=result.get("name", name),
            state="active",
            url=result.get("url", ""),
            metadata={
                "color": result.get("color", color),
                "description": description
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"Created GitHub label: {name}")
        return label_resource

    def list_issues(self, state: str = "open", limit: int = 30) -> List[GitHubResource]:
        """List GitHub issues"""

        args = [
            "issue", "list",
            "--state", state,
            "--limit", str(limit),
            "--json", "number,title,url,state,labels"
        ]

        result = self._run_gh_command(args)

        issues = []
        for issue_data in result:
            issue = GitHubResource(
                resource_type="issue",
                id=str(issue_data.get("number", "")),
                title=issue_data.get("title", ""),
                state=issue_data.get("state", "open"),
                url=issue_data.get("url", ""),
                metadata={"labels": issue_data.get("labels", [])}
            )
            issues.append(issue)

        logger.info(f"Retrieved {len(issues)} GitHub issues")
        return issues

    def list_pull_requests(self, state: str = "open", limit: int = 30) -> List[GitHubResource]:
        """List GitHub pull requests"""

        args = [
            "pr", "list",
            "--state", state,
            "--limit", str(limit),
            "--json", "number,title,url,state,labels"
        ]

        result = self._run_gh_command(args)

        prs = []
        for pr_data in result:
            pr = GitHubResource(
                resource_type="pr",
                id=str(pr_data.get("number", "")),
                title=pr_data.get("title", ""),
                state=pr_data.get("state", "open"),
                url=pr_data.get("url", ""),
                metadata={"labels": pr_data.get("labels", [])}
            )
            prs.append(pr)

        logger.info(f"Retrieved {len(prs)} GitHub PRs")
        return prs

    def trigger_workflow(
        self,
        workflow: str,
        ref: str = "main",
        inputs: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Trigger a GitHub Actions workflow"""

        args = ["workflow", "run", workflow, "--ref", ref]

        if inputs:
            for key, value in inputs.items():
                args.extend(["--field", f"{key}={value}"])

        _ = self._run_gh_command(args)

        logger.info(f"Triggered GitHub workflow: {workflow}")
        return {"success": True, "workflow": workflow, "ref": ref, "inputs": inputs}

    def get_repository_info(self) -> Dict[str, Any]:
        """Get current repository information"""

        args = ["repo", "view", "--json", "name,owner,url,defaultBranch"]

        result = self._run_gh_command(args)

        logger.info(f"Retrieved repo info: {result.get('name', 'unknown')}")
        return result


class GitHubIntegrationManager:
    """
    High-level GitHub integration manager
    Coordinates GitHub operations for Phase 7 features
    """

    def __init__(self, repo_path: str = None):
        """Initialize GitHub integration manager"""
        self.gh_cli = GitHubCLIWrapper(repo_path)
        self.repo_info = self.gh_cli.get_repository_info()
        logger.info("GitHub integration manager initialized")

    def create_l4_execution_issue(
        self,
        execution_id: str,
        template_name: str,
        deviation_reason: str,
        execution_context: Dict[str, Any]
    ) -> GitHubResource:
        """Create GitHub issue for L4 execution deviation"""

        title = f"L4 Execution Deviation - {template_name} ({execution_id[:8]})"

        body = f"""## L4 Autopilot Execution Deviation

**Execution ID:** `{execution_id}`
**Template:** {template_name}
**Deviation Reason:** {deviation_reason}

### Execution Context
```json
{json.dumps(execution_context, indent=2, ensure_ascii=False)}
```

### Next Steps
- [ ] Review execution logs
- [ ] Analyze deviation cause
- [ ] Update policy if needed
- [ ] Consider template patch

---
*Generated automatically by Desktop Agent L4 Autopilot System*
"""

        labels = ["l4-autopilot", "deviation", "automated"]

        return self.gh_cli.create_issue(
            title=title,
            body=body,
            labels=labels
        )

    def create_policy_violation_issue(
        self,
        violation_type: str,
        template_name: str,
        policy_details: Dict[str, Any]
    ) -> GitHubResource:
        """Create GitHub issue for policy violation"""

        title = f"Policy Violation - {violation_type} in {template_name}"

        body = f"""## Policy Engine Violation

**Violation Type:** {violation_type}
**Template:** {template_name}

### Policy Details
```yaml
{json.dumps(policy_details, indent=2, ensure_ascii=False)}
```

### Actions Required
- [ ] Review policy configuration
- [ ] Update template if needed
- [ ] Consider policy adjustment

---
*Generated automatically by Desktop Agent Policy Engine v1*
"""

        labels = ["policy-violation", "security", "automated"]

        return self.gh_cli.create_issue(
            title=title,
            body=body,
            labels=labels
        )

    def create_patch_proposal_pr(
        self,
        patch_data: Dict[str, Any],
        template_name: str,
        branch_name: str
    ) -> GitHubResource:
        """Create GitHub PR for Planner L2 patch proposal"""

        title = f"L2 Differential Patch - {template_name}"

        body = f"""## Planner L2 Differential Patch Proposal

**Template:** {template_name}
**Patch Type:** {patch_data.get('patch_type', 'unknown')}
**Confidence:** {patch_data.get('confidence', 0):.2f}

### Patch Details
```json
{json.dumps(patch_data, indent=2, ensure_ascii=False)}
```

### Review Checklist
- [ ] Verify patch safety
- [ ] Test execution stability
- [ ] Approve for auto-adoption

---
*Generated automatically by Desktop Agent Planner L2 System*
"""

        labels = ["planner-l2", "differential-patch", "automated"]

        return self.gh_cli.create_pull_request(
            title=title,
            body=body,
            head=branch_name,
            labels=labels,
            draft=True
        )

    def setup_phase7_milestones(self) -> List[GitHubResource]:
        """Setup Phase 7 project milestones"""

        milestones = [
            {
                "title": "Phase 7 - L4 Autopilot",
                "description": "L4 Limited Full Automation with policy compliance and deviation detection"
            },
            {
                "title": "Phase 7 - Policy Engine v1",
                "description": "Policy-based execution control with safe-fail mechanisms"
            },
            {
                "title": "Phase 7 - Planner L2",
                "description": "Differential patch proposals for execution stability"
            },
            {
                "title": "Phase 7 - WebX Enhancements",
                "description": "Advanced web interaction capabilities (iframe/shadow/downloads/cookies)"
            }
        ]

        created_milestones = []
        for milestone_data in milestones:
            try:
                milestone = self.gh_cli.create_milestone(**milestone_data)
                created_milestones.append(milestone)
            except GitHubCLIError as e:
                logger.warning(f"Failed to create milestone {milestone_data['title']}: {e}")

        logger.info(f"Created {len(created_milestones)} Phase 7 milestones")
        return created_milestones

    def setup_phase7_labels(self) -> List[GitHubResource]:
        """Setup Phase 7 project labels"""

        labels = [
            {"name": "l4-autopilot", "color": "0969da", "description": "L4 Limited Full Automation"},
            {"name": "policy-engine", "color": "d73a49", "description": "Policy Engine v1"},
            {"name": "planner-l2", "color": "0e8a16", "description": "Planner L2 Differential Patches"},
            {"name": "webx-enhancement", "color": "6f42c1", "description": "WebX Advanced Features"},
            {"name": "deviation", "color": "f66a0a", "description": "L4 Execution Deviation"},
            {"name": "policy-violation", "color": "b60205", "description": "Policy Violation"},
            {"name": "differential-patch", "color": "1d76db", "description": "L2 Differential Patch"},
            {"name": "automated", "color": "5319e7", "description": "Automatically Generated"}
        ]

        created_labels = []
        for label_data in labels:
            try:
                label = self.gh_cli.create_label(**label_data)
                created_labels.append(label)
            except GitHubCLIError as e:
                logger.warning(f"Failed to create label {label_data['name']}: {e}")

        logger.info(f"Created {len(created_labels)} Phase 7 labels")
        return created_labels
