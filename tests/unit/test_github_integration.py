"""
Unit tests for GitHub Integration - Phase 7
GitHub CLI/API wrapper functionality tests
Red tests first (TDD) - should fail initially
"""

import pytest
import json
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import subprocess

# These imports will fail initially - that's expected for TDD
try:
    from app.integrations.github_cli import GitHubCLIWrapper, GitHubIntegrationManager, GitHubResource, GitHubCLIError
    from app.integrations.github_api import GitHubAPIClient, GitHubAPIConfig, GitHubAPIError, GitHubMetricsCollector
except ImportError:
    # Expected during TDD red phase
    GitHubCLIWrapper = None
    GitHubIntegrationManager = None
    GitHubResource = None
    GitHubCLIError = None
    GitHubAPIClient = None
    GitHubAPIConfig = None
    GitHubAPIError = None
    GitHubMetricsCollector = None


class TestGitHubCLIWrapper:
    """Test GitHub CLI wrapper functionality"""
    
    def test_gh_cli_verification(self):
        """Should verify gh CLI is installed and authenticated"""
        # RED: Will fail - GitHubCLIWrapper doesn't exist yet
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        with patch('subprocess.run') as mock_run:
            # Mock successful gh version check
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="gh version 2.0.0"),  # version check
                MagicMock(returncode=0, stdout="✓ Logged in")  # auth check
            ]
            
            wrapper = GitHubCLIWrapper()
            
            assert mock_run.call_count == 2
            # Check version command was called
            version_call = mock_run.call_args_list[0]
            assert version_call[0][0] == ["gh", "--version"]
    
    def test_create_issue_basic(self):
        """Should create GitHub issue via gh CLI"""
        # RED: Will fail - issue creation not implemented
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        wrapper = GitHubCLIWrapper()
        
        mock_issue_response = {
            "number": 42,
            "title": "Test Issue",
            "url": "https://github.com/user/repo/issues/42",
            "state": "open"
        }
        
        with patch.object(wrapper, '_run_gh_command') as mock_run:
            mock_run.return_value = mock_issue_response
            
            issue = wrapper.create_issue(
                title="Test Issue",
                body="Test description",
                labels=["bug", "urgent"]
            )
            
            assert isinstance(issue, GitHubResource)
            assert issue.resource_type == "issue"
            assert issue.id == "42"
            assert issue.title == "Test Issue"
            assert issue.state == "open"
            
            # Check gh command was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "issue" in call_args
            assert "create" in call_args
            assert "--title" in call_args
            assert "Test Issue" in call_args
    
    def test_create_pull_request(self):
        """Should create GitHub pull request via gh CLI"""
        # RED: Will fail - PR creation not implemented
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        wrapper = GitHubCLIWrapper()
        
        mock_pr_response = {
            "number": 123,
            "title": "Feature PR",
            "url": "https://github.com/user/repo/pull/123",
            "state": "open"
        }
        
        with patch.object(wrapper, '_run_gh_command') as mock_run:
            mock_run.return_value = mock_pr_response
            
            pr = wrapper.create_pull_request(
                title="Feature PR",
                body="Adds new feature",
                base="main",
                head="feature-branch",
                labels=["enhancement"],
                reviewers=["user1", "user2"],
                draft=True
            )
            
            assert isinstance(pr, GitHubResource)
            assert pr.resource_type == "pr"
            assert pr.id == "123"
            assert pr.title == "Feature PR"
            assert pr.metadata["draft"] is True
    
    def test_create_milestone(self):
        """Should create GitHub milestone via API call"""
        # RED: Will fail - milestone creation not implemented
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        wrapper = GitHubCLIWrapper()
        
        mock_milestone_response = {
            "number": 5,
            "title": "v2.0 Release",
            "html_url": "https://github.com/user/repo/milestone/5",
            "state": "open"
        }
        
        with patch.object(wrapper, '_run_gh_command') as mock_run:
            mock_run.return_value = mock_milestone_response
            
            milestone = wrapper.create_milestone(
                title="v2.0 Release",
                description="Major release milestone",
                due_date="2024-12-31T23:59:59Z"
            )
            
            assert isinstance(milestone, GitHubResource)
            assert milestone.resource_type == "milestone"
            assert milestone.id == "5"
            assert milestone.title == "v2.0 Release"
    
    def test_create_label(self):
        """Should create GitHub label via API call"""
        # RED: Will fail - label creation not implemented
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        wrapper = GitHubCLIWrapper()
        
        mock_label_response = {
            "id": "12345",
            "name": "l4-autopilot",
            "color": "0969da",
            "url": "https://api.github.com/repos/user/repo/labels/l4-autopilot"
        }
        
        with patch.object(wrapper, '_run_gh_command') as mock_run:
            mock_run.return_value = mock_label_response
            
            label = wrapper.create_label(
                name="l4-autopilot",
                color="#0969da",
                description="L4 Limited Full Automation"
            )
            
            assert isinstance(label, GitHubResource)
            assert label.resource_type == "label"
            assert label.title == "l4-autopilot"
            assert label.metadata["color"] == "0969da"
    
    def test_list_issues(self):
        """Should list GitHub issues with filtering"""
        # RED: Will fail - issue listing not implemented
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        wrapper = GitHubCLIWrapper()
        
        mock_issues_response = [
            {"number": 1, "title": "Issue 1", "url": "https://github.com/user/repo/issues/1", "state": "open", "labels": []},
            {"number": 2, "title": "Issue 2", "url": "https://github.com/user/repo/issues/2", "state": "open", "labels": []}
        ]
        
        with patch.object(wrapper, '_run_gh_command') as mock_run:
            mock_run.return_value = mock_issues_response
            
            issues = wrapper.list_issues(state="open", limit=10)
            
            assert len(issues) == 2
            assert all(isinstance(issue, GitHubResource) for issue in issues)
            assert all(issue.resource_type == "issue" for issue in issues)
            assert issues[0].id == "1"
            assert issues[1].id == "2"
    
    def test_trigger_workflow(self):
        """Should trigger GitHub Actions workflow"""
        # RED: Will fail - workflow triggering not implemented
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        wrapper = GitHubCLIWrapper()
        
        with patch.object(wrapper, '_run_gh_command') as mock_run:
            mock_run.return_value = {"success": True}
            
            result = wrapper.trigger_workflow(
                workflow="ci.yml",
                ref="main",
                inputs={"environment": "production", "version": "v1.2.3"}
            )
            
            assert result["success"] is True
            assert result["workflow"] == "ci.yml"
            assert result["ref"] == "main"
            assert result["inputs"]["environment"] == "production"
    
    def test_gh_cli_error_handling(self):
        """Should handle gh CLI command errors gracefully"""
        # RED: Will fail - error handling not implemented
        if GitHubCLIWrapper is None:
            pytest.skip("GitHubCLIWrapper not implemented yet")
            
        wrapper = GitHubCLIWrapper()
        
        with patch.object(wrapper, '_run_gh_command') as mock_run:
            mock_run.side_effect = GitHubCLIError("Authentication failed")
            
            with pytest.raises(GitHubCLIError) as exc_info:
                wrapper.create_issue(title="Test")
            
            assert "authentication failed" in str(exc_info.value).lower()


