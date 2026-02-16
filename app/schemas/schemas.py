from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.models.models import (
    UserRole, DriverStatus, VehicleStatus, TripStatus, TripDirection,
    MaintenanceStatus, MaintenanceType, ShiftType, RotationPosition, ReplacementReason,
    TripTicketStatus
)

# --- Shared Config ---
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# --- Auth & User ---
class UserBase(BaseSchema):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseSchema):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

class Token(BaseSchema):
    access_token: str
    token_type: str

class TokenData(BaseSchema):
    email: Optional[str] = None

class LoginRequest(BaseSchema):
    username: str # OAuth2 compatible (email)
    password: str

# --- Driver ---
class DriverBase(BaseSchema):
    license_number: str
    license_expiry: Optional[date] = None
    garage_id: Optional[int] = None

class DriverCreate(DriverBase):
    user_id: Optional[int] = None # Can be passed or inferred
    user: Optional[UserCreate] = None # For nested creation

class DriverUpdate(BaseSchema):
    license_number: Optional[str] = None
    license_expiry: Optional[date] = None
    status: Optional[DriverStatus] = None
    current_vehicle_id: Optional[int] = None
    current_route_id: Optional[int] = None

class DriverResponse(DriverBase):
    id: int
    user_id: int
    user: Optional[UserResponse] = None
    status: DriverStatus
    current_vehicle_id: Optional[int]
    current_route_id: Optional[int]
    total_trips_today: int
    total_trips_all_time: int
    rating: float
    break_time_remaining: float
    total_break_time_today: float
    trips_since_last_break: int
    current_shift: Optional[ShiftType]
    created_at: datetime
    updated_at: datetime

# --- Vehicle ---
class VehicleBase(BaseSchema):
    plate_number: str
    model: str
    year: Optional[int] = None
    capacity: int = 50
    garage_id: Optional[int] = None

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseSchema):
    status: Optional[VehicleStatus] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    mileage: Optional[float] = None
    fuel_level: Optional[float] = None

class VehicleResponse(VehicleBase):
    id: int
    status: VehicleStatus
    current_latitude: Optional[float]
    current_longitude: Optional[float]
    mileage: float
    fuel_level: float
    last_maintenance_date: Optional[date]
    created_at: datetime
    updated_at: datetime

# --- Route & Stops ---
class RouteStopBase(BaseSchema):
    stop_name: str
    sequence_order: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    dwell_time_minutes: float = 2.0

class RouteStopCreate(RouteStopBase):
    pass

class RouteStopResponse(RouteStopBase):
    id: int
    route_id: int

class RouteBase(BaseSchema):
    name: str
    start_location: str
    end_location: str
    distance_km: Optional[float] = None
    estimated_time_minutes: float
    fare: float = 0.0
    turnaround_time_minutes: float = 10.0
    is_active: bool = True

class RouteCreate(RouteBase):
    stops: List[RouteStopCreate] = []

class RouteUpdate(BaseSchema):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class RouteResponse(RouteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    stops: List[RouteStopResponse] = []

# --- Rotation ---
class RotationAssignmentBase(BaseSchema):
    route_id: int
    driver_id: int
    vehicle_id: int
    shift_type: ShiftType
    position: RotationPosition
    shift_date: date
    shift_start_time: datetime
    shift_end_time: datetime

class RotationAssignmentCreate(RotationAssignmentBase):
    pass

class RotationAssignmentResponse(RotationAssignmentBase):
    id: int
    is_active: bool
    created_at: datetime
    # Nested minimal responses if needed
    driver_name: Optional[str] = None
    vehicle_plate: Optional[str] = None
    route_name: Optional[str] = None

class RotationOverrideRequest(BaseSchema):
    driver_id: int
    vehicle_id: int
    reason: Optional[str] = None

# --- Trip ---
class TripBase(BaseSchema):
    driver_id: int
    vehicle_id: int
    route_id: int
    direction: TripDirection
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None

class TripCreate(TripBase):
    rotation_assignment_id: Optional[int] = None
    trip_number: Optional[int] = None

class TripUpdate(BaseSchema):
    status: Optional[TripStatus] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    passenger_count: Optional[int] = None
    is_crowded: Optional[bool] = None
    notes: Optional[str] = None

class TripResponse(TripBase):
    id: int
    status: TripStatus
    trip_number: Optional[int]
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    passenger_count: int
    crowding_score: float
    is_crowded: bool
    fare_collected: float
    is_late: bool
    created_at: datetime
    updated_at: datetime

# --- GPS ---
class GPSSubmit(BaseSchema):
    latitude: float
    longitude: float
    speed: Optional[float] = 0.0
    heading: Optional[float] = 0.0
    trip_id: Optional[int] = None

class GPSResponse(GPSSubmit):
    id: int
    vehicle_id: int
    recorded_at: datetime

# --- Maintenance ---
class MaintenanceCreate(BaseSchema):
    vehicle_id: int
    type: MaintenanceType
    title: str
    description: Optional[str] = None
    priority: int = 3
    estimated_cost: Optional[float] = None

class MaintenanceResponse(BaseSchema):
    id: int
    vehicle_id: int
    requested_by_id: int
    approved_by_id: Optional[int]
    status: MaintenanceStatus
    type: MaintenanceType
    title: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

class MaintenanceRejectRequest(BaseSchema):
    reason: str

# --- Notification ---
class NotificationBase(BaseSchema):
    title: str
    message: str
    notification_type: str

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime

# --- Exchange ---
class DriverExchangeResponse(BaseSchema):
    id: int
    outgoing_driver_id: int
    incoming_driver_id: int
    reason: ReplacementReason
    exchange_time: datetime
    created_at: datetime

# --- Break ---
class BreakLogResponse(BaseSchema):
    id: int
    driver_id: int
    start_time: datetime
    end_time: Optional[datetime]
    duration_minutes: Optional[float]

# --- Admin Dashboard Stats ---
class AdminDashboardStats(BaseSchema):
    total_vehicles: int
    total_drivers: int
    total_routes: int
    total_users: int
    pending_maintenance: int
    active_trips: int
    trips_per_route: List[Dict[str, Any]] = []

# --- Manager Dashboard Stats ---
class ManagerDashboardStats(BaseSchema):
    trips_today: int
    total_revenue: float
    on_time_percentage: float
    crowding_alerts: int
    pending_maintenance: int

# --- Daily Report ---
class DailyReportResponse(BaseSchema):
    id: int
    report_date: date
    total_trips: int
    completed_trips: int
    total_revenue: float
    on_time_percentage: float
    created_at: datetime

# --- Audit Log ---
class AuditLogResponse(BaseSchema):
    id: int
    user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[int]
    created_at: datetime
    updated_at: datetime

# --- Tickets ---
class TicketBase(BaseSchema):
    trip_id: int
    passenger_name: Optional[str] = None
    seat_number: Optional[str] = None
    price: float
    status: TripTicketStatus = TripTicketStatus.ISSUED

class TicketCreate(TicketBase):
    pass

class TicketResponse(TicketBase):
    id: int
    purchase_time: datetime
    validation_time: Optional[datetime]
    created_at: datetime

# --- Composite Schemas ---
class UserWithDriverCreate(BaseSchema):
    user: UserCreate
    driver: DriverBase
