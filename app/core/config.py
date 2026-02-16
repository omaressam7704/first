from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Break Management
    BREAK_TIME_PER_SHIFT: int = 60
    MIN_TRIPS_BEFORE_BREAK: int = 1
    MIN_BREAK_DURATION: int = 10
    MAX_BREAK_DURATION: int = 30
    TURNAROUND_BUFFER: int = 10

    # Shift Hours
    MORNING_SHIFT_START: int = 6
    MORNING_SHIFT_END: int = 15
    EVENING_SHIFT_START: int = 15
    EVENING_SHIFT_END: int = 24

    # D3 Stagger
    D3_SHIFT_OFFSET_HOURS: int = 1

    # Crowding
    CROWDING_THRESHOLD: float = 0.85
    EXTRA_DISPATCH_PREP_TIME: int = 10

    # Shift-End Protection
    SHIFT_END_PROTECTION: int = 15

    # Auto-Assignment
    DAILY_SCHEDULE_GENERATION_HOUR: int = 5
    DAILY_SCHEDULE_GENERATION_MINUTE: int = 30

    # Assignment Retry
    ASSIGNMENT_MAX_RETRIES: int = 3
    ASSIGNMENT_RETRY_DELAY: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

settings = Settings()
