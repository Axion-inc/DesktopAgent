"""
WebX Marketplace β - Template Submission Pipeline
Implements submit→verify→dry-run→install pipeline for template distribution
"""

import asyncio
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import yaml  # noqa: F401

from ..utils.logging import get_logger
from ..security.policy_engine import get_policy_engine

logger = get_logger(__name__)


class SubmissionStatus(Enum):
    SUBMITTED = "submitted"
    VERIFYING = "verifying"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    DRY_RUN_TESTING = "dry_run_testing"
    DRY_RUN_PASSED = "dry_run_passed"
    DRY_RUN_FAILED = "dry_run_failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"


@dataclass
class TemplateSubmission:
    submission_id: str
    template_name: str
    version: str
    author: str
    description: str
    category: str
    submitted_at: datetime
    status: SubmissionStatus
    template_content: str
    signature_data: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    dry_run_result: Optional[Dict[str, Any]] = None
    reviewer_notes: str = ""
    approval_reason: str = ""
    rejection_reason: str = ""
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = asdict(self)
        result['submitted_at'] = self.submitted_at.isoformat()
        result['status'] = self.status.value
        return result


class MarketplaceBeta:
    def __init__(self, storage_dir: Path = None):
        self.storage_dir = storage_dir or Path("data/marketplace_beta")
        self.submissions_dir = self.storage_dir / "submissions"
        self.templates_dir = self.storage_dir / "templates"
        self.dry_run_dir = self.storage_dir / "dry_runs"

        # Create directories
        for dir_path in [self.storage_dir, self.submissions_dir, self.templates_dir, self.dry_run_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        self.policy_engine = get_policy_engine()
        self.submissions: Dict[str, TemplateSubmission] = {}
        self.load_submissions()

    def load_submissions(self):
        """Load existing submissions from storage"""
        try:
            submissions_index = self.storage_dir / "submissions_index.json"
            if submissions_index.exists():
                with open(submissions_index, 'r') as f:
                    data = json.load(f)

                for submission_data in data.get('submissions', []):
                    submission = TemplateSubmission(
                        submission_id=submission_data['submission_id'],
                        template_name=submission_data['template_name'],
                        version=submission_data['version'],
                        author=submission_data['author'],
                        description=submission_data['description'],
                        category=submission_data['category'],
                        submitted_at=datetime.fromisoformat(submission_data['submitted_at']),
                        status=SubmissionStatus(submission_data['status']),
                        template_content=submission_data['template_content'],
                        signature_data=submission_data.get('signature_data'),
                        verification_result=submission_data.get('verification_result'),
                        dry_run_result=submission_data.get('dry_run_result'),
                        reviewer_notes=submission_data.get('reviewer_notes', ''),
                        approval_reason=submission_data.get('approval_reason', ''),
                        rejection_reason=submission_data.get('rejection_reason', ''),
                        metadata=submission_data.get('metadata', {})
                    )
                    self.submissions[submission.submission_id] = submission

                logger.info(f"Loaded {len(self.submissions)} marketplace submissions")

        except Exception as e:
            logger.error(f"Failed to load submissions: {e}")

    def save_submissions(self):
        """Save submissions to storage"""
        try:
            submissions_data = {
                'submissions': [submission.to_dict() for submission in self.submissions.values()],
                'last_updated': datetime.now().isoformat()
            }

            submissions_index = self.storage_dir / "submissions_index.json"
            with open(submissions_index, 'w') as f:
                json.dump(submissions_data, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save submissions: {e}")

    async def submit_template(
        self,
        template_name: str,
        version: str,
        author: str,
        description: str,
        category: str,
        template_content: str,
        signature_file: Optional[bytes] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Submit a template to the marketplace

        Returns:
            Tuple of (success, message, submission_id)
        """
        try:
            # Generate submission ID
            import secrets
            submission_id = f"sub_{secrets.token_hex(8)}"

            # Parse and validate template content
            try:
                from ..dsl.parser import parse_yaml
                from ..dsl.validator import validate_plan
                plan = parse_yaml(template_content)
                validation_errors = validate_plan(plan)
                if validation_errors:
                    return False, f"Template validation failed: {'; '.join(validation_errors)}", None
            except Exception as e:
                return False, f"Template parsing failed: {str(e)}", None

            # Process signature if provided
            signature_data = None
            if signature_file:
                try:
                    signature_data = json.loads(signature_file.decode('utf-8'))
                except Exception as e:
                    return False, f"Invalid signature file: {str(e)}", None

            # Create submission
            submission = TemplateSubmission(
                submission_id=submission_id,
                template_name=template_name,
                version=version,
                author=author,
                description=description,
                category=category,
                submitted_at=datetime.now(),
                status=SubmissionStatus.SUBMITTED,
                template_content=template_content,
                signature_data=signature_data,
                metadata={
                    'template_hash': hashlib.sha256(template_content.encode()).hexdigest(),
                    'estimated_steps': len(plan.get('steps', [])),
                    'has_approval_requirements': any('approval' in str(step).lower() for step in plan.get('steps', []))
                }
            )

            # Save template file
            template_file = self.submissions_dir / f"{submission_id}.yaml"
            template_file.write_text(template_content, encoding='utf-8')

            # Save signature file if provided
            if signature_data:
                signature_file_path = self.submissions_dir / f"{submission_id}.sig.json"
                with open(signature_file_path, 'w') as f:
                    json.dump(signature_data, f, indent=2)

            # Store submission
            self.submissions[submission_id] = submission
            self.save_submissions()

            logger.info(f"Template submitted to marketplace: {submission_id} ({template_name} v{version})")

            # Start verification process asynchronously
            asyncio.create_task(self._verify_submission(submission_id))

            return True, f"Template submitted successfully. Submission ID: {submission_id}", submission_id

        except Exception as e:
            logger.error(f"Template submission failed: {e}")
            return False, f"Submission failed: {str(e)}", None

    async def _verify_submission(self, submission_id: str):
        """
        Verify a submitted template (async process)
        """
        try:
            submission = self.submissions.get(submission_id)
            if not submission:
                logger.error(f"Submission not found for verification: {submission_id}")
                return

            # Update status to verifying
            submission.status = SubmissionStatus.VERIFYING
            self.save_submissions()

            logger.info(f"Starting verification for submission: {submission_id}")

            # Verify template signature if provided
            verification_result = {
                'verified_at': datetime.now().isoformat(),
                'signature_valid': False,
                'trust_level': 'unknown',
                'security_issues': [],
                'warnings': []
            }

            if submission.signature_data:
                template_file = self.submissions_dir / f"{submission_id}.yaml"
                signature_file = self.submissions_dir / f"{submission_id}.sig.json"

                if template_file.exists() and signature_file.exists():
                    policy_result = self.policy_engine.verify_template_signature(template_file, signature_file)

                    verification_result.update({
                        'signature_valid': policy_result.valid,
                        'trust_level': policy_result.trust_level.value,
                        'key_trusted': policy_result.key_trusted,
                        'key_id': policy_result.key_id,
                        'errors': policy_result.errors,
                        'warnings': policy_result.warnings
                    })
                else:
                    verification_result['errors'] = ['Template or signature file missing']
            else:
                verification_result['warnings'].append('No signature provided - template is unsigned')

            # Additional security checks
            security_issues = []

            # Check for risky operations
            risky_actions = ['click_by_text', 'fill_by_label', 'compose_mail', 'move_to']
            template_lower = submission.template_content.lower()
            found_risky = [action for action in risky_actions if action in template_lower]
            if found_risky:
                security_issues.append(f"Contains risky operations: {', '.join(found_risky)}")

            # Check for external URLs
            if 'http://' in submission.template_content or 'https://' in submission.template_content:
                security_issues.append("Contains external URLs - review required")

            # Check for file system operations
            if 'file://' in submission.template_content or any(
                word in template_lower for word in ['mkdir', 'rmdir', 'delete']
            ):
                security_issues.append("Contains file system operations")

            verification_result['security_issues'] = security_issues

            # Update submission with verification result
            submission.verification_result = verification_result

            # Determine verification status
            if verification_result.get('errors'):
                submission.status = SubmissionStatus.VERIFICATION_FAILED
                submission.rejection_reason = f"Verification failed: {'; '.join(verification_result['errors'])}"
            else:
                submission.status = SubmissionStatus.VERIFICATION_PASSED
                # Proceed to dry run testing
                await asyncio.sleep(1)  # Small delay
                await self._dry_run_test(submission_id)

            self.save_submissions()
            logger.info(f"Verification completed for submission: {submission_id} (status: {submission.status.value})")

        except Exception as e:
            logger.error(f"Verification failed for submission {submission_id}: {e}")
            submission = self.submissions.get(submission_id)
            if submission:
                submission.status = SubmissionStatus.VERIFICATION_FAILED
                submission.rejection_reason = f"Verification error: {str(e)}"
                self.save_submissions()

    async def _dry_run_test(self, submission_id: str):
        """
        Perform dry run testing of the template
        """
        try:
            submission = self.submissions.get(submission_id)
            if not submission:
                logger.error(f"Submission not found for dry run: {submission_id}")
                return

            # Update status
            submission.status = SubmissionStatus.DRY_RUN_TESTING
            self.save_submissions()

            logger.info(f"Starting dry run test for submission: {submission_id}")

            # Create dry run result
            dry_run_result = {
                'tested_at': datetime.now().isoformat(),
                'success': False,
                'steps_executed': 0,
                'steps_total': 0,
                'execution_time_ms': 0,
                'errors': [],
                'warnings': [],
                'screenshots': []
            }

            try:
                # Parse template
                from ..dsl.parser import parse_yaml
                from ..dsl.runner import Runner

                plan = parse_yaml(submission.template_content)
                steps = plan.get('steps', [])
                dry_run_result['steps_total'] = len(steps)

                # Create dry run environment
                dry_run_variables = {
                    'test_mode': True,
                    'dry_run': True,
                    'email': 'test@marketplace-beta.local',
                    'name': 'Test User'
                }

                # Execute in dry run mode
                start_time = datetime.now()
                _ = Runner(plan, dry_run_variables, dry_run=True)

                # Execute each step in dry run mode
                for idx, step in enumerate(steps):
                    try:
                        action, params = list(step.items())[0]
                        logger.debug(f"Dry run step {idx + 1}: {action}")

                        # For dry run, we just validate the step structure
                        if not isinstance(params, dict):
                            dry_run_result['errors'].append(f"Step {idx + 1}: Invalid parameters for {action}")
                            break

                        dry_run_result['steps_executed'] = idx + 1

                    except Exception as step_error:
                        dry_run_result['errors'].append(f"Step {idx + 1} failed: {str(step_error)}")
                        break

                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                dry_run_result['execution_time_ms'] = int(execution_time)

                # Determine success
                if not dry_run_result['errors'] and dry_run_result['steps_executed'] == dry_run_result['steps_total']:
                    dry_run_result['success'] = True
                    submission.status = SubmissionStatus.DRY_RUN_PASSED
                    logger.info(f"Dry run passed for submission: {submission_id}")
                else:
                    submission.status = SubmissionStatus.DRY_RUN_FAILED
                    submission.rejection_reason = f"Dry run failed: {'; '.join(dry_run_result['errors'])}"
                    logger.warning(f"Dry run failed for submission: {submission_id}")

            except Exception as e:
                dry_run_result['errors'].append(f"Dry run execution error: {str(e)}")
                submission.status = SubmissionStatus.DRY_RUN_FAILED
                submission.rejection_reason = f"Dry run error: {str(e)}"

            # Save dry run result
            submission.dry_run_result = dry_run_result
            self.save_submissions()

        except Exception as e:
            logger.error(f"Dry run test failed for submission {submission_id}: {e}")
            submission = self.submissions.get(submission_id)
            if submission:
                submission.status = SubmissionStatus.DRY_RUN_FAILED
                submission.rejection_reason = f"Dry run test error: {str(e)}"
                self.save_submissions()

    def approve_submission(self, submission_id: str, approver: str, reason: str = "") -> Tuple[bool, str]:
        """Approve a submission for publication"""
        try:
            submission = self.submissions.get(submission_id)
            if not submission:
                return False, "Submission not found"

            if submission.status != SubmissionStatus.DRY_RUN_PASSED:
                return False, f"Submission not ready for approval (status: {submission.status.value})"

            submission.status = SubmissionStatus.APPROVED
            submission.approval_reason = reason
            submission.metadata['approved_by'] = approver
            submission.metadata['approved_at'] = datetime.now().isoformat()

            self.save_submissions()
            logger.info(f"Submission approved: {submission_id} by {approver}")

            return True, "Submission approved successfully"

        except Exception as e:
            logger.error(f"Failed to approve submission {submission_id}: {e}")
            return False, str(e)

    def reject_submission(self, submission_id: str, reviewer: str, reason: str) -> Tuple[bool, str]:
        """Reject a submission"""
        try:
            submission = self.submissions.get(submission_id)
            if not submission:
                return False, "Submission not found"

            submission.status = SubmissionStatus.REJECTED
            submission.rejection_reason = reason
            submission.metadata['rejected_by'] = reviewer
            submission.metadata['rejected_at'] = datetime.now().isoformat()

            self.save_submissions()
            logger.info(f"Submission rejected: {submission_id} by {reviewer}")

            return True, "Submission rejected"

        except Exception as e:
            logger.error(f"Failed to reject submission {submission_id}: {e}")
            return False, str(e)

    def publish_submission(self, submission_id: str) -> Tuple[bool, str]:
        """Publish an approved submission to the marketplace"""
        try:
            submission = self.submissions.get(submission_id)
            if not submission:
                return False, "Submission not found"

            if submission.status != SubmissionStatus.APPROVED:
                return False, f"Submission not approved for publication (status: {submission.status.value})"

            # Copy template to published templates directory
            published_file = self.templates_dir / f"{submission.template_name}_{submission.version}.yaml"
            published_file.write_text(submission.template_content, encoding='utf-8')

            # Copy signature if available
            if submission.signature_data:
                signature_file = self.templates_dir / f"{submission.template_name}_{submission.version}.sig.json"
                with open(signature_file, 'w') as f:
                    json.dump(submission.signature_data, f, indent=2)

            submission.status = SubmissionStatus.PUBLISHED
            submission.metadata['published_at'] = datetime.now().isoformat()
            submission.metadata['published_file'] = str(published_file)

            self.save_submissions()
            logger.info(f"Submission published: {submission_id} -> {published_file}")

            return True, f"Template published as {published_file.name}"

        except Exception as e:
            logger.error(f"Failed to publish submission {submission_id}: {e}")
            return False, str(e)

    def list_submissions(
        self,
        status_filter: Optional[SubmissionStatus] = None,
        author_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List submissions with optional filters"""
        try:
            submissions = list(self.submissions.values())

            # Apply filters
            if status_filter:
                submissions = [s for s in submissions if s.status == status_filter]

            if author_filter:
                submissions = [s for s in submissions if author_filter.lower() in s.author.lower()]

            # Sort by submission date (newest first)
            submissions.sort(key=lambda x: x.submitted_at, reverse=True)

            return [submission.to_dict() for submission in submissions]

        except Exception as e:
            logger.error(f"Failed to list submissions: {e}")
            return []

    def get_submission(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific submission"""
        submission = self.submissions.get(submission_id)
        if submission:
            return submission.to_dict()
        return None

    def get_marketplace_stats(self) -> Dict[str, Any]:
        """Get marketplace statistics"""
        try:
            submissions = list(self.submissions.values())
            status_counts = {}

            for status in SubmissionStatus:
                status_counts[status.value] = len([s for s in submissions if s.status == status])

            # Calculate approval rate
            total_completed = sum(status_counts[status] for status in [
                SubmissionStatus.APPROVED.value,
                SubmissionStatus.REJECTED.value,
                SubmissionStatus.PUBLISHED.value
            ])

            approved_count = (
                status_counts.get(SubmissionStatus.APPROVED.value, 0)
                + status_counts.get(SubmissionStatus.PUBLISHED.value, 0)
            )

            approval_rate = (approved_count / total_completed * 100) if total_completed > 0 else 0

            return {
                'total_submissions': len(submissions),
                'status_distribution': status_counts,
                'approval_rate_percent': round(approval_rate, 1),
                'published_templates': status_counts.get(SubmissionStatus.PUBLISHED.value, 0),
                'pending_review': sum(status_counts[status] for status in [
                    SubmissionStatus.DRY_RUN_PASSED.value,
                    SubmissionStatus.VERIFICATION_PASSED.value
                ])
            }

        except Exception as e:
            logger.error(f"Failed to get marketplace stats: {e}")
            return {"error": str(e)}

    async def install_template(self, submission_id: str, username: str) -> Tuple[bool, str]:
        """Install a published template to the local plans/templates directory"""
        try:
            submission = self.submissions.get(submission_id)
            if not submission:
                return False, "Template not found"

            if submission.status != SubmissionStatus.PUBLISHED:
                return False, "Template is not published and cannot be installed"

            # Create plans/templates directory if it doesn't exist
            templates_dir = Path("plans/templates")
            templates_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with version suffix
            template_filename = f"{submission.template_name}_{submission.version}.yaml"
            destination_path = templates_dir / template_filename

            # Check if template already exists
            if destination_path.exists():
                return False, f"Template {template_filename} is already installed"

            # Install template file
            destination_path.write_text(submission.template_content, encoding='utf-8')

            # Install signature file if available
            if submission.signature_data:
                signature_filename = f"{submission.template_name}_{submission.version}.sig.json"
                signature_path = templates_dir / signature_filename
                with open(signature_path, 'w', encoding='utf-8') as f:
                    json.dump(submission.signature_data, f, indent=2)
                logger.info(f"Signature installed: {signature_filename}")

            # Update submission metadata
            if not submission.metadata:
                submission.metadata = {}
            if 'installations' not in submission.metadata:
                submission.metadata['installations'] = []

            submission.metadata['installations'].append({
                'user': username,
                'installed_at': datetime.now().isoformat(),
                'installed_path': str(destination_path)
            })

            self.save_submissions()

            logger.info(f"Template installed: {template_filename} by {username}")
            return True, f"Template installed as {template_filename}"

        except Exception as e:
            logger.error(f"Failed to install template {submission_id}: {e}")
            return False, str(e)


# Global marketplace instance
_marketplace_beta: Optional[MarketplaceBeta] = None


def get_marketplace_beta() -> MarketplaceBeta:
    """Get the global marketplace beta instance"""
    global _marketplace_beta
    if _marketplace_beta is None:
        _marketplace_beta = MarketplaceBeta()
    return _marketplace_beta
