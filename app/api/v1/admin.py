from typing import Annotated, List, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user_with_role
from app.models.models import UserRole, User, Driver, Vehicle, Route, RouteStop, RotationAssignment, MaintenanceRequest, AuditLog, TripDirection
from app.schemas.schemas import (
    UserCreate, UserUpdate, UserResponse, 
    DriverCreate, DriverUpdate, DriverResponse, 
    VehicleCreate, VehicleUpdate, VehicleResponse,
    RouteCreate, RouteUpdate, RouteResponse, 
    RotationAssignmentCreate, RotationAssignmentResponse, 
    AdminDashboardStats, AuditLogResponse,
    UserWithDriverCreate, TicketCreate, TicketResponse, TicketBase
)
from app.core.security import security
from app.services.audit_service import log_action

# Enforce ADMIN role
router = APIRouter(dependencies=[Depends(get_current_user_with_role(UserRole.ADMIN))])

# --- Dashboard ---
@router.get("/dashboard/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(db: Annotated[AsyncSession, Depends(get_db)]):
    # Simplified count queries
    # In real app, might want to optimize or cache
    from sqlalchemy import func
    from app.models.models import Trip, Route
    
    total_vehicles = await db.scalar(select(func.count(Vehicle.id)))
    total_drivers = await db.scalar(select(func.count(Driver.id)))
    total_routes = await db.scalar(select(func.count(Route.id)))
    total_users = await db.scalar(select(func.count(User.id)))
    pending_maintenance = await db.scalar(select(func.count(MaintenanceRequest.id)).where(MaintenanceRequest.status == "PENDING"))
    # Active trips: status=ACTIVE
    active_trips = await db.scalar(select(func.count(Trip.id)).where(Trip.status == "ACTIVE"))
    
    # Calculate trips per route for the chart
    stmt = select(Route.name, func.count(Trip.id)).outerjoin(Trip).group_by(Route.id, Route.name)
    res = await db.execute(stmt)
    trips_per_route = [{"name": row[0], "trips": row[1]} for row in res.all()]
    
    return {
        "total_vehicles": total_vehicles or 0,
        "total_drivers": total_drivers or 0,
        "total_routes": total_routes or 0,
        "total_users": total_users or 0,
        "pending_maintenance": pending_maintenance or 0,
        "active_trips": active_trips or 0,
        "trips_per_route": trips_per_route
    }

# --- Users ---
# --- Users ---
@router.get("/users", response_model=List[UserResponse])
async def read_users(db: Annotated[AsyncSession, Depends(get_db)], skip: int = 0, limit: int = 100):
    result = await db.execute(select(User).order_by(User.id).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/users", response_model=UserResponse)
async def create_user(user_in: UserCreate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    stmt = select(User).where(User.email == user_in.email)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        phone=user_in.phone,
        is_active=user_in.is_active
    )
    db.add(user)
    await db.flush()
    await log_action(db, current_user.id, "CREATE", "User", user.id)
    await db.commit()
    await db.refresh(user)
    return user

@router.put("/users/{id}", response_model=UserResponse)
async def update_user(id: int, user_in: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = security.get_password_hash(update_data.pop("password"))
        
    for key, value in update_data.items():
        setattr(user, key, value)
        
    await log_action(db, current_user.id, "UPDATE", "User", user.id)
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/users/{id}")
async def delete_user(id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Soft delete
    user.is_active = False
    await log_action(db, current_user.id, "DELETE", "User", user.id)
    await db.commit()
    return {"message": "User deactivated"}

@router.post("/users/driver", response_model=DriverResponse)
async def create_user_and_driver(
    composite_in: UserWithDriverCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))
):
    # 1. Check Email
    stmt = select(User).where(User.email == composite_in.user.email)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 2. Check License
    stmt_driver = select(Driver).where(Driver.license_number == composite_in.driver.license_number)
    if (await db.execute(stmt_driver)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="License number already exists")

    # 3. Create User
    user_in = composite_in.user
    user = User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=UserRole.DRIVER, # Enforce Driver role
        phone=user_in.phone,
        is_active=user_in.is_active
    )
    db.add(user)
    await db.flush() # Get user.id
    
    # 4. Create Driver
    driver_in = composite_in.driver
    driver = Driver(
        user_id=user.id,
        license_number=driver_in.license_number,
        license_expiry=driver_in.license_expiry,
        garage_id=driver_in.garage_id,
        status=DriverStatus.ACTIVE
    )
    db.add(driver)
    
    await log_action(db, current_user.id, "CREATE", "User+Driver", user.id)
    await db.commit()
    await db.refresh(driver)
    
    # Eager load user for response
    from sqlalchemy.orm import selectinload
    stmt = select(Driver).options(selectinload(Driver.user)).where(Driver.id == driver.id)
    driver = (await db.execute(stmt)).scalar_one()
    
    return driver

# --- Drivers ---
@router.get("/drivers", response_model=List[DriverResponse])
async def read_drivers(db: Annotated[AsyncSession, Depends(get_db)], skip: int = 0, limit: int = 100):
    from sqlalchemy.orm import selectinload
    stmt = select(Driver).options(selectinload(Driver.user)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/drivers", response_model=DriverResponse)
async def create_driver(driver_in: DriverCreate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    stmt = select(Driver).where(Driver.license_number == driver_in.license_number)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="License number already exists")
    
    driver = Driver(
        user_id=driver_in.user_id,
        license_number=driver_in.license_number,
        license_expiry=driver_in.license_expiry,
        garage_id=driver_in.garage_id,
        status="ACTIVE"
    )
    db.add(driver)
    await db.flush()
    await log_action(db, current_user.id, "CREATE", "Driver", driver.id)
    await db.commit()
    await db.refresh(driver)
    return driver

@router.put("/drivers/{id}", response_model=DriverResponse)
async def update_driver(id: int, driver_in: DriverUpdate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    driver = await db.get(Driver, id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
        
    update_data = driver_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(driver, key, value)
        
    await log_action(db, current_user.id, "UPDATE", "Driver", driver.id)
    await db.commit()
    await db.refresh(driver)
    return driver

@router.delete("/drivers/{id}")
async def delete_driver(id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    driver = await db.get(Driver, id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    driver.status = "OFF_DUTY" # Or some inactive state
    await log_action(db, current_user.id, "DELETE", "Driver", driver.id)
    await db.commit()
    return {"message": "Driver deactivated"}

# --- Vehicles ---
@router.get("/vehicles", response_model=List[VehicleResponse])
async def read_vehicles(db: Annotated[AsyncSession, Depends(get_db)], skip: int = 0, limit: int = 100):
    result = await db.execute(select(Vehicle).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/vehicles", response_model=VehicleResponse)
async def create_vehicle(vehicle_in: VehicleCreate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    # Check if plate already exists
    stmt = select(Vehicle).where(Vehicle.plate_number == vehicle_in.plate_number)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vehicle with this plate number already exists")

    vehicle = Vehicle(**vehicle_in.model_dump())
    db.add(vehicle)
    await db.flush()
    await log_action(db, current_user.id, "CREATE", "Vehicle", vehicle.id)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle

@router.put("/vehicles/{id}", response_model=VehicleResponse)
async def update_vehicle(id: int, vehicle_in: VehicleUpdate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    vehicle = await db.get(Vehicle, id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    update_data = vehicle_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vehicle, key, value)
        
    await log_action(db, current_user.id, "UPDATE", "Vehicle", vehicle.id)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle

@router.delete("/vehicles/{id}")
async def delete_vehicle(id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    vehicle = await db.get(Vehicle, id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    vehicle.status = "OUT_OF_SERVICE"
    await log_action(db, current_user.id, "DELETE", "Vehicle", vehicle.id)
    await db.commit()
    return {"message": "Vehicle marked as Out of Service"}

# --- Routes ---
@router.get("/routes", response_model=List[RouteResponse])
async def read_routes(db: Annotated[AsyncSession, Depends(get_db)]):
    from sqlalchemy.orm import selectinload
    stmt = select(Route).options(selectinload(Route.stops))
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/routes", response_model=RouteResponse)
async def create_route(route_in: RouteCreate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    route_data = route_in.model_dump(exclude={"stops"})
    route = Route(**route_data)
    db.add(route)
    await db.flush()
    
    for stop_in in route_in.stops:
        stop = RouteStop(route_id=route.id, **stop_in.model_dump())
        db.add(stop)
        
    await log_action(db, current_user.id, "CREATE", "Route", route.id)
    await db.commit()
    await db.refresh(route)
    stmt = select(Route).options(selectinload(Route.stops)).where(Route.id == route.id)
    route = (await db.execute(stmt)).scalar_one()
    return route

@router.put("/routes/{id}", response_model=RouteResponse)
async def update_route(id: int, route_in: RouteUpdate, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    route = await db.get(Route, id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    update_data = route_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(route, key, value)
        
    await log_action(db, current_user.id, "UPDATE", "Route", route.id)
    await db.commit()
    
    # Re-fetch for response
    from sqlalchemy.orm import selectinload
    stmt = select(Route).options(selectinload(Route.stops)).where(Route.id == route.id)
    route = (await db.execute(stmt)).scalar_one()
    return route

@router.delete("/routes/{id}")
async def delete_route(id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))):
    route = await db.get(Route, id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    route.is_active = False
    await log_action(db, current_user.id, "DELETE", "Route", route.id)
    await db.commit()
    return {"message": "Route deactivated"}

# --- Rotations ---
@router.post("/rotations", response_model=RotationAssignmentResponse)
async def create_assignment(
    assignment_in: RotationAssignmentCreate, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN))
):
    assignment = RotationAssignment(**assignment_in.model_dump())
    db.add(assignment)
    await log_action(db, current_user.id, "CREATE", "RotationAssignment", 0)
    await db.commit()
    await db.refresh(assignment)
    return assignment

@router.post("/rotations/generate")
async def force_generate_schedule(
    db: Annotated[AsyncSession, Depends(get_db)],
    regenerate: bool = False
):
    from app.services.rotation_service import generate_daily_schedule
    from datetime import date
    try:
        trips = await generate_daily_schedule(db, date.today(), regenerate=regenerate)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Regeneration Failed: {str(e)}")
    
    action = "Regenerated" if regenerate else "Generated"
    if not trips and not regenerate:
        return {"message": "Schedule already exists. Use regenerate=true to overwrite."}
        
    return {"message": f"{action} {len(trips)} trips for today"}

@router.get("/trips/{id}", response_model=dict)
async def get_trip_details(id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    from app.models.models import Trip, Driver, Vehicle, Route
    from sqlalchemy.orm import selectinload
    
    stmt = select(Trip).options(
        selectinload(Trip.route),
        selectinload(Trip.driver).selectinload(Driver.user),
        selectinload(Trip.vehicle),
        selectinload(Trip.tickets)
    ).where(Trip.id == id)
    
    trip = await db.scalar(stmt)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    return {
        "id": trip.id,
        "trip_number": trip.trip_number,
        "status": trip.status,
        "direction": trip.direction,
        "scheduled_start": trip.scheduled_start,
        "scheduled_end": trip.scheduled_end,
        "actual_start": trip.actual_start,
        "actual_end": trip.actual_end,
        "passenger_count": trip.passenger_count,
        "crowding_score": trip.crowding_score,
        "route": {
            "id": trip.route.id,
            "name": trip.route.name,
            "start_location": trip.route.start_location,
            "end_location": trip.route.end_location
        } if trip.route else None,
        "driver": {
            "id": trip.driver.id,
            "full_name": trip.driver.user.full_name if trip.driver and trip.driver.user else "Unknown",
            "rating": trip.driver.rating
        } if trip.driver else None,
        "vehicle": {
            "id": trip.vehicle.id,
            "plate_number": trip.vehicle.plate_number,
            "model": trip.vehicle.model,
            "capacity": trip.vehicle.capacity
        } if trip.vehicle else None,
        "tickets": [
            {
                "id": t.id,
                "passenger": t.passenger_name,
                "seat": t.seat_number,
                "status": t.status,
                "price": t.price
            } for t in trip.tickets
        ]
    }

@router.get("/trips", response_model=List[dict]) # fast simplification: returning dicts or use TripResponse
async def get_trips(db: Annotated[AsyncSession, Depends(get_db)], date_filter: Optional[date] = None):
    from app.models.models import Trip, Route, Driver, Vehicle
    from sqlalchemy.orm import selectinload
    
    target_date = date_filter or date.today()
    # Filter by scheduled_start date component
    # SQLite/Postgres date extraction varies. For now, simplistic range check or just fetching all and filtering?
    # Better: cast(Trip.scheduled_start, Date) == target_date
    from sqlalchemy import cast, Date
    
    stmt = select(Trip).options(
        selectinload(Trip.route),
        selectinload(Trip.driver).selectinload(Driver.user),
        selectinload(Trip.vehicle)
    ).where(cast(Trip.scheduled_start, Date) == target_date).order_by(Trip.scheduled_start)
    
    result = await db.execute(stmt)
    trips = result.scalars().all()
    
    # Manual serialization to include nested names easily without complex schemas
    serialized = []
    for t in trips:
        # Determine logical origin/destination based on direction
        origin = t.route.start_location if t.direction == TripDirection.OUTBOUND else t.route.end_location
        destination = t.route.end_location if t.direction == TripDirection.OUTBOUND else t.route.start_location
        
        serialized.append({
            "id": t.id,
            "trip_number": t.trip_number,
            "status": t.status,
            "direction": t.direction,
            "origin": origin,
            "destination": destination,
            "start_time": t.scheduled_start,
            "end_time": t.scheduled_end,
            "route_name": t.route.name if t.route else "Unknown",
            "driver_name": t.driver.user.full_name if t.driver and t.driver.user else "Unknown",
            "vehicle_plate": t.vehicle.plate_number if t.vehicle else "Unknown"
        })
    return serialized

# --- Audit Logs ---
@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def read_audit_logs(db: Annotated[AsyncSession, Depends(get_db)], skip: int = 0, limit: int = 100):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()

# --- Tickets ---
@router.post("/tickets", response_model=TicketResponse)
async def create_ticket(
    ticket_in: TicketCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user_with_role(UserRole.ADMIN, UserRole.DRIVER))
):
    from app.models.models import Ticket, Trip, Driver
    from sqlalchemy import func

    # 1. Get Trip and Vehicle Capacity
    trip = await db.get(Trip, ticket_in.trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # 2. Ownership check if Driver
    if current_user.role == UserRole.DRIVER:
        driver_res = await db.execute(select(Driver).where(Driver.user_id == current_user.id))
        driver = driver_res.scalar_one()
        if trip.driver_id != driver.id:
            raise HTTPException(status_code=403, detail="Not authorized to issue tickets for this trip")
    
    # Lazy load vehicle if not present (though usually trip.vehicle_id is enough)
    # We need capacity. Let's assume Vehicle model has 'capacity' field. 
    # If not, we'll need to fetch it or default to a standard bus size (e.g. 50).
    # Let's check Vehicle model first. 
    # For now, let's fetch the vehicle to be sure.
    vehicle = await db.get(Vehicle, trip.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=400, detail="Trip has no assigned vehicle")
    
    bus_capacity = vehicle.capacity if hasattr(vehicle, 'capacity') else 50 # Default fallback
    
    # 2. Check Capacity
    count_stmt = select(func.count(Ticket.id)).where(Ticket.trip_id == ticket_in.trip_id)
    current_count = await db.scalar(count_stmt)
    
    if current_count >= bus_capacity:
        raise HTTPException(status_code=400, detail=f"Bus is full! Capacity: {bus_capacity}")
        
    # 3. Check Seat Availability
    seat_stmt = select(Ticket).where(
        Ticket.trip_id == ticket_in.trip_id,
        Ticket.seat_number == ticket_in.seat_number
    )
    if (await db.execute(seat_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Seat {ticket_in.seat_number} is already taken")

    ticket = Ticket(**ticket_in.model_dump())
    db.add(ticket)
    
    # Update Trip counters if we had them, but dynamic count is safer.
    
    await db.commit()
    await db.refresh(ticket)
    return ticket

@router.get("/tickets", response_model=List[TicketResponse])
async def read_tickets(db: Annotated[AsyncSession, Depends(get_db)], skip: int = 0, limit: int = 100):
    from app.models.models import Ticket
    result = await db.execute(select(Ticket).offset(skip).limit(limit))
    return result.scalars().all()
