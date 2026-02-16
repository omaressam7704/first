from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import MaintenanceRequest, MaintenanceType, MaintenanceStatus, Vehicle, VehicleStatus
from app.services.notification_service import create_notification
from app.services.audit_service import log_action

async def create_maintenance_request(
    db: AsyncSession,
    vehicle_id: int,
    user_id: int, # requested_by
    type: MaintenanceType,
    title: str,
    description: Optional[str] = None,
    priority: int = 3
):
    # Auto-approve flow for REGULAR
    status = MaintenanceStatus.PENDING
    if type == MaintenanceType.REGULAR:
        status = MaintenanceStatus.APPROVED
    
    request = MaintenanceRequest(
        vehicle_id=vehicle_id,
        requested_by_id=user_id,
        type=type,
        status=status,
        title=title,
        description=description,
        priority=priority
    )
    db.add(request)
    await db.flush() # get ID

    # If EMERGENCY, notify managers
    if type == MaintenanceType.EMERGENCY:
        # TODO: Ideally fetch all managers and notify them. 
        # For now, simplistic approach or delegate to another service?
        # Let's just create a generic notification for now, targeting no specific user ID yet?
        # Or loop through managers.
        # Since I don't have user logic here easily, I might skip mass notification or do it later.
        # But wait, create_notification requires user_id.
        # I'll rely on the caller or a separate background task for mass notification if strictly needed.
        pass

    await log_action(db, user_id, "CREATE", "MaintenanceRequest", request.id, new_values={"title": title, "type": type})
    return request

async def approve_maintenance_request(
    db: AsyncSession,
    request: MaintenanceRequest,
    manager_id: int
):
    old_status = request.status
    request.status = MaintenanceStatus.APPROVED
    request.approved_by_id = manager_id
    
    # Update vehicle status
    if request.vehicle:
        request.vehicle.status = VehicleStatus.MAINTENANCE
    else:
        # Fetch vehicle if not loaded? usually it is not loaded by default
        vehicle = await db.get(Vehicle, request.vehicle_id)
        if vehicle:
            vehicle.status = VehicleStatus.MAINTENANCE

    await log_action(db, manager_id, "APPROVE", "MaintenanceRequest", request.id, old_values={"status": old_status}, new_values={"status": "APPROVED"})
    
    # Notify requester
    await create_notification(db, request.requested_by_id, "Maintenance Approved", f"Your request '{request.title}' has been approved.", "MAINTENANCE")
    
    return request

async def reject_maintenance_request(
    db: AsyncSession,
    request: MaintenanceRequest,
    manager_id: int,
    reason: str
):
    old_status = request.status
    request.status = MaintenanceStatus.REJECTED
    request.rejection_reason = reason
    request.approved_by_id = manager_id # actively rejected by

    await log_action(db, manager_id, "REJECT", "MaintenanceRequest", request.id, old_values={"status": old_status}, new_values={"status": "REJECTED", "reason": reason})

    # Notify requester
    await create_notification(db, request.requested_by_id, "Maintenance Rejected", f"Your request '{request.title}' was rejected: {reason}", "MAINTENANCE")

    return request
