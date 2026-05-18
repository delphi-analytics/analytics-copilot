"""Dashboard CRUD + chart refresh endpoints."""
from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
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


class AddChartRequest(BaseModel):
    title: str
    datasource_id: str
    sql_query: str
    viz_config: dict
    position: dict = {}


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
    return [{"id": d.id, "name": d.name, "created_at": d.created_at.isoformat()} for d in result.scalars()]


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
        "charts": [{"id": c.id, "title": c.title, "viz_config": c.viz_config,
                    "position": c.position, "sql_query": c.sql_query} for c in charts],
    }


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


@router.get("/{dashboard_id}/charts/{chart_id}/refresh")
async def refresh_chart(dashboard_id: str, chart_id: str, db: DbDep) -> dict:
    """Re-execute chart SQL and return fresh data."""
    result = await db.execute(select(DashboardChart).where(DashboardChart.id == chart_id))
    chart = result.scalar_one_or_none()
    if not chart:
        raise HTTPException(404, "Chart not found")
    data = await execute_query(chart.datasource_id, chart.sql_query)
    return {"chart_id": chart_id, "data": data, "viz_config": chart.viz_config}
