"""Approval Queue Model - Tracks pending document updates awaiting approval."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class ApprovalQueue(Base):
    """Pending changes awaiting human approval before updating knowledge documents."""
    __tablename__ = "approval_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_type: Mapped[str] = mapped_column(String(50))  # "db_schema", "business_knowledge"
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    diff_data: Mapped[dict] = mapped_column(JSON)  # The actual changes
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING, APPROVED, REJECTED
    requested_by: Mapped[str] = mapped_column(String(255), default="system")
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    meta: Mapped[dict | None] = mapped_column(JSON)  # Additional context (renamed from 'metadata' - reserved in SQLAlchemy)
