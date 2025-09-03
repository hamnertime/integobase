from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ... import models, schemas
from ...database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Asset])
def read_assets(
    search: str = "",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve all assets with optional search and pagination.
    """
    query = db.query(models.Asset)
    if search:
        search_term = f"%{search}%"
        query = query.join(models.Company).filter(
            models.Asset.hostname.ilike(search_term) |
            models.Asset.operating_system.ilike(search_term) |
            models.Asset.last_logged_in_user.ilike(search_term) |
            models.Company.name.ilike(search_term)
        )
    assets = query.offset(skip).limit(limit).all()
    return assets

@router.get("/{asset_id}", response_model=schemas.Asset)
def read_asset(asset_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single asset by its ID.
    """
    db_asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if db_asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset

