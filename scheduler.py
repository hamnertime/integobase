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
    and initial data population on startup. It now uses asyncio.create_task
    to launch the syncs as non-blocking background tasks.
    """
    print("--- LAUNCHING INITIAL DATA SYNC ON STARTUP (NON-BLOCKING) ---")

    async def sync_task(sync_function):
        """Wrapper to manage the database session for each concurrent task."""
        db: Session = SessionLocal()
        try:
            # Run the synchronous DB-heavy function in a separate thread
            await asyncio.to_thread(sync_function, db)
            print(f"--- Initial sync for {sync_function.__module__} completed successfully. ---")
        except Exception as e:
            print(f"!!! An error occurred during initial background sync for {sync_function.__module__}: {e}")
        finally:
            db.close()

    # Create and start a background task for each data puller
    tasks = [
        asyncio.create_task(sync_task(pull_freshservice.sync_freshservice_data)),
        asyncio.create_task(sync_task(pull_datto.sync_datto_data)),
        asyncio.create_task(sync_task(pull_ticket_details.sync_ticket_details_data))
    ]

    print(f"--- {len(tasks)} sync tasks are running in the background. API is ready. ---")
    # The tasks will continue to run to completion in the background


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
