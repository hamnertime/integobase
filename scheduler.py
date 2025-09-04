import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from .database import SessionLocal
from .data_pullers import pull_freshservice, pull_datto, pull_ticket_details

scheduler = AsyncIOScheduler()

async def run_all_syncs_once():
    """
    An async function to run all data pullers once for debugging
    and initial data population on startup. It now uses asyncio.to_thread
    to prevent blocking the main event loop.
    """
    print("--- RUNNING INITIAL DATA SYNC ON STARTUP ---")
    db: Session = SessionLocal()
    try:
        await asyncio.to_thread(pull_freshservice.sync_freshservice_data, db)
        await asyncio.to_thread(pull_datto.sync_datto_data, db)
        await asyncio.to_thread(pull_ticket_details.sync_ticket_details_data, db)
    except Exception as e:
        print(f"!!! An error occurred during initial data sync: {e}")
    finally:
        db.close()
    print("--- INITIAL DATA SYNC FINISHED ---")


async def run_freshservice_sync():
    print("SCHEDULER: Running Freshservice sync job...")
    db: Session = SessionLocal()
    try:
        # The sync function is synchronous, so run it in a thread.
        await asyncio.to_thread(pull_freshservice.sync_freshservice_data, db)
    finally:
        db.close()
    print("SCHEDULER: Freshservice sync job finished.")

async def run_datto_sync():
    print("SCHEDULER: Running Datto RMM sync job...")
    db: Session = SessionLocal()
    try:
        # The sync function is synchronous, so run it in a thread.
        await asyncio.to_thread(pull_datto.sync_datto_data, db)
    finally:
        db.close()
    print("SCHEDULER: Datto RMM sync job finished.")

async def run_tickets_sync():
    print("SCHEDULER: Running Ticket Details sync job...")
    db: Session = SessionLocal()
    try:
        # The sync function is synchronous, so run it in a thread.
        await asyncio.to_thread(pull_ticket_details.sync_ticket_details_data, db)
    finally:
        db.close()
    print("SCHEDULER: Ticket Details sync job finished.")


def trigger_job_run(job_id: int):
    """
    Triggers a specific job to run immediately by setting its next run time to now.
    """
    if scheduler.running:
        scheduler.modify_job(str(job_id), next_run_time=datetime.now())


def setup_scheduler():
    """
    Configures and starts the background scheduler jobs.
    Reads job configurations from the database.
    """
    db = SessionLocal()
    try:
        # Using text() to mark the string as a SQL expression
        query = text("SELECT * FROM scheduler_jobs WHERE enabled = TRUE")
        jobs = db.execute(query).fetchall()

        for job in jobs:
            job_func = None
            if 'freshservice' in job.script_path:
                job_func = run_freshservice_sync
            elif 'datto' in job.script_path:
                job_func = run_datto_sync
            elif 'ticket_details' in job.script_path:
                job_func = run_tickets_sync

            if job_func:
                scheduler.add_job(job_func, 'interval', minutes=job.interval_minutes, id=str(job.id))

        if jobs:
            scheduler.start()
            print("Scheduler started with configured jobs.")
    finally:
        db.close()
