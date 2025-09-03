# integobase/api/endpoints/clients.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from ... import models, schemas, billing
from ...database import get_db
import os
import uuid
from werkzeug.utils import secure_filename

router = APIRouter()

# --- Existing Endpoints (with the new paginated dashboard) ---
@router.get("/", response_model=List[schemas.Company])
def read_clients(search: str = "", skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # ... (implementation from previous message)
    pass

@router.post("/", response_model=schemas.Company)
def create_client(client: schemas.CompanyCreate, db: Session = Depends(get_db)):
    # ... (implementation from previous message)
    pass

@router.get("/dashboard", response_model=List[schemas.ClientDashboard])
def get_dashboard_data(db: Session = Depends(get_db)):
    # ... (implementation from previous message)
    pass

@router.get("/dashboard/paginated")
def get_paginated_dashboard_data(page: int = 1, per_page: int = 50, search: str = "", sort_by: str = "name", sort_order: str = "asc", db: Session = Depends(get_db)):
    # ... (implementation from previous message)
    pass

# --- NEW Billing Details Endpoint ---
@router.get("/{account_number}/billing-details", response_model=schemas.ClientBillingDetails)
def get_client_billing_details(account_number: str, year: int, month: int, db: Session = Depends(get_db)):
    """ A comprehensive endpoint to fetch all data for the client details page. """
    details = billing.get_billing_data_for_client(db, account_number, year, month)
    if not details:
        raise HTTPException(status_code=404, detail="Client not found or billing plan is unconfigured.")
    return details

# --- NEW Note Endpoints ---
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

# --- NEW Attachment Endpoints ---
UPLOAD_FOLDER = 'uploads' # Should be configured via settings
@router.post("/{account_number}/attachments")
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

# ... (other client endpoints from previous message)
