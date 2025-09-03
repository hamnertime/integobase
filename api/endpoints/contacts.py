from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ... import models, schemas
from ...database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Contact])
def read_contacts(
    search: str = "",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve all contacts with optional search and pagination.
    """
    query = db.query(models.Contact)
    if search:
        search_term = f"%{search}%"
        query = query.join(models.Company).filter(
            models.Contact.first_name.ilike(search_term) |
            models.Contact.last_name.ilike(search_term) |
            models.Contact.email.ilike(search_term) |
            models.Company.name.ilike(search_term)
        )
    contacts = query.offset(skip).limit(limit).all()
    return contacts

@router.post("/", response_model=schemas.Contact)
def create_contact(contact: schemas.ContactCreate, db: Session = Depends(get_db)):
    """
    Create a new contact.
    """
    db_contact = models.Contact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.get("/{contact_id}", response_model=schemas.Contact)
def read_contact(contact_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single contact by their ID.
    """
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@router.put("/{contact_id}", response_model=schemas.Contact)
def update_contact(contact_id: int, contact: schemas.ContactCreate, db: Session = Depends(get_db)):
    """
    Update an existing contact.
    """
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = contact.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)

    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    """
    Delete a contact.
    """
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(db_contact)
    db.commit()
    return {"ok": True}

