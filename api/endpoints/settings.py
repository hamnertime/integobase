from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Any
import json
import re
from werkzeug.security import generate_password_hash, check_password_hash
from ... import models, schemas
from ...database import get_db, engine
from ...scheduler import trigger_job_run
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy import text
from collections import defaultdict
import os

router = APIRouter()

# --- Default Widget Layouts ---
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
    ],
    "kb": [
        {"x": 0, "y": 0, "w": 12, "h": 8, "id": "kb-articles-table-widget"}
    ],
    "contacts": [
        {"x": 0, "y": 0, "w": 12, "h": 8, "id": "contacts-table-widget"}
    ],
    "contact_details": [
        {"x": 0, "y": 0, "w": 7, "h": 6, "id": "contact-info-widget"},
        {"x": 7, "y": 0, "w": 5, "h": 6, "id": "associated-assets-widget"},
        {"x": 0, "y": 6, "w": 12, "h": 4, "id": "contact-notes-widget"}
    ],
    "assets": [
        {"x": 0, "y": 0, "w": 12, "h": 8, "id": "assets-table-widget"}
    ],
    "client_settings": [
        {"w": 6, "h": 5, "id": "client-details-widget", "x": 0, "y": 0},
        {"x": 6, "w": 6, "h": 5, "id": "contract-details-widget", "y": 0},
        {"y": 5, "w": 12, "h": 4, "id": "locations-settings-widget", "x": 0},
        {"y": 9, "w": 12, "h": 7, "id": "billing-overrides-widget", "x": 0},
        {"y": 16, "w": 12, "h": 4, "id": "feature-overrides-widget", "x": 0},
        {"y": 20, "w": 12, "h": 4, "id": "custom-line-items-widget", "x": 0},
        {"x": 0, "y": 24, "w": 6, "h": 4, "id": "add-manual-user-widget"},
        {"y": 24, "w": 6, "h": 4, "id": "add-manual-asset-widget", "x": 6},
        {"y": 28, "w": 12, "h": 3, "id": "user-overrides-widget", "x": 0},
        {"y": 31, "w": 12, "h": 4, "id": "asset-overrides-widget", "x": 0}
    ],
    "settings": [
        {"w": 12, "h": 2, "id": "import-export-widget", "x": 0, "y": 0},
        {"x": 0, "w": 12, "h": 4, "id": "scheduler-widget", "y": 2},
        {"y": 6, "w": 12, "h": 7, "id": "users-auditing-widget", "x": 0},
        {"y": 13, "w": 12, "h": 4, "id": "password-reset-widget", "x": 0},
        {"y": 17, "w": 12, "h": 3, "id": "custom-links-widget", "x": 0},
        {"y": 20, "w": 12, "h": 8, "id": "billing-plans-widget", "x": 0},
        {"x": 0, "y": 28, "w": 12, "h": 8, "id": "feature-options-widget"}
    ],
}

def sanitize_column_name(name: str) -> str:
    """Sanitizes a string to be a valid SQL column name for a feature."""
    return 'feature_' + re.sub(r'[^a-zA-Z0-9_]', '', name.lower().replace(' ', '_'))


# --- Layout Endpoints ---
@router.get("/layouts/default/{page_name}", response_model=List[Dict[str, Any]])
def get_default_layout(page_name: str):
    if page_name not in default_widget_layouts:
        raise HTTPException(status_code=404, detail="Default layout for this page not found.")
    return default_widget_layouts[page_name]

@router.get("/layouts/{user_id}/{page_name}", response_model=List[Dict[str, Any]])
def get_user_layout(user_id: int, page_name: str, db: Session = Depends(get_db)):
    layout_data = db.query(models.UserWidgetLayout).filter_by(user_id=user_id, page_name=page_name).first()
    if layout_data and layout_data.layout:
        try:
            return json.loads(layout_data.layout)
        except json.JSONDecodeError:
            pass # Fallback to default if JSON is invalid

    if page_name not in default_widget_layouts:
        raise HTTPException(status_code=404, detail="Layout for this page not found.")
    return default_widget_layouts[page_name]

@router.post("/layouts/{user_id}/{page_name}")
def save_user_layout(user_id: int, page_name: str, payload: dict, db: Session = Depends(get_db)):
    layout = payload.get('layout')
    if not layout:
        raise HTTPException(status_code=400, detail="Layout data is required.")

    db_layout = db.query(models.UserWidgetLayout).filter_by(user_id=user_id, page_name=page_name).first()
    if db_layout:
        db_layout.layout = layout
    else:
        db_layout = models.UserWidgetLayout(user_id=user_id, page_name=page_name, layout=layout)
        db.add(db_layout)
    db.commit()
    return {"status": "success"}

