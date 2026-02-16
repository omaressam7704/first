from datetime import datetime, date, timedelta
from typing import List, Annotated
from sqlalchemy import select, func, cast, Date, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Trip, RotationAssignment, Route, Driver, Vehicle, DriverExchange, Ticket, GPSTracking, TripStatus, TripDirection, DriverStatus, VehicleStatus, TripTicketStatus, ShiftType, RotationPosition
from sqlalchemy.orm import selectinload

async def generate_daily_schedule(
    db: AsyncSession,
    target_date: date,
    regenerate: bool = False
):
    # 1. Check existing trips
    existing_trips_stmt = select(func.count(Trip.id)).where(cast(Trip.scheduled_start, Date) == target_date)
    existing_trips_count = (await db.execute(existing_trips_stmt)).scalar()

    if existing_trips_count > 0 and not regenerate:
        return []

    if regenerate:
        try:
            # 1. Gather all ID sets to avoid missed orphans
            assign_stmt = select(RotationAssignment.id).where(RotationAssignment.shift_date == target_date)
            assign_result = await db.execute(assign_stmt)
            assignment_ids = assign_result.scalars().all()
            
            trip_stmt = select(Trip.id).where(cast(Trip.scheduled_start, Date) == target_date)
            trip_result = await db.execute(trip_stmt)
            trip_ids = trip_result.scalars().all()
            
            # 2. Delete Child Records
            if trip_ids:
                await db.execute(delete(Ticket).where(Ticket.trip_id.in_(trip_ids)))
                await db.execute(delete(GPSTracking).where(GPSTracking.trip_id.in_(trip_ids)))
                
            if assignment_ids:
                await db.execute(delete(DriverExchange).where(DriverExchange.rotation_assignment_id.in_(assignment_ids)))

            # 3. Delete Main Records
            if trip_ids:
                await db.execute(delete(Trip).where(Trip.id.in_(trip_ids)))
                
            if assignment_ids:
                await db.execute(delete(RotationAssignment).where(RotationAssignment.id.in_(assignment_ids)))
            
            await db.flush()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    # 2. Get all active routes
    routes_result = await db.execute(select(Route).where(Route.is_active == True))
    routes = routes_result.scalars().all()
    
    # 3. Get all active drivers and vehicles
    drivers_res = await db.execute(select(Driver).where(Driver.status != DriverStatus.OFF_DUTY))
    all_drivers = drivers_res.scalars().all()
    
    vehicles_res = await db.execute(select(Vehicle).where(Vehicle.status != VehicleStatus.OUT_OF_SERVICE)) 
    all_vehicles = vehicles_res.scalars().all()

    if not all_drivers or not all_vehicles:
        return []

    generated_trips = []
    
    # Resource counters to distribute work
    driver_idx = 0
    vehicle_idx = 0

    for route in routes:
        # Filter resources for this route or just pick from pool
        route_drivers = all_drivers[driver_idx:driver_idx+3]
        route_vehicles = all_vehicles[vehicle_idx:vehicle_idx+2]
        
        if len(route_drivers) < 2 or len(route_vehicles) < 2:
            continue
            
        driver_idx = (driver_idx + 3) % len(all_drivers)
        vehicle_idx = (vehicle_idx + 2) % len(all_vehicles)

        assignments = []
        morning_start = datetime.combine(target_date, datetime.strptime("06:00", "%H:%M").time())
        morning_end = datetime.combine(target_date, datetime.strptime("15:00", "%H:%M").time())
        
        for i, (d, v) in enumerate(zip(route_drivers[:2], route_vehicles)):
            assignment = RotationAssignment(
                route_id=route.id,
                driver_id=d.id,
                vehicle_id=v.id,
                shift_date=target_date,
                shift_type=ShiftType.MORNING,
                position=RotationPosition.DRIVER_1 if i == 0 else RotationPosition.DRIVER_2,
                shift_start_time=morning_start,
                shift_end_time=morning_end
            )
            db.add(assignment)
            assignments.append(assignment)
        
        await db.flush() # assignments.id needed

        start_time = datetime.combine(target_date, datetime.strptime("06:00", "%H:%M").time())
        end_time = datetime.combine(target_date, datetime.strptime("14:00", "%H:%M").time())
        current_dt = start_time
        driver_toggle = 0

        while current_dt < end_time:
            active_assignment = assignments[driver_toggle]
            driver_toggle = 1 - driver_toggle

            # OUTBOUND
            trip_out = Trip(
                trip_number=f"{route.name[:3].upper()}-{current_dt.strftime('%H%M')}-O",
                route_id=route.id,
                driver_id=active_assignment.driver_id,
                vehicle_id=active_assignment.vehicle_id,
                scheduled_start=current_dt,
                scheduled_end=current_dt + timedelta(minutes=route.estimated_time_minutes),
                status=TripStatus.SCHEDULED,
                direction=TripDirection.OUTBOUND,
                rotation_assignment_id=active_assignment.id
            )
            db.add(trip_out)
            generated_trips.append(trip_out)
            
            # INBOUND
            return_start = current_dt + timedelta(minutes=route.estimated_time_minutes + route.turnaround_time_minutes)
            if return_start < end_time:
                trip_in = Trip(
                    trip_number=f"{route.name[:3].upper()}-{return_start.strftime('%H%M')}-I",
                    route_id=route.id,
                    driver_id=active_assignment.driver_id,
                    vehicle_id=active_assignment.vehicle_id,
                    scheduled_start=return_start,
                    scheduled_end=return_start + timedelta(minutes=route.estimated_time_minutes),
                    status=TripStatus.SCHEDULED,
                    direction=TripDirection.INBOUND,
                    rotation_assignment_id=active_assignment.id
                )
                db.add(trip_in)
                generated_trips.append(trip_in)
                
            current_dt += timedelta(minutes=60) # Frequency

    await db.commit()
    return generated_trips
