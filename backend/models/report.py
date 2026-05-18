import uuid
from datetime import datetime
from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[str] = mapped_column(String(36))
    conversation_id: Mapped[str | None] = mapped_column(String(36))
    content: Mapped[str] = mapped_column(Text)   # markdown content
    charts: Mapped[list] = mapped_column(JSON, default=list)
    schedule: Mapped[dict | None] = mapped_column(JSON)  # cron config for scheduled delivery
    recipients: Mapped[list] = mapped_column(JSON, default=list)  # email list
    format: Mapped[str] = mapped_column(String(20), default="pdf")   # pdf | excel | html
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
