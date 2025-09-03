from fastapi import FastAPI
from contextlib import asynccontextmanager
from .scheduler import setup_scheduler, scheduler
from .api.endpoints import clients, assets, contacts, knowledge_base, settings
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    print("Starting up Integobase API server...")
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

