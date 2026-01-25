from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from app.core.database import get_db
from app.core.redis import redis_client
from app.models.user import User
from app.utils.dependencies import get_current_active_user
from pydantic import BaseModel


class MonthlyRevenue(BaseModel):
    month: str
    revenue: float


class AnalyticsResponse(BaseModel):
    total_invoices: int
    total_revenue: float
    paid_invoices: int
    pending_invoices: int
    overdue_invoices: int
    outstanding_amount: float
    average_payment_days: float
    monthly_revenue: List[MonthlyRevenue]
    last_updated: str


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/", response_model=AnalyticsResponse)
async def get_analytics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get analytics and metrics for current user."""
    # Try to get from cache
    cache_key = f"analytics:{current_user.id}"
    cached_metrics = await redis_client.get_json(cache_key)
    
    if cached_metrics:
        return cached_metrics
    
    # If not in cache, trigger analytics worker to update
    # For now, return empty data
    return {
        "total_invoices": 0,
        "total_revenue": 0.0,
        "paid_invoices": 0,
        "pending_invoices": 0,
        "overdue_invoices": 0,
        "outstanding_amount": 0.0,
        "average_payment_days": 0.0,
        "monthly_revenue": [],
        "last_updated": datetime.now().isoformat()
    }