from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Trip, Vehicle, Notification
from app.core.config import settings
from app.services.notification_service import create_notification

async def check_crowding(
    db: AsyncSession,
    trip: Trip,
    vehicle_capacity: int
):
    if not vehicle_capacity:
        return

    score = trip.passenger_count / vehicle_capacity
    trip.crowding_score = score
    
    if score >= settings.CROWDING_THRESHOLD and not trip.is_crowded: # Prevent duplicate alerts?
        trip.is_crowded = True
        
        # Notify Managers
        # Similar issue as maintenance: need to broadcast to managers.
        # Implementation note: In a real system, we'd have a helper `notify_role(role, ...)`
        # For now, we update the state. The WebSocket broadcast might handle role-based subscriptions.
        pass
    
    return trip

async def report_crowding(
    db: AsyncSession,
    trip: Trip,
    driver_id: int
):
    trip.driver_crowding_report = True
    trip.is_crowded = True # Manual override implies crowded
    
    # Notify
    # await notify_managers(...)
    
    return trip
