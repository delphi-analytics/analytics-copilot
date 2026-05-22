"""Reports CRUD + export endpoints."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models.report import Report
from backend.models.user import User
from backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])
DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


class CreateReportRequest(BaseModel):
    name: str
    conversation_id: str | None = None
    content: str = ""
    charts: list[dict] = []
    schedule: dict | None = None
    recipients: list[str] = []
    format: str = "pdf"


class UpdateReportRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    charts: list[dict] | None = None
    schedule: dict | None = None
    recipients: list[str] | None = None
    format: str | None = None


class ReportResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    conversation_id: str | None
    content: str
    charts: list[dict]
    schedule: dict | None
    recipients: list[str]
    format: str
    created_at: str


@router.post("")
async def create_report(payload: CreateReportRequest, current_user: UserDep, db: DbDep) -> dict:
    report = Report(
        id=str(uuid.uuid4()),
        name=payload.name,
        owner_id=current_user.id,
        conversation_id=payload.conversation_id,
        content=payload.content,
        charts=payload.charts,
        schedule=payload.schedule,
        recipients=payload.recipients,
        format=payload.format,
    )
    db.add(report)
    await db.flush()
    await db.commit()
    return {"id": report.id, "name": report.name, "status": "created"}


@router.get("", response_model=list[ReportResponse])
async def list_reports(current_user: UserDep, db: DbDep) -> list:
    result = await db.execute(
        select(Report).where(Report.owner_id == current_user.id).order_by(Report.created_at.desc())
    )
    reports = result.scalars().all()
    return [
        ReportResponse(
            id=r.id, name=r.name, owner_id=r.owner_id,
            conversation_id=r.conversation_id, content=r.content,
            charts=r.charts or [], schedule=r.schedule,
            recipients=r.recipients or [], format=r.format,
            created_at=r.created_at.isoformat(),
        )
        for r in reports
    ]


@router.get("/{report_id}")
async def get_report(report_id: str, current_user: UserDep, db: DbDep) -> ReportResponse:
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    if r.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")
    return ReportResponse(
        id=r.id, name=r.name, owner_id=r.owner_id,
        conversation_id=r.conversation_id, content=r.content,
        charts=r.charts or [], schedule=r.schedule,
        recipients=r.recipients or [], format=r.format,
        created_at=r.created_at.isoformat(),
    )


@router.put("/{report_id}")
async def update_report(report_id: str, payload: UpdateReportRequest, current_user: UserDep, db: DbDep) -> dict:
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    if r.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")

    update_data = {k: v for k, v in payload.model_dump(exclude_none=True).items() if v is not None}
    if update_data:
        await db.execute(update(Report).where(Report.id == report_id).values(**update_data))
        await db.commit()
    return {"status": "updated"}


@router.delete("/{report_id}")
async def delete_report(report_id: str, current_user: UserDep, db: DbDep) -> dict:
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    if r.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")

    await db.execute(sa_delete(Report).where(Report.id == report_id))
    await db.commit()
    return {"status": "deleted"}


@router.post("/{report_id}/export")
async def export_report(report_id: str, current_user: UserDep, db: DbDep) -> dict:
    """Export a report. Returns report data in the configured format."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    if r.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")

    return {
        "report_id": r.id,
        "name": r.name,
        "format": r.format,
        "content": r.content,
        "charts": r.charts or [],
        "exported_at": datetime.utcnow().isoformat(),
    }
