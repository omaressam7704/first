from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON, Text, DateTime, Date, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base

# --- ENUMS ---

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    DRIVER = "DRIVER"

class DriverStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ON_TRIP = "ON_TRIP"
    ON_BREAK = "ON_BREAK"
    OFF_DUTY = "OFF_DUTY"

class VehicleStatus(str, Enum):
    FREE = "FREE"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    MAINTENANCE = "MAINTENANCE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"

class TripStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class TripDirection(str, Enum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"

class MaintenanceStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

class MaintenanceType(str, Enum):
    REGULAR = "REGULAR"
    EMERGENCY = "EMERGENCY"

class ShiftType(str, Enum):
    MORNING = "MORNING"
    EVENING = "EVENING"

class RotationPosition(str, Enum):
    DRIVER_1 = "DRIVER_1"
    DRIVER_2 = "DRIVER_2"
    DRIVER_3 = "DRIVER_3"

class ReplacementReason(str, Enum):
    BREAK = "BREAK"
    EMERGENCY_CROWDING = "EMERGENCY_CROWDING"
    EMERGENCY_BREAKDOWN = "EMERGENCY_BREAKDOWN"
    NO_SHOW = "NO_SHOW"

# --- MODELS ---

class Garage(Base):
    __tablename__ = "garages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    total_capacity: Mapped[int] = mapped_column(Integer, default=50)
    current_occupancy: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String, nullable=False) # Store Enum as String
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    driver: Mapped[Optional["Driver"]] = relationship("Driver", back_populates="user", uselist=False)
    # Notifications handled by back_populates in Notification model

class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    license_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    license_expiry: Mapped[Optional[date]] = mapped_column(Date)
    garage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("garages.id"))
    status: Mapped[DriverStatus] = mapped_column(String, default=DriverStatus.ACTIVE)
    current_vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id"))
    current_route_id: Mapped[Optional[int]] = mapped_column(ForeignKey("routes.id"))
    total_trips_today: Mapped[int] = mapped_column(Integer, default=0)
    total_trips_all_time: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    
    # Break Management
    break_time_remaining: Mapped[float] = mapped_column(Float, default=60.0)
    total_break_time_today: Mapped[float] = mapped_column(Float, default=0.0)
    break_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    trips_since_last_break: Mapped[int] = mapped_column(Integer, default=0)
    current_break_number: Mapped[int] = mapped_column(Integer, default=0)
    min_break_duration: Mapped[float] = mapped_column(Float, default=10.0)
    max_break_duration: Mapped[float] = mapped_column(Float, default=30.0)
    
    # Shift Info
    current_shift: Mapped[Optional[ShiftType]] = mapped_column(String)
    shift_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    shift_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="driver")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", foreign_keys=[current_vehicle_id], back_populates="current_driver")
    # Route relationship needs logical handling (Driver is on Route X)
    # Circular imports might happen if not careful with strings
    trips: Mapped[List["Trip"]] = relationship("Trip", back_populates="driver")
    
class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[VehicleStatus] = mapped_column(String, default=VehicleStatus.FREE)
    garage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("garages.id"))
    current_latitude: Mapped[Optional[float]] = mapped_column(Float)
    current_longitude: Mapped[Optional[float]] = mapped_column(Float)
    mileage: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_level: Mapped[float] = mapped_column(Float, default=100.0)
    last_maintenance_date: Mapped[Optional[date]] = mapped_column(Date)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    current_driver: Mapped[Optional["Driver"]] = relationship("Driver", foreign_keys="Driver.current_vehicle_id", back_populates="vehicle")
    trips: Mapped[List["Trip"]] = relationship("Trip", back_populates="vehicle")
    gps_logs: Mapped[List["GPSTracking"]] = relationship("GPSTracking", back_populates="vehicle")
    maintenance_requests: Mapped[List["MaintenanceRequest"]] = relationship("MaintenanceRequest", back_populates="vehicle")

