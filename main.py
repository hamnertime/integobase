#!/usr/bin/env python

import sys
import os
import uvicorn

# This block is still necessary. It allows Python to find the "integobase" package.
if __name__ == "__main__" and __package__ is None:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)


# --- Key Change: Imports are now ABSOLUTE ---
from fastapi import FastAPI
from contextlib import asynccontextmanager
from integobase.scheduler import setup_scheduler, scheduler, run_all_syncs_once
from integobase.api.endpoints import clients, assets, contacts, knowledge_base, settings
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    print("Starting up Integobase API server...")

    # Run all data pullers once on startup to get fresh data and see debug output
    run_all_syncs_once()

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
