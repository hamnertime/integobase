from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
from werkzeug.security import generate_password_hash
from ... import models, schemas
from ...database import get_db
from ...scheduler import trigger_job_run

router = APIRouter()

# --- App Settings (e.g., Session Timeout) ---
@router.get("/app/", response_model=List[schemas.AppSetting])
def read_app_settings(db: Session = Depends(get_db)):
    """
    Retrieve all application settings.
    """
    return db.query(models.AppSetting).all()

@router.put("/app/{key}", response_model=schemas.AppSetting)
def update_app_setting(key: str, setting: schemas.AppSettingCreate, db: Session = Depends(get_db)):
    """
    Create or update a specific application setting.
    """
    db_setting = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
    if db_setting:
        db_setting.value = setting.value
    else:
        db_setting = models.AppSetting(key=key, value=setting.value)
        db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting

# --- Billing Plan Endpoints ---
@router.get("/billing_plans/", response_model=List[schemas.BillingPlan])
def read_billing_plans(db: Session = Depends(get_db)):
    """
    Retrieve all billing plans.
    """
    return db.query(models.BillingPlan).order_by(models.BillingPlan.billing_plan, models.BillingPlan.term_length).all()

@router.post("/billing_plans/", response_model=schemas.BillingPlan, status_code=status.HTTP_201_CREATED)
def create_billing_plan(plan: schemas.BillingPlanCreate, db: Session = Depends(get_db)):
    """
    Create a new billing plan term.
    """
    db_plan = models.BillingPlan(**plan.model_dump())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.put("/billing_plans/{plan_id}", response_model=schemas.BillingPlan)
def update_billing_plan(plan_id: int, plan: schemas.BillingPlanUpdate, db: Session = Depends(get_db)):
    """
    Update an existing billing plan term.
    """
    db_plan = db.query(models.BillingPlan).filter(models.BillingPlan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Billing plan not found")

    update_data = plan.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_plan, key, value)

    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.delete("/billing_plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_billing_plan(plan_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific billing plan term.
    """
    db_plan = db.query(models.BillingPlan).filter(models.BillingPlan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    db.delete(db_plan)
    db.commit()
    return {"ok": True}

# --- Scheduler Job Endpoints ---
@router.get("/scheduler_jobs/", response_model=List[schemas.SchedulerJob])
def read_scheduler_jobs(db: Session = Depends(get_db)):
    """
    Retrieve all scheduler jobs.
    """
    return db.query(models.SchedulerJob).all()

@router.put("/scheduler_jobs/{job_id}", response_model=schemas.SchedulerJob)
def update_scheduler_job(job_id: int, job: schemas.SchedulerJobUpdate, db: Session = Depends(get_db)):
    """
    Update a scheduler job's settings (e.g., interval, enabled status).
    """
    db_job = db.query(models.SchedulerJob).filter(models.SchedulerJob.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Scheduler job not found")

    update_data = job.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_job, key, value)

    db.commit()
    db.refresh(db_job)
    # Note: The running scheduler will need to be signaled or restarted to pick up changes.
    return db_job

@router.post("/scheduler_jobs/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_scheduler_job_now(job_id: int, db: Session = Depends(get_db)):
    """
    Trigger a scheduler job to run immediately.
    """
    db_job = db.query(models.SchedulerJob).filter(models.SchedulerJob.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Scheduler job not found")

    trigger_job_run(job_id)
    return {"message": f"Job '{db_job.job_name}' has been triggered to run."}

# --- User Management Endpoints ---
@router.get("/users/", response_model=List[schemas.AppUser])
def read_users(db: Session = Depends(get_db)):
    """
    Retrieve all application users.
    """
    return db.query(models.AppUser).all()

@router.post("/users/", response_model=schemas.AppUser, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.AppUserCreate, db: Session = Depends(get_db)):
    """
    Create a new application user.
    """
    hashed_password = generate_password_hash(user.password)
    db_user = models.AppUser(
        username=user.username,
        role=user.role,
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/users/{user_id}", response_model=schemas.AppUser)
def update_user(user_id: int, user: schemas.AppUserCreate, db: Session = Depends(get_db)):
    """
    Update an application user's details (role, etc.).
    """
    db_user = db.query(models.AppUser).filter(models.AppUser.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user.model_dump(exclude_unset=True)
    # Exclude password from general updates; should be handled separately
    if 'password' in update_data:
        del update_data['password']

    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Delete an application user.
    """
    db_user = db.query(models.AppUser).filter(models.AppUser.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"ok": True}

# --- Import / Export Endpoints ---
@router.get("/export/", response_model=Dict[str, List[Any]])
def export_all_settings(db: Session = Depends(get_db)):
    """
    Export all settings and data from the database into a single JSON object.
    """
    export_data = {}
    # This list is speculative and needs to match actual models/schemas
    tables_to_export = [
        "Company", "ClientLocation", "AppUser", "BillingPlan",
        "FeatureOption", "CustomLink"
        # Add other models as needed, ensuring they have corresponding Pydantic schemas
    ]

    for model_name in tables_to_export:
        try:
            model = getattr(models, model_name)
            schema = getattr(schemas, model_name)
            records = db.query(model).all()
            export_data[model_name.lower() + 's'] = [schema.from_orm(rec).dict() for rec in records]
        except AttributeError:
            print(f"Warning: Could not export table for model {model_name}. Model or Schema not found.")

    return export_data

@router.post("/import/", status_code=status.HTTP_202_ACCEPTED)
async def import_all_settings(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Import settings from a JSON file, overwriting existing data.
    """
    if file.content_type != "application/json":
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a JSON file.")

    contents = await file.read()
    import_data = json.loads(contents)

    # This is a simplified import and should be made more robust
    # Process in a safe order to respect foreign keys
    tables_to_import = [
        "BillingPlan", "AppUser", "Company", "ClientLocation"
    ]

    try:
        with db.begin():
            for model_name in reversed(tables_to_import): # Delete in reverse order
                 if (model_name.lower() + 's') in import_data:
                    model = getattr(models, model_name)
                    db.query(model).delete()

            for model_name in tables_to_import:
                table_key = model_name.lower() + 's'
                if table_key in import_data:
                    model = getattr(models, model_name)
                    for record in import_data[table_key]:
                        db.add(model(**record))
        return {"message": "Settings imported successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred during import: {str(e)}")
