import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class DataSource(Base):
    __tablename__ = "datasources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(50))   # postgresql | clickhouse | csv | excel | sqlite
    owner_id: Mapped[str] = mapped_column(String(36))

    # Connection config (encrypted in production)
    connection_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Cached schema
    schema_cache: Mapped[dict | None] = mapped_column(JSON)
    schema_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    row_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
