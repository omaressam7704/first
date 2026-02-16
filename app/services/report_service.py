from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Trip, DailyReport, Driver, Vehicle
from app.schemas.schemas import DailyReportResponse

async def generate_daily_report(
    db: AsyncSession,
    report_date: date
):
    # Aggregation query
    stmt = select(
        func.count(Trip.id).label("total"),
        func.sum(func.cast(Trip.status == "COMPLETED", int)).label("completed"),
        func.sum(func.cast(Trip.status == "CANCELLED", int)).label("cancelled"),
        func.sum(Trip.fare_collected).label("revenue"),
        func.sum(Trip.passenger_count).label("passengers"),
        func.avg(Trip.crowding_score).label("avg_crowding"),
        func.avg(func.cast(Trip.is_late == False, float)).label("on_time")
    ).where(func.date(Trip.scheduled_start) == report_date)
    
    result = await db.execute(stmt)
    stats = result.first()
    
    # Update or Create DailyReport
    # Check if exists
    existing = await db.execute(select(DailyReport).where(DailyReport.report_date == report_date))
    report = existing.scalar_one_or_none()
    
    if not report:
        report = DailyReport(report_date=report_date)
        db.add(report)
    
    if stats:
        report.total_trips = stats.total or 0
        report.completed_trips = stats.completed or 0
        report.cancelled_trips = stats.cancelled or 0
        report.total_revenue = stats.revenue or 0.0
        report.total_passengers = stats.passengers or 0
        report.avg_crowding_score = stats.avg_crowding or 0.0
        report.on_time_percentage = (stats.on_time or 0.0) * 100
        
    await db.commit()
    return report

async def get_dynamic_report(
    db: AsyncSession,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    driver_id: Optional[int] = None,
    route_id: Optional[int] = None
):
    query = select(Trip).order_by(Trip.scheduled_start.desc())
    
    if start_date:
        query = query.where(func.date(Trip.scheduled_start) >= start_date)
    if end_date:
        query = query.where(func.date(Trip.scheduled_start) <= end_date)
    if driver_id:
        query = query.where(Trip.driver_id == driver_id)
    if route_id:
        query = query.where(Trip.route_id == route_id)
        
    result = await db.execute(query)
    trips = result.scalars().all()
    
    # Calculate summary
    total_revenue = sum(t.fare_collected for t in trips)
    total_trips = len(trips)
    
    return {
        "summary": {
            "total_trips": total_trips,
            "total_revenue": total_revenue
        },
        "trips": trips
    }