class TestGitHubIntegrationManager:
    """Test high-level GitHub integration manager"""
    
    def test_create_l4_execution_issue(self):
        """Should create GitHub issue for L4 execution deviation"""
        # RED: Will fail - integration manager not implemented
        if GitHubIntegrationManager is None:
            pytest.skip("GitHubIntegrationManager not implemented yet")
            
        with patch('app.integrations.github_cli.GitHubCLIWrapper') as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper_class.return_value = mock_wrapper
            mock_wrapper.get_repository_info.return_value = {"name": "test-repo", "owner": {"login": "user"}}
            
            # Mock successful issue creation
            mock_issue = GitHubResource(
                resource_type="issue",
                id="45",
                title="L4 Execution Deviation - test-template (12345678)",
                state="open"
            )
            mock_wrapper.create_issue.return_value = mock_issue
            
            manager = GitHubIntegrationManager()
            
            issue = manager.create_l4_execution_issue(
                execution_id="123456789abcdef",
                template_name="test-template",
                deviation_reason="Unexpected element not found",
                execution_context={"step": 5, "action": "click_by_text"}
            )
            
            assert issue.resource_type == "issue"
            assert "L4 Execution Deviation" in issue.title
            assert "test-template" in issue.title
            
            # Check that the issue was created with correct parameters
            mock_wrapper.create_issue.assert_called_once()
            call_args = mock_wrapper.create_issue.call_args
            assert "L4 Execution Deviation" in call_args[1]["title"]
            assert "l4-autopilot" in call_args[1]["labels"]
    
    def test_create_policy_violation_issue(self):
        """Should create GitHub issue for policy violation"""
        # RED: Will fail - policy violation issue creation not implemented
        if GitHubIntegrationManager is None:
            pytest.skip("GitHubIntegrationManager not implemented yet")
            
        with patch('app.integrations.github_cli.GitHubCLIWrapper') as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper_class.return_value = mock_wrapper
            mock_wrapper.get_repository_info.return_value = {"name": "test-repo"}
            
            mock_issue = GitHubResource(
                resource_type="issue",
                id="46",
                title="Policy Violation - Domain Restriction in test-template",
                state="open"
            )
            mock_wrapper.create_issue.return_value = mock_issue
            
            manager = GitHubIntegrationManager()
            
            issue = manager.create_policy_violation_issue(
                violation_type="Domain Restriction",
                template_name="test-template",
                policy_details={"blocked_domain": "unauthorized.com", "policy": "allow_domains"}
            )
            
            assert issue.resource_type == "issue"
            assert "Policy Violation" in issue.title
            assert "Domain Restriction" in issue.title
    
    def test_create_patch_proposal_pr(self):
        """Should create GitHub PR for Planner L2 patch proposal"""
        # RED: Will fail - patch proposal PR creation not implemented
        if GitHubIntegrationManager is None:
            pytest.skip("GitHubIntegrationManager not implemented yet")
            
        with patch('app.integrations.github_cli.GitHubCLIWrapper') as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper_class.return_value = mock_wrapper
            mock_wrapper.get_repository_info.return_value = {"name": "test-repo"}
            
            mock_pr = GitHubResource(
                resource_type="pr",
                id="124",
                title="L2 Differential Patch - test-template",
                state="open"
            )
            mock_wrapper.create_pull_request.return_value = mock_pr
            
            manager = GitHubIntegrationManager()
            
            patch_data = {
                "patch_type": "replace_text",
                "confidence": 0.92,
                "replacements": [{"find": "送信", "with": "確定"}]
            }
            
            pr = manager.create_patch_proposal_pr(
                patch_data=patch_data,
                template_name="test-template",
                branch_name="patch/test-template-20240827"
            )
            
            assert pr.resource_type == "pr"
            assert "L2 Differential Patch" in pr.title
            assert "test-template" in pr.title
    
    def test_setup_phase7_milestones(self):
        """Should setup Phase 7 project milestones"""
        # RED: Will fail - milestone setup not implemented
        if GitHubIntegrationManager is None:
            pytest.skip("GitHubIntegrationManager not implemented yet")
            
        with patch('app.integrations.github_cli.GitHubCLIWrapper') as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper_class.return_value = mock_wrapper
            mock_wrapper.get_repository_info.return_value = {"name": "test-repo"}
            
            # Mock milestone creation responses
            mock_milestones = [
                GitHubResource(resource_type="milestone", id="1", title="Phase 7 - L4 Autopilot"),
                GitHubResource(resource_type="milestone", id="2", title="Phase 7 - Policy Engine v1"),
                GitHubResource(resource_type="milestone", id="3", title="Phase 7 - Planner L2"),
                GitHubResource(resource_type="milestone", id="4", title="Phase 7 - WebX Enhancements")
            ]
            mock_wrapper.create_milestone.side_effect = mock_milestones
            
            manager = GitHubIntegrationManager()
            
            milestones = manager.setup_phase7_milestones()
            
            assert len(milestones) == 4
            assert all(milestone.resource_type == "milestone" for milestone in milestones)
            assert any("L4 Autopilot" in milestone.title for milestone in milestones)
            assert any("Policy Engine" in milestone.title for milestone in milestones)
    
    def test_setup_phase7_labels(self):
        """Should setup Phase 7 project labels"""
        # RED: Will fail - label setup not implemented
        if GitHubIntegrationManager is None:
            pytest.skip("GitHubIntegrationManager not implemented yet")
            
        with patch('app.integrations.github_cli.GitHubCLIWrapper') as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper_class.return_value = mock_wrapper
            mock_wrapper.get_repository_info.return_value = {"name": "test-repo"}
            
            # Mock successful label creation
            def create_label_side_effect(**kwargs):
                return GitHubResource(
                    resource_type="label", 
                    id="123", 
                    title=kwargs["name"], 
                    state="active"
                )
            
            mock_wrapper.create_label.side_effect = create_label_side_effect
            
            manager = GitHubIntegrationManager()
            
            labels = manager.setup_phase7_labels()
            
            assert len(labels) >= 6  # At least 6 Phase 7 labels
            assert all(label.resource_type == "label" for label in labels)
            
            label_names = [label.title for label in labels]
            assert "l4-autopilot" in label_names
            assert "policy-engine" in label_names
            assert "planner-l2" in label_names
            assert "webx-enhancement" in label_names


