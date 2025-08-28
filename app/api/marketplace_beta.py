"""
WebX Marketplace β API
API endpoints for template submission pipeline: submit→verify→dry-run→install
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from ..webx.marketplace_beta import get_marketplace_beta, SubmissionStatus
from ..middleware.auth import require_admin, require_editor, get_current_user
from ..utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/marketplace-beta", tags=["Marketplace Beta"])


# Request/Response Models
class TemplateSubmissionRequest(BaseModel):
    template_name: str
    version: str
    author: str
    description: str
    category: str
    template_content: str


class SubmissionReviewRequest(BaseModel):
    action: str  # "approve" or "reject"
    reason: str = ""


class SubmissionResponse(BaseModel):
    success: bool
    message: str
    submission_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# Template Submission Endpoints

@router.post("/submit", response_model=SubmissionResponse)
@require_editor
async def submit_template(
    request: TemplateSubmissionRequest,
    signature_file: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user)
):
    """Submit a template to the marketplace for review"""
    try:
        marketplace = get_marketplace_beta()

        # Process signature file if provided
        signature_data = None
        if signature_file:
            if not signature_file.filename.endswith('.sig.json'):
                raise HTTPException(status_code=400, detail="Signature file must be a .sig.json file")

            signature_content = await signature_file.read()
            signature_data = signature_content

        # Submit template
        success, message, submission_id = await marketplace.submit_template(
            template_name=request.template_name,
            version=request.version,
            author=request.author,
            description=request.description,
            category=request.category,
            template_content=request.template_content,
            signature_file=signature_data
        )

        if success:
            logger.info(f"Template submitted by {current_user.username}: {submission_id}")
            return SubmissionResponse(
                success=True,
                message=message,
                submission_id=submission_id
            )
        else:
            raise HTTPException(status_code=400, detail=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/submissions", response_model=List[Dict[str, Any]])
async def list_submissions(
    status: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    current_user=Depends(get_current_user)
):
    """List all submissions with optional filters"""
    try:
        marketplace = get_marketplace_beta()

        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = SubmissionStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        submissions = marketplace.list_submissions(
            status_filter=status_filter,
            author_filter=author
        )

        return submissions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    current_user=Depends(get_current_user)
):
    """Get detailed information about a specific submission"""
    try:
        marketplace = get_marketplace_beta()

        submission = marketplace.get_submission(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        return submission

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get submission {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Review and Approval Endpoints

@router.post("/submissions/{submission_id}/review", response_model=SubmissionResponse)
@require_admin
async def review_submission(
    submission_id: str,
    request: SubmissionReviewRequest,
    current_user=Depends(get_current_user)
):
    """Review a submission (approve or reject) - Admin only"""
    try:
        marketplace = get_marketplace_beta()

        if request.action == "approve":
            success, message = marketplace.approve_submission(
                submission_id,
                current_user.username,
                request.reason
            )
        elif request.action == "reject":
            success, message = marketplace.reject_submission(
                submission_id,
                current_user.username,
                request.reason
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'")

        if success:
            logger.info(f"Submission {request.action}d by {current_user.username}: {submission_id}")
            return SubmissionResponse(success=True, message=message)
        else:
            raise HTTPException(status_code=400, detail=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to review submission {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submissions/{submission_id}/publish", response_model=SubmissionResponse)
@require_admin
async def publish_submission(
    submission_id: str,
    current_user=Depends(get_current_user)
):
    """Publish an approved submission to the marketplace - Admin only"""
    try:
        marketplace = get_marketplace_beta()

        success, message = marketplace.publish_submission(submission_id)

        if success:
            logger.info(f"Submission published by {current_user.username}: {submission_id}")
            return SubmissionResponse(success=True, message=message)
        else:
            raise HTTPException(status_code=400, detail=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to publish submission {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Statistics and Management

@router.get("/stats")
async def get_marketplace_stats(
    current_user=Depends(get_current_user)
):
    """Get marketplace β statistics - Public endpoint"""
    try:
        marketplace = get_marketplace_beta()

        stats = marketplace.get_marketplace_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get marketplace stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/submissions/{submission_id}/download")
@require_admin
async def download_submission_template(
    submission_id: str,
    current_user=Depends(get_current_user)
):
    """Download the template file for a submission - Admin only"""
    try:
        marketplace = get_marketplace_beta()

        submission = marketplace.get_submission(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Create temporary file for download
        template_file = marketplace.submissions_dir / f"{submission_id}.yaml"
        if not template_file.exists():
            raise HTTPException(status_code=404, detail="Template file not found")

        return FileResponse(
            path=template_file,
            filename=f"{submission['template_name']}_{submission['version']}.yaml",
            media_type="application/x-yaml"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download submission template {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/submissions/{submission_id}/signature")
@require_admin
async def download_submission_signature(
    submission_id: str,
    current_user=Depends(get_current_user)
):
    """Download the signature file for a submission - Admin only"""
    try:
        marketplace = get_marketplace_beta()

        submission = marketplace.get_submission(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        if not submission.get('signature_data'):
            raise HTTPException(status_code=404, detail="No signature file for this submission")

        signature_file = marketplace.submissions_dir / f"{submission_id}.sig.json"
        if not signature_file.exists():
            raise HTTPException(status_code=404, detail="Signature file not found")

        return FileResponse(
            path=signature_file,
            filename=f"{submission['template_name']}_{submission['version']}.sig.json",
            media_type="application/json"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download submission signature {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Queue Management

@router.get("/queue/pending")
@require_admin
async def get_pending_reviews(
    current_user=Depends(get_current_user)
):
    """Get submissions pending review - Admin only"""
    try:
        marketplace = get_marketplace_beta()

        # Get submissions that passed dry run and are ready for review
        pending_submissions = marketplace.list_submissions(
            status_filter=SubmissionStatus.DRY_RUN_PASSED
        )

        return {
            "pending_reviews": pending_submissions,
            "count": len(pending_submissions)
        }

    except Exception as e:
        logger.error(f"Failed to get pending reviews: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/verification")
async def get_verification_queue(
    current_user=Depends(get_current_user)
):
    """Get submissions in verification queue"""
    try:
        marketplace = get_marketplace_beta()

        # Get submissions currently being verified
        verifying_submissions = marketplace.list_submissions(
            status_filter=SubmissionStatus.VERIFYING
        )

        dry_run_submissions = marketplace.list_submissions(
            status_filter=SubmissionStatus.DRY_RUN_TESTING
        )

        return {
            "verifying": verifying_submissions,
            "dry_run_testing": dry_run_submissions,
            "total_in_queue": len(verifying_submissions) + len(dry_run_submissions)
        }

    except Exception as e:
        logger.error(f"Failed to get verification queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Template Installation
@router.post("/install/{submission_id}", response_model=SubmissionResponse)
async def install_template(
    submission_id: str,
    current_user=Depends(get_current_user)
):
    """Install a published template to the local template directory"""
    try:
        marketplace = get_marketplace_beta()

        # Get submission info
        submission = marketplace.get_submission(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check if template is published
        if submission.get('status') != 'published':
            raise HTTPException(status_code=400, detail="Template is not published and cannot be installed")

        # Install template to local directory
        success, message = await marketplace.install_template(submission_id, current_user.username)

        if success:
            logger.info(f"Template {submission_id} installed by {current_user.username}")
            return SubmissionResponse(
                success=True,
                message=f"Template '{submission['template_name']}' v{submission['version']} installed successfully",
                data={"installed_path": f"plans/templates/{submission['template_name']}.yaml"}
            )
        else:
            raise HTTPException(status_code=400, detail=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install template {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
