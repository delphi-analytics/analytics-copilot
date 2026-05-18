import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Dashboard(Base):
    __tablename__ = "dashboards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(String(36))
    layout: Mapped[dict] = mapped_column(JSON, default=dict)   # grid positions
    is_public: Mapped[bool] = mapped_column(default=False)
    refresh_interval_seconds: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    charts: Mapped[list["DashboardChart"]] = relationship("DashboardChart", back_populates="dashboard")


class DashboardChart(Base):
    __tablename__ = "dashboard_charts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dashboard_id: Mapped[str] = mapped_column(String(36), ForeignKey("dashboards.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    datasource_id: Mapped[str] = mapped_column(String(36))
    sql_query: Mapped[str] = mapped_column(Text)
    viz_config: Mapped[dict] = mapped_column(JSON)     # ECharts option object
    position: Mapped[dict] = mapped_column(JSON, default=dict)  # {x, y, w, h}
    refresh_interval_seconds: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    dashboard: Mapped["Dashboard"] = relationship("Dashboard", back_populates="charts")