class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_location: Mapped[str] = mapped_column(String(255), nullable=False)
    end_location: Mapped[str] = mapped_column(String(255), nullable=False)
    distance_km: Mapped[Optional[float]] = mapped_column(Float)
    estimated_time_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    fare: Mapped[float] = mapped_column(Float, default=0.0)
    turnaround_time_minutes: Mapped[float] = mapped_column(Float, default=10.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    stops: Mapped[List["RouteStop"]] = relationship("RouteStop", back_populates="route")
    trips: Mapped[List["Trip"]] = relationship("Trip", back_populates="route")
    rotations: Mapped[List["RotationAssignment"]] = relationship("RotationAssignment", back_populates="route")

class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = (
        UniqueConstraint('route_id', 'sequence_order', name='uix_route_stop_order'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    stop_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    dwell_time_minutes: Mapped[float] = mapped_column(Float, default=2.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    route: Mapped["Route"] = relationship("Route", back_populates="stops")

class RotationAssignment(Base):
    __tablename__ = "rotation_assignments"
    __table_args__ = (
        UniqueConstraint('route_id', 'shift_type', 'position', 'shift_date', name='uix_rotation_assignment'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    shift_type: Mapped[ShiftType] = mapped_column(String, nullable=False)
    position: Mapped[RotationPosition] = mapped_column(String, nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    shift_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    route: Mapped["Route"] = relationship("Route", back_populates="rotations")
    driver: Mapped["Driver"] = relationship("Driver")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle")

class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    rotation_assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rotation_assignments.id"))
    direction: Mapped[TripDirection] = mapped_column(String, nullable=False)
    status: Mapped[TripStatus] = mapped_column(String, default=TripStatus.SCHEDULED)
    trip_number: Mapped[Optional[str]] = mapped_column(String(50)) # e.g. RAM-0600-O
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Crowding
    passenger_count: Mapped[int] = mapped_column(Integer, default=0)
    crowding_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_crowded: Mapped[bool] = mapped_column(Boolean, default=False)
    driver_crowding_report: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Financial
    fare_collected: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Flags
    is_extra_dispatch: Mapped[bool] = mapped_column(Boolean, default=False)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    driver: Mapped["Driver"] = relationship("Driver", back_populates="trips")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="trips")
    route: Mapped["Route"] = relationship("Route", back_populates="trips")
    tickets: Mapped[List["Ticket"]] = relationship("Ticket", back_populates="trip")

class GPSTracking(Base):
    __tablename__ = "gps_tracking"
    __table_args__ = (
        Index('idx_gps_vehicle_time', 'vehicle_id', 'recorded_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    trip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trips.id"))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float] = mapped_column(Float, default=0.0)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="gps_logs")

class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    type: Mapped[MaintenanceType] = mapped_column(String, nullable=False)
    status: Mapped[MaintenanceStatus] = mapped_column(String, default=MaintenanceStatus.PENDING)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float)
    actual_cost: Mapped[Optional[float]] = mapped_column(Float)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date)
    completed_date: Mapped[Optional[date]] = mapped_column(Date)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="maintenance_requests")
    requested_by: Mapped["User"] = relationship("User", foreign_keys=[requested_by_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_id])

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50)) # EMERGENCY, SCHEDULE, etc.
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User")

class TripTicketStatus(str, Enum):
    ISSUED = "ISSUED"
    USED = "USED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False)
    passenger_name: Mapped[Optional[str]] = mapped_column(String(255))
    seat_number: Mapped[Optional[str]] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[TripTicketStatus] = mapped_column(String, default=TripTicketStatus.ISSUED)
    purchase_time: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    validation_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    trip: Mapped["Trip"] = relationship("Trip", back_populates="tickets")

# Add back_populates to Trip model
# (This part needs to be applied to the Trip class separately or I can try to do it here if I am careful, 
# but Trip is already defined. I will use a separate edit for Trip to be safe/clean)

class DriverExchange(Base):
    __tablename__ = "driver_exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rotation_assignment_id: Mapped[int] = mapped_column(ForeignKey("rotation_assignments.id"), nullable=False)
    outgoing_driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    incoming_driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    reason: Mapped[ReplacementReason] = mapped_column(String, nullable=False)
    exchange_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    return_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    trip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trips.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class BreakLog(Base):
    __tablename__ = "break_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    break_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_minutes: Mapped[Optional[float]] = mapped_column(Float)
    replaced_by_driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_trips: Mapped[int] = mapped_column(Integer, default=0)
    completed_trips: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_trips: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    total_passengers: Mapped[int] = mapped_column(Integer, default=0)
    avg_crowding_score: Mapped[float] = mapped_column(Float, default=0.0)
    on_time_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    total_maintenance_requests: Mapped[int] = mapped_column(Integer, default=0)
    active_vehicles: Mapped[int] = mapped_column(Integer, default=0)
    active_drivers: Mapped[int] = mapped_column(Integer, default=0)
    extra_dispatches: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
