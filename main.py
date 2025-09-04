#!/usr/bin/env python

import sys
import os
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

# This block is essential for making the script runnable directly.
# It ensures Python can find the 'integobase' package by
# correctly manipulating the system path.
if __name__ == "__main__" and __package__ is None:
    # Get the parent directory (the root of the project, 'integobase/')
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    # Remove the current directory from the path if it exists to prevent
    # Python from looking for 'integobase' inside itself.
    if parent_dir in sys.path:
        sys.path.remove(parent_dir)
    # Add the project root to the path so Python can find 'integobase.scheduler', etc.
    sys.path.insert(0, os.path.dirname(parent_dir))


# --- Imports are now ABSOLUTE and work when run with `./main.py` ---
from integobase.scheduler import setup_scheduler, scheduler, run_all_syncs_once
from integobase.api.endpoints import clients, assets, contacts, knowledge_base, settings
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    print("Starting up Integobase API server...")

    # Run all data pullers once on startup to get fresh data and see debug output
    # FIX: Add 'await' to properly run the coroutine
    await run_all_syncs_once()

    # Now, set up the recurring schedule for future runs
    setup_scheduler()

    yield

    # Code to run on shutdown
    print("Shutting down scheduler...")
    if scheduler.running:
        scheduler.shutdown()
    print("Integobase API server shut down.")


app = FastAPI(
    title="Integobase API",
    description="The central API server for the Integodash ecosystem.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS to allow frontend applications to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers from different modules
app.include_router(clients.router, prefix="/api/v1/clients", tags=["Clients"])
app.include_router(assets.router, prefix="/api/v1/assets", tags=["Assets"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["Contacts"])
app.include_router(knowledge_base.router, prefix="/api/v1/kb", tags=["Knowledge Base"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Integobase API"}


# This block remains the same.
if __name__ == "__main__":
    uvicorn.run("integobase.main:app", host="127.0.0.1", port=8000, reload=True)