@router.delete("/layouts/{user_id}/{page_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_layout(user_id: int, page_name: str, db: Session = Depends(get_db)):
    db_layout = db.query(models.UserWidgetLayout).filter_by(user_id=user_id, page_name=page_name).first()
    if db_layout:
        db.delete(db_layout)
        db.commit()
    return {"status": "success"}


# --- User Authentication & Management ---
@router.post("/users/login", tags=["Auth"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.AppUser).filter(models.AppUser.username == form_data.username).first()
    if not user or not user.password_hash or not check_password_hash(user.password_hash, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = f"fake-super-secret-token-for-{user.username}"
    return {"access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "username": user.username, "role": user.role}}

@router.get("/users/", response_model=List[schemas.AppUser])
def read_users(db: Session = Depends(get_db)):
    return db.query(models.AppUser).order_by(models.AppUser.username).all()

@router.post("/users/", response_model=schemas.AppUser, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.AppUserCreate, db: Session = Depends(get_db)):
    db_user = models.AppUser(
        username=user.username,
        role=user.role,
        force_password_reset=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/users/{user_id}", response_model=schemas.AppUser)
def update_user(user_id: int, user_update: schemas.AppUserUpdate, db: Session = Depends(get_db)):
    db_user = db.query(models.AppUser).filter(models.AppUser.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.username = user_update.username
    db_user.role = user_update.role
    if user_update.new_password:
        db_user.password_hash = generate_password_hash(user_update.new_password)
        db_user.force_password_reset = True

    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    if user_id == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the default Admin user.")
    db_user = db.query(models.AppUser).filter(models.AppUser.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return {"ok": True}

# --- Billing Plan Endpoint ---
@router.get("/billing-plans/", response_model=List[schemas.BillingPlan])
def read_billing_plans(db: Session = Depends(get_db)):
    plans_query = db.query(models.BillingPlan.billing_plan).distinct().order_by(models.BillingPlan.billing_plan).all()
    return [{"billing_plan": p[0]} for p in plans_query]

# --- Scheduler Endpoints ---
@router.get("/scheduler/jobs", response_model=List[schemas.SchedulerJob])
def get_scheduler_jobs(db: Session = Depends(get_db)):
    return db.query(models.SchedulerJob).order_by(models.SchedulerJob.id).all()

@router.post("/scheduler/run-now/{job_id}", status_code=status.HTTP_202_ACCEPTED)
def run_job_now(job_id: int):
    trigger_job_run(job_id)
    return {"message": f"Job {job_id} has been triggered to run."}

@router.get("/scheduler/log/{job_id}", response_model=schemas.SchedulerLog)
def get_job_log(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.SchedulerJob).filter(models.SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"log": job.last_run_log or "No log available."}

# --- Feature Options Endpoints ---
@router.get("/features/", response_model=Dict[str, List[schemas.FeatureOption]])
def get_all_feature_options(db: Session = Depends(get_db)):
    options_raw = db.query(models.FeatureOption).order_by(models.FeatureOption.feature_type, models.FeatureOption.option_name).all()
    feature_options = defaultdict(list)
    for option in options_raw:
        feature_options[option.feature_type].append(option)
    return feature_options

@router.post("/features/types", status_code=status.HTTP_201_CREATED)
def add_feature_type(feature_type_in: schemas.FeatureTypeCreate, db: Session = Depends(get_db)):
    feature_type = feature_type_in.feature_type
    column_name = sanitize_column_name(feature_type)

    with engine.connect() as connection:
        with connection.begin(): # Start a transaction
            try:
                # Using text() to mark the string as a SQL expression
                connection.execute(text(f"ALTER TABLE billing_plans ADD COLUMN {column_name} TEXT DEFAULT 'Not Included'"))
                connection.execute(text(f"ALTER TABLE client_billing_overrides ADD COLUMN {column_name} TEXT"))
                connection.execute(text(f"ALTER TABLE client_billing_overrides ADD COLUMN override_{column_name}_enabled BOOLEAN DEFAULT 0"))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Database error: {e}")

    db_option = models.FeatureOption(feature_type=feature_type, option_name="Not Included")
    db.add(db_option)
    db.commit()
    return {"message": "Feature category created successfully"}

# --- Custom Links Endpoints (Added to fix 404) ---
@router.get("/links/", response_model=List[schemas.CustomLink])
def get_custom_links(db: Session = Depends(get_db)):
    return db.query(models.CustomLink).order_by(models.CustomLink.link_order).all()

@router.post("/links/", response_model=schemas.CustomLink, status_code=status.HTTP_201_CREATED)
def add_custom_link(link_in: schemas.CustomLinkBase, db: Session = Depends(get_db)):
    db_link = models.CustomLink(**link_in.model_dump())
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link

@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_link(link_id: int, db: Session = Depends(get_db)):
    db_link = db.query(models.CustomLink).filter(models.CustomLink.id == link_id).first()
    if not db_link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(db_link)
    db.commit()
    return {"ok": True}

@router.put("/links/{link_id}", response_model=schemas.CustomLink)
def update_custom_link(link_id: int, link_in: schemas.CustomLinkBase, db: Session = Depends(get_db)):
    db_link = db.query(models.CustomLink).filter(models.CustomLink.id == link_id).first()
    if not db_link:
        raise HTTPException(status_code=404, detail="Link not found")

    update_data = link_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_link, key, value)
    db.commit()
    db.refresh(db_link)
    return db_link
