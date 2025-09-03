from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# Create the SQLAlchemy engine for connecting to the PostgreSQL database
engine = create_engine(settings.DATABASE_URL)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative class definitions
Base = declarative_base()

def get_db():
    """
    Dependency function to get a database session.
    This will be used in API endpoints to interact with the database.
    It ensures the session is properly closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
