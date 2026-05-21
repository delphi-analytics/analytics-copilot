"""Analytics Router - Query analytics and insights endpoints."""
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.auth.dependencies import require_role
from backend.models.user import User
from backend.database import get_db
from backend.services.query_analytics import (
    get_user_summary,
    get_daily_stats,
    get_popular_queries,
    get_intent_distribution,
    get_admin_summary,
    get_user_activity,
    get_datasource_performance
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
async def get_analytics_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst", "non_tech_user", "team_member"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get query summary for the current user."""
    user_id = current_user.id if current_user else "anonymous"
    return await get_user_summary(db, user_id, days)


@router.get("/daily")
async def get_daily_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst", "non_tech_user", "team_member"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get daily query statistics for the current user."""
    user_id = current_user.id if current_user else "anonymous"
    return await get_daily_stats(db, user_id, days)


@router.get("/popular")
async def get_popular_analytics(
    limit: int = Query(10, ge=1, le=50),
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst", "non_tech_user", "team_member"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get most frequently asked questions for the current user."""
    user_id = current_user.id if current_user else "anonymous"
    return await get_popular_queries(db, user_id, limit)


@router.get("/intents")
async def get_intent_analytics(
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst", "non_tech_user", "team_member"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get distribution of query intent types for the current user."""
    user_id = current_user.id if current_user else "anonymous"
    return await get_intent_distribution(db, user_id)


# Admin-only endpoints
@router.get("/admin/summary")
async def get_admin_analytics_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: Annotated[User, Depends(require_role("admin"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get system-wide query summary (admin only)."""
    return await get_admin_summary(db, days)


@router.get("/admin/users")
async def get_admin_user_activity(
    days: int = Query(30, ge=1, le=365),
    current_user: Annotated[User, Depends(require_role("admin"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get query count by user (admin only)."""
    return await get_user_activity(db, days)


@router.get("/admin/datasources")
async def get_admin_datasource_performance(
    days: int = Query(30, ge=1, le=365),
    current_user: Annotated[User, Depends(require_role("admin"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get query performance by datasource (admin only)."""
    return await get_datasource_performance(db, days)
