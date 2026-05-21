"""Admin Router - Handles knowledge document approvals."""
from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.auth.dependencies import require_role
from backend.models.user import User
from backend.database import get_db
from backend.models.approval_queue import ApprovalQueue
from backend.services.schema_scanner import scan_and_detect_changes
from backend.services.notifier import send_approval_notification
from backend.services.knowledge.business_knowledge import (
    get_business_knowledge_service,
    get_db_knowledge_service
)

router = APIRouter(prefix="/admin", tags=["Admin"])


class ApprovalResponse(BaseModel):
    id: str
    change_type: str
    title: str
    description: str
    diff_data: dict
    status: str
    created_at: str


@router.get("/approvals", response_model=list[ApprovalResponse])
async def get_pending_approvals(
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get all pending approvals."""
    result = await db.execute(
        select(ApprovalQueue).where(ApprovalQueue.status == "PENDING").order_by(ApprovalQueue.created_at)
    )
    items = result.scalars().all()
    return [
        ApprovalResponse(
            id=item.id,
            change_type=item.change_type,
            title=item.title,
            description=item.description,
            diff_data=item.diff_data or {},
            status=item.status,
            created_at=item.created_at.isoformat()
        )
        for item in items
    ]


@router.post("/trigger-scan")
async def trigger_schema_scan(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Trigger a schema scan and create approval request if changes detected."""
    async def scan_and_notify():
        try:
            scan_result = await scan_and_detect_changes()
            diff = scan_result.get("diff", {})

            if diff.get("type") == "no_changes":
                return {"status": "no_changes", "message": "No schema changes detected"}

            # Create approval queue entry
            approval = ApprovalQueue(
                change_type="db_schema",
                title=diff.get("summary", "Schema changes detected"),
                description="Database schema has changed since last scan",
                diff_data=diff,
                requested_by=current_user.id if current_user else "system"
            )
            db.add(approval)
            await db.commit()

            # Send notification (if configured)
            from backend.config import settings
            config = {
                "smtp_host": getattr(settings, "smtp_host", ""),
                "smtp_port": getattr(settings, "smtp_port", "587"),
                "smtp_user": getattr(settings, "smtp_user", ""),
                "smtp_password": getattr(settings, "smtp_password", ""),
                "slack_webhook_url": getattr(settings, "slack_webhook_url", ""),
                "notification_email": getattr(settings, "notification_email", "")
            }

            await send_approval_notification(
                change_type="db_schema",
                title=diff.get("summary", "Schema changes"),
                description="Database schema has changed. Please review the changes.",
                diff_data=diff,
                approval_url=f"http://localhost:8001/docs#/admin/admin_approve_approve__{approval.id}__post",
                config=config if any(config.values()) else None
            )

            return {"status": "approval_created", "approval_id": approval.id}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    background_tasks.add_task(scan_and_notify)
    return {"status": "scan_started"}


@router.post("/approve/{approval_id}")
async def approve_change(
    approval_id: str,
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Approve a pending change and apply it to the knowledge documents."""
    result = await db.execute(
        select(ApprovalQueue).where(ApprovalQueue.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Already {approval.status.lower()}")

    # Update approval status
    await db.execute(
        update(ApprovalQueue)
        .where(ApprovalQueue.id == approval_id)
        .values(
            status="APPROVED",
            reviewed_by=current_user.id,
            reviewed_at=datetime.utcnow()
        )
    )

    # Apply the changes to knowledge documents
    if approval.change_type == "db_schema":
        # Re-index DB knowledge
        db_service = get_db_knowledge_service()
        db_service.ensure_collection()
        # Trigger full re-index
        from backend.main import _reindex_knowledge
        await _reindex_knowledge()

    await db.commit()
    return {"status": "approved", "message": "Change approved and applied"}


@router.post("/reject/{approval_id}")
async def reject_change(
    approval_id: str,
    reason: str = "",
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Reject a pending change."""
    result = await db.execute(
        select(ApprovalQueue).where(ApprovalQueue.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Already {approval.status.lower()}")

    await db.execute(
        update(ApprovalQueue)
        .where(ApprovalQueue.id == approval_id)
        .values(
            status="REJECTED",
            reviewed_by=current_user.id,
            reviewed_at=datetime.utcnow(),
            metadata={"rejection_reason": reason}
        )
    )
    await db.commit()

    return {"status": "rejected", "message": "Change rejected"}
