# integobase/api/endpoints/clients.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ... import models, schemas, billing
from ...database import get_db
import os
import uuid
from werkzeug.utils import secure_filename

router = APIRouter()
UPLOAD_FOLDER = 'uploads'

@router.get("/", response_model=List[schemas.Company])
def read_clients(search: str = "", skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
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


@router.post("/", response_model=schemas.Company, status_code=status.HTTP_201_CREATED)
def create_client(client: schemas.CompanyCreate, db: Session = Depends(get_db)):
    """
    Create a new client.
    """
    db_company = db.query(models.Company).filter(models.Company.account_number == client.account_number).first()
    if db_company:
        raise HTTPException(status_code=400, detail="Client with this account number already exists")
    db_client = models.Company(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


@router.get("/dashboard/paginated")
def get_paginated_dashboard_data(page: int = 1, per_page: int = 50, search: str = "", sort_by: str = "name", sort_order: str = "asc", db: Session = Depends(get_db)):
    """
    Handles the paginated, sorted, and searchable data for the main client dashboard.
    """
    all_clients_data = billing.get_billing_dashboard_data(db)

    # --- Search ---
    if search:
        search_term = search.lower()
        all_clients_data = [
            c for c in all_clients_data
            if search_term in c.get('name', '').lower() or \
               search_term in c.get('account_number', '').lower() or \
               search_term in c.get('billing_plan', '').lower()
        ]

    # --- Sorting ---
    reverse_order = sort_order == 'desc'
    # Handle cases where the sort_by key might not exist for a client (e.g., None values)
    all_clients_data.sort(key=lambda x: (x.get(sort_by) is not None, x.get(sort_by)), reverse=reverse_order)

    # --- Pagination ---
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_clients = all_clients_data[start_index:end_index]
    total_pages = (len(all_clients_data) + per_page - 1) // per_page

    return {
        "clients": paginated_clients,
        "total_pages": total_pages,
        "current_page": page
    }

@router.get("/{account_number}", response_model=schemas.Company)
def read_client(account_number: str, db: Session = Depends(get_db)):
    """
    Retrieve a single client by their account number.
    """
    db_client = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if db_client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return db_client

@router.delete("/{account_number}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(account_number: str, db: Session = Depends(get_db)):
    """
    Delete a client by their account number.
    """
    db_client = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if db_client:
        db.delete(db_client)
        db.commit()
    return {"ok": True}


@router.get("/{account_number}/billing-details")
def get_client_billing_details(account_number: str, year: int, month: int, db: Session = Depends(get_db)):
    """ A comprehensive endpoint to fetch all data for the client details page. """
    details = billing.get_billing_data_for_client(db, account_number, year, month)
    if not details:
        raise HTTPException(status_code=404, detail="Client not found or billing plan is unconfigured.")
    return details


@router.post("/{account_number}/notes", response_model=schemas.BillingNote)
def create_note_for_client(account_number: str, note: schemas.BillingNoteCreate, db: Session = Depends(get_db)):
    db_company = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if not db_company:
        raise HTTPException(status_code=404, detail="Client not found")
    db_note = models.BillingNote(**note.model_dump(), company_account_number=account_number)
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db_note = db.query(models.BillingNote).filter(models.BillingNote.id == note_id).first()
    if db_note:
        db.delete(db_note)
        db.commit()
    return {"ok": True}


@router.post("/{account_number}/attachments", response_model=schemas.ClientAttachment)
def upload_attachment_for_client(account_number: str, category: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    db_company = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if not db_company:
        raise HTTPException(status_code=404, detail="Client not found")

    original_filename = secure_filename(file.filename)
    stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
    client_upload_dir = os.path.join(UPLOAD_FOLDER, account_number)
    os.makedirs(client_upload_dir, exist_ok=True)
    file_path = os.path.join(client_upload_dir, stored_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    file_size = os.path.getsize(file_path)

    db_attachment = models.ClientAttachment(
        company_account_number=account_number,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_size=file_size,
        category=category
    )
    db.add(db_attachment)
    db.commit()
    db.refresh(db_attachment)
    return db_attachment

@router.get("/{account_number}/assets", response_model=List[schemas.Asset])
def get_assets_for_client(account_number: str, db: Session = Depends(get_db)):
    """
    Retrieve all assets associated with a specific client account number.
    """
    assets = db.query(models.Asset).filter(models.Asset.company_account_number == account_number).all()
    if not assets:
        return []
    return assets
