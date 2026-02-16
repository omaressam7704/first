from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date

# Service imports - need to handle async session in job
from app.core.database import AsyncSessionLocal
from app.services.rotation_service import generate_daily_schedule

scheduler = AsyncIOScheduler()

async def scheduled_daily_generation():
    # Job function
    today = date.today()
    async with AsyncSessionLocal() as session:
        try:
            await generate_daily_schedule(session, today)
        except Exception as e:
            print(f"Error in scheduled task: {e}")
            # Needs proper logging

def start_scheduler():
    # Add jobs
    # PRD: 05:30 AM daily
    scheduler.add_job(
        scheduled_daily_generation,
        CronTrigger(hour=5, minute=30),
        id="daily_schedule_gen",
        replace_existing=True
    )
    scheduler.start()
