from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ... import models, schemas
from ...database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Company])
def read_clients(
    search: str = "",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve all clients with optional search and pagination.
    """
    query = db.query(models.Company)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            models.Company.name.ilike(search_term) |
            models.Company.account_number.ilike(search_term)
        )
    clients = query.offset(skip).limit(limit).all()
    return clients

@router.post("/", response_model=schemas.Company)
def create_client(client: schemas.CompanyCreate, db: Session = Depends(get_db)):
    """
    Create a new client.
    """
    db_client = models.Company(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.get("/{account_number}", response_model=schemas.Company)
def read_client(account_number: str, db: Session = Depends(get_db)):
    """
    Retrieve a single client by their account number.
    """
    db_client = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if db_client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return db_client

@router.put("/{account_number}", response_model=schemas.Company)
def update_client(account_number: str, client: schemas.CompanyCreate, db: Session = Depends(get_db)):
    """
    Update an existing client's details.
    """
    db_client = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if db_client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    update_data = client.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_client, key, value)

    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.delete("/{account_number}", status_code=204)
def delete_client(account_number: str, db: Session = Depends(get_db)):
    """
    Delete a client.
    """
    db_client = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if db_client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(db_client)
    db.commit()
    return {"ok": True}

