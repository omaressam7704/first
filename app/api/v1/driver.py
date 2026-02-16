from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user_with_role
from app.models.models import UserRole, Driver, Trip, BreakLog
from app.schemas.schemas import DriverResponse, TripResponse, BreakLogResponse
from app.services.break_service import start_break, end_break, get_break_status

router = APIRouter(dependencies=[Depends(get_current_user_with_role(UserRole.DRIVER))])

@router.get("/me", response_model=DriverResponse)
async def get_my_driver_profile(db: Annotated[AsyncSession, Depends(get_db)], current_user = Depends(get_current_user_with_role(UserRole.DRIVER))):
    stmt = select(Driver).where(Driver.user_id == current_user.id)
    driver = (await db.execute(stmt)).scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    
    # Populate user data manually if needed or rely on loading
    driver.user = current_user
    return driver

@router.get("/me/trips", response_model=List[TripResponse])
async def get_my_trips(db: Annotated[AsyncSession, Depends(get_db)], current_user = Depends(get_current_user_with_role(UserRole.DRIVER))):
    # Get driver id
    driver_res = await db.execute(select(Driver).where(Driver.user_id == current_user.id))
    driver = driver_res.scalar_one()
    
    stmt = select(Trip).where(Trip.driver_id == driver.id).order_by(Trip.scheduled_start.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/me/trips/{trip_id}", response_model=TripResponse)
async def get_my_trip_details(
    trip_id: int, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user = Depends(get_current_user_with_role(UserRole.DRIVER))
):
    # Verify owner
    driver_res = await db.execute(select(Driver).where(Driver.user_id == current_user.id))
    driver = driver_res.scalar_one()
    
    trip = await db.get(Trip, trip_id)
    if not trip or trip.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Trip not found or not assigned to you")
    
    # Eager load relations for response
    from sqlalchemy.orm import selectinload
    stmt = select(Trip).options(
        selectinload(Trip.route),
        selectinload(Trip.vehicle),
        selectinload(Trip.driver),
        selectinload(Trip.tickets)
    ).where(Trip.id == trip_id)
    
    return (await db.execute(stmt)).scalar_one()

# --- Break Management ---
@router.post("/me/break/start", response_model=BreakLogResponse)
async def request_start_break(db: Annotated[AsyncSession, Depends(get_db)], current_user = Depends(get_current_user_with_role(UserRole.DRIVER))):
    driver = (await db.execute(select(Driver).where(Driver.user_id == current_user.id))).scalar_one()
    try:
        log = await start_break(db, driver)
        await db.commit()
        await db.refresh(log)
        return log
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/me/break/end", response_model=DriverResponse)
async def request_end_break(db: Annotated[AsyncSession, Depends(get_db)], current_user = Depends(get_current_user_with_role(UserRole.DRIVER))):
    driver = (await db.execute(select(Driver).where(Driver.user_id == current_user.id))).scalar_one()
    try:
        updated_driver = await end_break(db, driver)
        updated_driver.user = current_user
        await db.commit()
        return updated_driver
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
