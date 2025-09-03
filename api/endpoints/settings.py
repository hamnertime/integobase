from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
from werkzeug.security import generate_password_hash, check_password_hash
from ... import models, schemas
from ...database import get_db
from ...scheduler import trigger_job_run
# New imports for token handling
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

router = APIRouter()

# --- Default Widget Layouts (Moved from old Integodash) ---
default_widget_layouts = {
    "clients": [
        {"w": 12, "h": 2, "id": "export-all-widget", "x": 0, "y": 0},
        {"x": 0, "y": 2, "w": 12, "h": 8, "id": "clients-table-widget"}
    ],
    "client_details": [
        {"w": 12, "h": 1, "id": "billing-period-selector-widget"},
        {"w": 6, "h": 4, "id": "client-details-widget"},
        {"w": 6, "h": 4, "id": "client-features-widget"},
        {"w": 6, "h": 2, "id": "locations-widget"},
        {"w": 6, "h": 5, "id": "billing-receipt-widget"},
        {"w": 6, "h": 3, "id": "contract-details-widget"},
        {"w": 6, "h": 4, "id": "notes-widget"},
        {"w": 6, "h": 4, "id": "attachments-widget"},
        {"w": 12, "h": 3, "id": "tracked-assets-widget"},
        {"w": 12, "h": 3, "id": "ticket-breakdown-widget"}
    ]
    # Add other pages' default layouts here as they are refactored
}

# --- NEW: Layout Endpoints ---
@router.get("/layouts/default/{page_name}", response_model=List[Dict[str, Any]])
def get_default_layout(page_name: str):
    """Returns the default widget layout for a given page."""
    if page_name not in default_widget_layouts:
        raise HTTPException(status_code=404, detail="Default layout for this page not found.")
    return default_widget_layouts[page_name]

@router.get("/layouts/{user_id}/{page_name}", response_model=List[Dict[str, Any]])
def get_user_layout(user_id: int, page_name: str, db: Session = Depends(get_db)):
    """Fetches a user's saved layout, falling back to the default if none is found."""
    # This model name needs to match your SQLAlchemy model in models.py
    layout_data = db.query(models.UserWidgetLayout).filter_by(user_id=user_id, page_name=page_name).first()
    if layout_data and layout_data.layout:
        try:
            return json.loads(layout_data.layout)
        except json.JSONDecodeError:
            pass # Fallback to default if JSON is invalid

    if page_name not in default_widget_layouts:
        raise HTTPException(status_code=404, detail="Layout for this page not found.")
    return default_widget_layouts[page_name]

# --- User Authentication ---
@router.post("/users/login/")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.AppUser).filter(models.AppUser.username == form_data.username).first()
    if not user or not user.password_hash or not check_password_hash(user.password_hash, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # This should be replaced with a real JWT implementation in production
    access_token = f"fake-super-secret-token-for-{user.username}"
    return {"access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "username": user.username, "role": user.role}}

# --- User Management Endpoints ---
# (The rest of your settings endpoints remain the same)
@router.get("/users/", response_model=List[schemas.AppUser])
def read_users(db: Session = Depends(get_db)):
    """Retrieve all application users."""
    return db.query(models.AppUser).all()

# ... (rest of the file)
