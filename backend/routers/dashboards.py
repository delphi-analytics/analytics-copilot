"""Dashboard CRUD + chart refresh endpoints."""
from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models.dashboard import Dashboard, DashboardChart
from backend.data.connector import execute_query

router = APIRouter()
DbDep = Annotated[AsyncSession, Depends(get_db)]


class CreateDashboardRequest(BaseModel):
    name: str
    description: str | None = None
    owner_id: str = "anonymous"


class UpdateDashboardRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    layout: dict | None = None
    is_public: bool | None = None
    refresh_interval_seconds: int | None = None


class AddChartRequest(BaseModel):
    title: str
    datasource_id: str
    sql_query: str
    viz_config: dict
    position: dict = {}


class UpdateChartRequest(BaseModel):
    title: str | None = None
    sql_query: str | None = None
    viz_config: dict | None = None
    position: dict | None = None
    datasource_id: str | None = None


@router.post("")
async def create_dashboard(payload: CreateDashboardRequest, db: DbDep) -> dict:
    d = Dashboard(id=str(uuid.uuid4()), name=payload.name,
                  description=payload.description, owner_id=payload.owner_id)
    db.add(d)
    await db.flush()
    await db.commit()
    return {"id": d.id, "name": d.name, "status": "created"}


@router.get("")
async def list_dashboards(owner_id: str = "anonymous", db: DbDep = None) -> list:
    result = await db.execute(select(Dashboard).where(Dashboard.owner_id == owner_id))
    return [{"id": d.id, "name": d.name, "description": d.description,
             "created_at": d.created_at.isoformat(), "is_public": d.is_public,
             "chart_count": len(d.charts) if hasattr(d, 'charts') else 0}
            for d in result.scalars()]


@router.get("/{dashboard_id}")
async def get_dashboard(dashboard_id: str, db: DbDep) -> dict:
    result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dashboard not found")
    charts_result = await db.execute(select(DashboardChart).where(DashboardChart.dashboard_id == dashboard_id))
    charts = charts_result.scalars().all()
    return {
        "id": d.id, "name": d.name, "description": d.description, "layout": d.layout,
        "is_public": d.is_public, "refresh_interval_seconds": d.refresh_interval_seconds,
        "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat(),
        "charts": [{"id": c.id, "title": c.title, "viz_config": c.viz_config,
                    "position": c.position, "sql_query": c.sql_query,
                    "datasource_id": c.datasource_id} for c in charts],
    }


@router.put("/{dashboard_id}")
async def update_dashboard(dashboard_id: str, payload: UpdateDashboardRequest, db: DbDep) -> dict:
    result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dashboard not found")

    update_data = {k: v for k, v in payload.model_dump(exclude_none=True).items() if v is not None}
    if update_data:
        await db.execute(
            Dashboard.__table__.update().where(Dashboard.id == dashboard_id).values(**update_data)
        )
        await db.commit()
    return {"status": "updated"}


@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str, db: DbDep) -> dict:
    result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dashboard not found")

    await db.execute(sa_delete(DashboardChart).where(DashboardChart.dashboard_id == dashboard_id))
    await db.execute(sa_delete(Dashboard).where(Dashboard.id == dashboard_id))
    await db.commit()
    return {"status": "deleted"}


@router.post("/{dashboard_id}/charts")
async def add_chart(dashboard_id: str, payload: AddChartRequest, db: DbDep) -> dict:
    chart = DashboardChart(
        id=str(uuid.uuid4()), dashboard_id=dashboard_id, title=payload.title,
        datasource_id=payload.datasource_id, sql_query=payload.sql_query,
        viz_config=payload.viz_config, position=payload.position,
    )
    db.add(chart)
    await db.flush()
    await db.commit()
    return {"chart_id": chart.id, "status": "added"}


@router.put("/{dashboard_id}/charts/{chart_id}")
async def update_chart(dashboard_id: str, chart_id: str, payload: UpdateChartRequest, db: DbDep) -> dict:
    result = await db.execute(select(DashboardChart).where(DashboardChart.id == chart_id))
    chart = result.scalar_one_or_none()
    if not chart:
        raise HTTPException(404, "Chart not found")

    update_data = {k: v for k, v in payload.model_dump(exclude_none=True).items() if v is not None}
    if update_data:
        await db.execute(
            DashboardChart.__table__.update().where(DashboardChart.id == chart_id).values(**update_data)
        )
        await db.commit()
    return {"status": "updated"}


@router.delete("/{dashboard_id}/charts/{chart_id}")
async def delete_chart(dashboard_id: str, chart_id: str, db: DbDep) -> dict:
    result = await db.execute(select(DashboardChart).where(DashboardChart.id == chart_id))
    chart = result.scalar_one_or_none()
    if not chart:
        raise HTTPException(404, "Chart not found")
    await db.execute(sa_delete(DashboardChart).where(DashboardChart.id == chart_id))
    await db.commit()
    return {"status": "deleted"}


@router.get("/{dashboard_id}/charts/{chart_id}/refresh")
async def refresh_chart(dashboard_id: str, chart_id: str, db: DbDep) -> dict:
    """Re-execute chart SQL and return fresh data."""
    result = await db.execute(select(DashboardChart).where(DashboardChart.id == chart_id))
    chart = result.scalar_one_or_none()
    if not chart:
        raise HTTPException(404, "Chart not found")
    data = await execute_query(chart.datasource_id, chart.sql_query)
    return {"chart_id": chart_id, "data": data, "viz_config": chart.viz_config}
