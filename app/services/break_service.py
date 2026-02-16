from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Driver, BreakLog, DriverStatus, DriverExchange, ReplacementReason, RotationAssignment
from app.core.config import settings
from app.services.audit_service import log_action
from app.services.notification_service import create_notification

async def get_break_status(driver: Driver):
    return {
        "break_time_remaining": driver.break_time_remaining,
        "total_break_time_today": driver.total_break_time_today,
        "trips_since_last_break": driver.trips_since_last_break,
        "is_eligible": driver.trips_since_last_break >= settings.MIN_TRIPS_BEFORE_BREAK and driver.break_time_remaining > 0
    }

async def start_break(
    db: AsyncSession,
    driver: Driver
):
    # Validation
    if driver.status != DriverStatus.ACTIVE: # Only active drivers can take break? Or waiting?
        # Assuming ACTIVE means "available to drive" or "waiting at terminal"
        # If ON_TRIP, they can't take break until trip ends.
        pass
    
    if driver.trips_since_last_break < settings.MIN_TRIPS_BEFORE_BREAK:
        raise ValueError("Not enough trips completed to take a break")
    
    if driver.break_time_remaining <= 0:
        raise ValueError("No break time remaining")

    # Start Break
    now = datetime.now()
    driver.status = DriverStatus.ON_BREAK
    driver.break_start_time = now
    driver.current_break_number += 1
    
    # Log
    break_log = BreakLog(
        driver_id=driver.id,
        shift_date=now.date(),
        break_number=driver.current_break_number,
        start_time=now
    )
    db.add(break_log)
    
    # Handle Replacement (Rotation Logic)
    # Ideally, Rotation Service handles this, or we call it here.
    # We need to find the "incoming" driver (D3 usually, or D1/D2 swap)
    # For now, we'll placeholder the replacement logic or just mark the driver as on break.
    # The system needs to know WHO replaces them.
    # This might require complex query to find available D3.
    
    await log_action(db, driver.user_id, "START_BREAK", "Driver", driver.id)
    return break_log

async def end_break(
    db: AsyncSession,
    driver: Driver
):
    if driver.status != DriverStatus.ON_BREAK or not driver.break_start_time:
        raise ValueError("Driver is not on break")
        
    now = datetime.now()
    duration = (now - driver.break_start_time).total_seconds() / 60.0
    
    # Update Driver
    driver.status = DriverStatus.ACTIVE
    driver.break_time_remaining = max(0, driver.break_time_remaining - duration)
    driver.total_break_time_today += duration
    driver.break_start_time = None
    driver.trips_since_last_break = 0 # Reset counter
    
    # Update Log
    # Find the open break log
    stmt = select(BreakLog).where(
        BreakLog.driver_id == driver.id,
        BreakLog.end_time == None
    ).order_by(BreakLog.start_time.desc())
    result = await db.execute(stmt)
    break_log = result.scalars().first()
    
    if break_log:
        break_log.end_time = now
        break_log.duration_minutes = duration
    
    await log_action(db, driver.user_id, "END_BREAK", "Driver", driver.id)
    return driver
