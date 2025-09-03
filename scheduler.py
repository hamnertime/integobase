from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from .database import SessionLocal
from .data_pullers import pull_freshservice, pull_datto, pull_ticket_details

scheduler = AsyncIOScheduler()

async def run_freshservice_sync():
    print("SCHEDULER: Running Freshservice sync job...")
    db: Session = SessionLocal()
    try:
        await pull_freshservice.sync_freshservice_data(db)
    finally:
        db.close()
    print("SCHEDULER: Freshservice sync job finished.")

async def run_datto_sync():
    print("SCHEDULER: Running Datto RMM sync job...")
    db: Session = SessionLocal()
    try:
        await pull_datto.sync_datto_data(db)
    finally:
        db.close()
    print("SCHEDULER: Datto RMM sync job finished.")

async def run_tickets_sync():
    print("SCHEDULER: Running Ticket Details sync job...")
    db: Session = SessionLocal()
    try:
        await pull_ticket_details.sync_ticket_details(db)
    finally:
        db.close()
    print("SCHEDULER: Ticket Details sync job finished.")


def setup_scheduler():
    """
    Configures and starts the background scheduler jobs.
    Reads job configurations from the database.
    """
    db = SessionLocal()
    try:
        jobs = db.execute("SELECT * FROM scheduler_jobs WHERE enabled = TRUE").fetchall()
        for job in jobs:
            if 'freshservice' in job.script_path:
                scheduler.add_job(run_freshservice_sync, 'interval', minutes=job.interval_minutes, id=str(job.id))
            elif 'datto' in job.script_path:
                scheduler.add_job(run_datto_sync, 'interval', minutes=job.interval_minutes, id=str(job.id))
            elif 'ticket_details' in job.script_path:
                scheduler.add_job(run_tickets_sync, 'interval', minutes=job.interval_minutes, id=str(job.id))
        if jobs:
            scheduler.start()
            print("Scheduler started with configured jobs.")
    finally:
        db.close()
