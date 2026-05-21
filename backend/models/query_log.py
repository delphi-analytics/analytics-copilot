"""Query Log Model - Track all queries for analytics and insights."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Integer, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class QueryLog(Base):
    """Query execution log for analytics, monitoring, and insights."""
    __tablename__ = "query_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    conversation_id: Mapped[str] = mapped_column(String(255), index=True)
    datasource_id: Mapped[str] = mapped_column(String(100), index=True)

    # Query details
    question: Mapped[str] = mapped_column(String(2000))
    intent_type: Mapped[str] = mapped_column(String(100), index=True)
    sql_query: Mapped[str | None] = mapped_column(String(5000))

    # Results
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    viz_type: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int] = mapped_column(Integer)

    # Performance metrics
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    model_used: Mapped[str] = mapped_column(String(100))

    # Status
    error: Mapped[str | None] = mapped_column(String(1000))
    success: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
