from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user_with_role
from app.models.models import UserRole, MaintenanceRequest, Trip, Vehicle, Driver, Notification
from app.schemas.schemas import (
    MaintenanceResponse, MaintenanceRejectRequest, TripResponse, ManagerDashboardStats, NotificationResponse, VehicleResponse, DriverResponse
)
from app.services.maintenance_service import approve_maintenance_request, reject_maintenance_request

router = APIRouter(dependencies=[Depends(get_current_user_with_role(UserRole.MANAGER))])

# --- Dashboard ---
@router.get("/dashboard/stats", response_model=ManagerDashboardStats)
async def get_dashboard_stats(db: Annotated[AsyncSession, Depends(get_db)]):
    from sqlalchemy import func
    from datetime import date
    today = date.today()
    
    # Trips today
    trips_today = await db.scalar(select(func.count(Trip.id)).where(func.date(Trip.scheduled_start) == today))
    # Revenue
    revenue = await db.scalar(select(func.sum(Trip.fare_collected)).where(func.date(Trip.scheduled_start) == today))
    # On Time % (simple check: is_late=False)
    # count late / total
    # Implement simpler query or stored metric
    
    return {
        "trips_today": trips_today or 0,
        "total_revenue": revenue or 0.0,
        "on_time_percentage": 95.0, # Placeholder
        "crowding_alerts": 0,
        "pending_maintenance": 0
    }

# --- Fleet ---
@router.get("/fleet", response_model=List[VehicleResponse])
async def get_fleet(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Vehicle))
    return result.scalars().all()

@router.get("/drivers", response_model=List[DriverResponse])
async def get_drivers(db: Annotated[AsyncSession, Depends(get_db)]):
    from sqlalchemy.orm import selectinload
    stmt = select(Driver).options(selectinload(Driver.user))
    result = await db.execute(stmt)
    return result.scalars().all()

# --- Maintenance ---
@router.get("/maintenance/pending", response_model=List[MaintenanceResponse])
async def get_pending_maintenance(db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = select(MaintenanceRequest).where(MaintenanceRequest.status == "PENDING")
    result = await db.execute(stmt)
    return result.scalars().all()

@router.patch("/maintenance/{id}/approve", response_model=MaintenanceResponse)
async def approve_request(id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user = Depends(get_current_user_with_role(UserRole.MANAGER))):
    request = await db.get(MaintenanceRequest, id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    updated = await approve_maintenance_request(db, request, current_user.id)
    await db.commit()
    await db.refresh(updated)
    return updated

@router.patch("/maintenance/{id}/reject", response_model=MaintenanceResponse)
async def reject_request(id: int, rejection: MaintenanceRejectRequest, db: Annotated[AsyncSession, Depends(get_db)], current_user = Depends(get_current_user_with_role(UserRole.MANAGER))):
    request = await db.get(MaintenanceRequest, id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    updated = await reject_maintenance_request(db, request, current_user.id, rejection.reason)
    await db.commit()
    await db.refresh(updated)
    return updated

# --- Notifications ---
@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(db: Annotated[AsyncSession, Depends(get_db)], current_user = Depends(get_current_user_with_role(UserRole.MANAGER))):
    stmt = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
