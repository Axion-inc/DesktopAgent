"""
CLI command for GitHub integration setup - Phase 7
Sets up GitHub milestones, labels, and integration
"""

import click
import os
import sys
from pathlib import Path

# Add app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.github_cli import GitHubIntegrationManager, GitHubCLIError
from integrations.github_api import GitHubAPIClient, GitHubAPIConfig, GitHubAPIError


@click.group()
def github():
    """GitHub integration commands for Phase 7"""
    pass


@github.command()
@click.option('--repo-path', default='.', help='Path to git repository')
def setup_labels(repo_path):
    """Setup Phase 7 GitHub labels"""
    click.echo("Setting up Phase 7 GitHub labels...")
    
    try:
        manager = GitHubIntegrationManager(repo_path)
        labels = manager.setup_phase7_labels()
        
        click.echo(f"✅ Created {len(labels)} GitHub labels:")
        for label in labels:
            click.echo(f"  - {label.title} ({label.metadata.get('color', 'default')})")
        
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Setup failed: {e}", err=True)
        sys.exit(1)


@github.command()
@click.option('--repo-path', default='.', help='Path to git repository')
def setup_milestones(repo_path):
    """Setup Phase 7 GitHub milestones"""
    click.echo("Setting up Phase 7 GitHub milestones...")
    
    try:
        manager = GitHubIntegrationManager(repo_path)
        milestones = manager.setup_phase7_milestones()
        
        click.echo(f"✅ Created {len(milestones)} GitHub milestones:")
        for milestone in milestones:
            click.echo(f"  - {milestone.title}")
        
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Setup failed: {e}", err=True)
        sys.exit(1)


@github.command()
@click.option('--repo-path', default='.', help='Path to git repository')
def setup_all(repo_path):
    """Setup all Phase 7 GitHub resources (labels, milestones)"""
    click.echo("Setting up all Phase 7 GitHub resources...")
    
    try:
        manager = GitHubIntegrationManager(repo_path)
        
        # Setup labels
        click.echo("\n🏷️  Creating labels...")
        labels = manager.setup_phase7_labels()
        click.echo(f"   Created {len(labels)} labels")
        
        # Setup milestones
        click.echo("\n🎯 Creating milestones...")
        milestones = manager.setup_phase7_milestones()
        click.echo(f"   Created {len(milestones)} milestones")
        
        click.echo(f"\n✅ Phase 7 GitHub setup completed successfully!")
        click.echo(f"   Labels: {len(labels)}")
        click.echo(f"   Milestones: {len(milestones)}")
        
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Setup failed: {e}", err=True)
        sys.exit(1)


@github.command()
@click.option('--execution-id', required=True, help='Execution ID that deviated')
@click.option('--template-name', required=True, help='Template name that deviated') 
@click.option('--reason', required=True, help='Deviation reason')
@click.option('--repo-path', default='.', help='Path to git repository')
def create_deviation_issue(execution_id, template_name, reason, repo_path):
    """Create GitHub issue for L4 execution deviation"""
    click.echo(f"Creating L4 deviation issue for execution {execution_id[:8]}...")
    
    try:
        manager = GitHubIntegrationManager(repo_path)
        
        execution_context = {
            "execution_id": execution_id,
            "template": template_name,
            "deviation_reason": reason,
            "reported_via": "cli"
        }
        
        issue = manager.create_l4_execution_issue(
            execution_id=execution_id,
            template_name=template_name, 
            deviation_reason=reason,
            execution_context=execution_context
        )
        
        click.echo(f"✅ Created GitHub issue #{issue.id}: {issue.title}")
        click.echo(f"   URL: {issue.url}")
        
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Issue creation failed: {e}", err=True)
        sys.exit(1)


@github.command()
@click.option('--violation-type', required=True, help='Policy violation type')
@click.option('--template-name', required=True, help='Template name')
@click.option('--repo-path', default='.', help='Path to git repository')
def create_policy_issue(violation_type, template_name, repo_path):
    """Create GitHub issue for policy violation"""
    click.echo(f"Creating policy violation issue for {template_name}...")
    
    try:
        manager = GitHubIntegrationManager(repo_path)
        
        policy_details = {
            "violation_type": violation_type,
            "template": template_name,
            "reported_via": "cli"
        }
        
        issue = manager.create_policy_violation_issue(
            violation_type=violation_type,
            template_name=template_name,
            policy_details=policy_details
        )
        
        click.echo(f"✅ Created GitHub issue #{issue.id}: {issue.title}")
        click.echo(f"   URL: {issue.url}")
        
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Issue creation failed: {e}", err=True)
        sys.exit(1)


@github.command()
def check_auth():
    """Check GitHub CLI authentication status"""
    click.echo("Checking GitHub CLI authentication...")
    
    try:
        from integrations.github_cli import GitHubCLIWrapper
        
        # This will trigger auth check in initialization
        wrapper = GitHubCLIWrapper()
        
        # Get repository info to verify connection
        repo_info = wrapper.get_repository_info()
        
        click.echo("✅ GitHub CLI authentication successful")
        click.echo(f"   Repository: {repo_info.get('name', 'unknown')}")
        click.echo(f"   Owner: {repo_info.get('owner', {}).get('login', 'unknown')}")
        click.echo(f"   URL: {repo_info.get('url', 'unknown')}")
        
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI authentication failed: {e}", err=True)
        click.echo("\n💡 To authenticate, run: gh auth login")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Authentication check failed: {e}", err=True)
        sys.exit(1)


@github.command()
@click.option('--state', default='open', help='Issue state (open, closed, all)')
@click.option('--limit', default=10, help='Maximum number of issues to show')
def list_issues(state, limit):
    """List GitHub issues"""
    click.echo(f"Listing GitHub issues (state: {state}, limit: {limit})...")
    
    try:
        from integrations.github_cli import GitHubCLIWrapper
        wrapper = GitHubCLIWrapper()
        
        issues = wrapper.list_issues(state=state, limit=limit)
        
        if not issues:
            click.echo("No issues found")
            return
        
        click.echo(f"\n📋 Found {len(issues)} issues:")
        for issue in issues:
            click.echo(f"  #{issue.id}: {issue.title}")
            click.echo(f"     State: {issue.state}")
            click.echo(f"     URL: {issue.url}")
            if issue.metadata.get("labels"):
                labels = ", ".join([label.get("name", "") for label in issue.metadata["labels"]])
                click.echo(f"     Labels: {labels}")
            click.echo()
            
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Failed to list issues: {e}", err=True)
        sys.exit(1)


@github.command()
@click.option('--workflow', required=True, help='Workflow name or file (e.g., ci.yml)')
@click.option('--ref', default='main', help='Git reference to run against')
def trigger_workflow(workflow, ref):
    """Trigger GitHub Actions workflow"""
    click.echo(f"Triggering GitHub workflow: {workflow} on {ref}...")
    
    try:
        from integrations.github_cli import GitHubCLIWrapper
        wrapper = GitHubCLIWrapper()
        
        result = wrapper.trigger_workflow(
            workflow=workflow,
            ref=ref
        )
        
        if result.get("success"):
            click.echo(f"✅ Workflow triggered successfully")
            click.echo(f"   Workflow: {workflow}")
            click.echo(f"   Reference: {ref}")
        else:
            click.echo(f"❌ Workflow trigger failed")
            
    except GitHubCLIError as e:
        click.echo(f"❌ GitHub CLI error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Failed to trigger workflow: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    github()