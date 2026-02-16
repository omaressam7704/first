from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth

from app.services.scheduler import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Start Scheduler
    start_scheduler()
    
    yield
    # Shutdown: Dispose engine
    await engine.dispose()

app = FastAPI(
    title="Smart Bus Garage API",
    version="1.1",
    description="API for Smart Bus Garage Management System",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
from app.api.v1 import admin, manager, driver, websocket

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(manager.router, prefix="/api/v1/manager", tags=["Manager"])
app.include_router(driver.router, prefix="/api/v1/driver", tags=["Driver"])
app.include_router(websocket.router, tags=["WebSocket"])

@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "1.1"}