class TestGitHubAPIClient:
    """Test GitHub API client functionality"""
    
    def test_api_client_initialization(self):
        """Should initialize GitHub API client with proper configuration"""
        # RED: Will fail - GitHubAPIClient doesn't exist yet
        if GitHubAPIClient is None:
            pytest.skip("GitHubAPIClient not implemented yet")
            
        config = GitHubAPIConfig(
            token="test_token",
            owner="user",
            repo="test-repo"
        )
        
        client = GitHubAPIClient(config)
        
        assert client.config.token == "test_token"
        assert client.config.owner == "user"
        assert client.config.repo == "test-repo"
        assert "Authorization" in client.session.headers
    
    def test_create_issue_via_api(self):
        """Should create GitHub issue via direct API call"""
        # RED: Will fail - API issue creation not implemented
        if GitHubAPIClient is None:
            pytest.skip("GitHubAPIClient not implemented yet")
            
        config = GitHubAPIConfig(token="test_token", owner="user", repo="test-repo")
        client = GitHubAPIClient(config)
        
        mock_response = {
            "number": 47,
            "title": "API Test Issue",
            "html_url": "https://github.com/user/test-repo/issues/47",
            "state": "open"
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = client.create_issue(
                title="API Test Issue",
                body="Created via API",
                labels=["api-test"],
                assignees=["user1"]
            )
            
            assert result["number"] == 47
            assert result["title"] == "API Test Issue"
            
            # Check API call was made correctly
            mock_request.assert_called_once_with(
                "POST",
                "repos/user/test-repo/issues",
                {
                    "title": "API Test Issue",
                    "body": "Created via API",
                    "labels": ["api-test"],
                    "assignees": ["user1"]
                }
            )
    
    def test_api_error_handling(self):
        """Should handle GitHub API errors gracefully"""
        # RED: Will fail - API error handling not implemented
        if GitHubAPIClient is None:
            pytest.skip("GitHubAPIClient not implemented yet")
            
        config = GitHubAPIConfig(token="invalid_token", owner="user", repo="test-repo")
        client = GitHubAPIClient(config)
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = GitHubAPIError("API rate limit exceeded")
            
            with pytest.raises(GitHubAPIError) as exc_info:
                client.create_issue(title="Test")
            
            assert "rate limit" in str(exc_info.value).lower()


class TestGitHubMetricsCollector:
    """Test GitHub metrics collection"""
    
    def test_collect_phase7_metrics(self):
        """Should collect Phase 7 specific GitHub metrics"""
        # RED: Will fail - metrics collector not implemented
        if GitHubMetricsCollector is None:
            pytest.skip("GitHubMetricsCollector not implemented yet")
            
        config = GitHubAPIConfig(token="test_token", owner="user", repo="test-repo")
        api_client = GitHubAPIClient(config)
        
        collector = GitHubMetricsCollector(api_client)
        
        # Mock API responses
        mock_issues = [
            {"number": 1, "labels": [{"name": "l4-autopilot"}]},
            {"number": 2, "labels": [{"name": "policy-violation"}]},
            {"number": 3, "labels": [{"name": "bug"}]}
        ]
        
        mock_prs = [
            {"number": 1, "labels": [{"name": "planner-l2"}]},
            {"number": 2, "labels": [{"name": "enhancement"}]}
        ]
        
        mock_workflow_runs = [
            {"created_at": "2024-08-27T10:00:00Z"},
            {"created_at": "2024-08-27T15:30:00Z"}
        ]
        
        with patch.object(api_client, 'list_issues') as mock_list_issues:
            with patch.object(api_client, 'list_pull_requests') as mock_list_prs:
                with patch.object(api_client, 'get_workflow_runs') as mock_workflow_runs_call:
                    
                    # Setup mock responses based on label filtering
                    def list_issues_side_effect(labels="", **kwargs):
                        if labels == "l4-autopilot":
                            return [mock_issues[0]]
                        elif labels == "policy-violation":
                            return [mock_issues[1]]
                        else:
                            return mock_issues
                    
                    mock_list_issues.side_effect = list_issues_side_effect
                    mock_list_prs.return_value = mock_prs
                    mock_workflow_runs_call.return_value = mock_workflow_runs
                    
                    metrics = collector.collect_phase7_metrics()
                    
                    assert "github_issues_total" in metrics
                    assert "github_l4_issues" in metrics
                    assert "github_policy_violations" in metrics
                    assert "github_patch_proposals" in metrics
                    assert "github_workflow_runs_24h" in metrics
                    assert "collected_at" in metrics
                    
                    assert metrics["github_issues_total"] == 3
                    assert metrics["github_l4_issues"] == 1
                    assert metrics["github_policy_violations"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])