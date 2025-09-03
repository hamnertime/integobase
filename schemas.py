from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Base Schemas ---

class CompanyBase(BaseModel):
    account_number: str
    name: str
    freshservice_id: Optional[int] = None
    datto_site_uid: Optional[str] = None
    datto_portal_url: Optional[str] = None
    contract_type: Optional[str] = None
    billing_plan: Optional[str] = None
    status: Optional[str] = None
    contract_term_length: Optional[str] = None
    contract_start_date: Optional[datetime] = None
    support_level: Optional[str] = None
    phone_number: Optional[str] = None
    client_start_date: Optional[datetime] = None
    domains: Optional[str] = None
    company_owner: Optional[str] = None
    business_type: Optional[str] = None
    description: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class AssetBase(BaseModel):
    hostname: str
    company_account_number: str
    datto_uid: Optional[str] = None
    device_type: Optional[str] = None
    billing_type: Optional[str] = None

class AssetCreate(AssetBase):
    pass

class ContactBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    company_account_number: str
    title: Optional[str] = None
    work_phone: Optional[str] = None
    mobile_phone: Optional[str] = None
    employment_type: Optional[str] = None
    status: Optional[str] = 'Active'

class ContactCreate(ContactBase):
    pass

class KBCategoryBase(BaseModel):
    name: str

class KBCategoryCreate(KBCategoryBase):
    pass

class KBArticleBase(BaseModel):
    title: str
    content: str
    visibility: str = 'Internal'
    company_account_number: Optional[str] = None

class KBArticleCreate(KBArticleBase):
    category_ids: List[int] = []

class AppSettingBase(BaseModel):
    key: str
    value: str

class AppSettingCreate(AppSettingBase):
    pass

class AppUserBase(BaseModel):
    username: str
    role: str

class AppUserCreate(AppUserBase):
    password: str

class BillingPlanBase(BaseModel):
    billing_plan: str
    term_length: str
    support_level: str
    per_user_cost: float
    per_workstation_cost: float
    per_server_cost: float
    # Add other cost fields as necessary

class BillingPlanCreate(BillingPlanBase):
    pass

class BillingPlanUpdate(BillingPlanBase):
    pass

class SchedulerJobBase(BaseModel):
    job_name: str
    script_path: str
    interval_minutes: int
    enabled: bool

class SchedulerJobUpdate(SchedulerJobBase):
    pass


# --- Response Schemas ---

class Contact(ContactBase):
    id: int
    class Config:
        from_attributes = True

class Asset(AssetBase):
    id: int
    is_online: Optional[bool] = None
    last_seen: Optional[datetime] = None
    operating_system: Optional[str] = None
    portal_url: Optional[str] = None
    web_remote_url: Optional[str] = None
    class Config:
        from_attributes = True

class KBCategory(KBCategoryBase):
    id: int
    class Config:
        from_attributes = True

class AppUser(AppUserBase):
    id: int
    class Config:
        from_attributes = True

class KBArticle(KBArticleBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    categories: List[KBCategory] = []
    author: AppUser
    class Config:
        from_attributes = True

class Company(CompanyBase):
    assets: List[Asset] = []
    contacts: List[Contact] = []
    class Config:
        from_attributes = True

# --- API-Specific Schemas for Refactored Integodash ---

class ClientDashboard(BaseModel):
    account_number: str
    name: str
    billing_plan: Optional[str] = None
    support_level: Optional[str] = None
    contract_end_date: Optional[str] = None
    workstations: int
    servers: int
    vms: int
    regular_users: int
    total_backup_bytes: float
    total_hours: float
    total_bill: float
    contract_expired: bool

class ReceiptData(BaseModel):
    total: float
    # ... other receipt fields will be added here

class ClientBillingDetails(BaseModel):
    client: Company
    receipt_data: ReceiptData
    quantities: Dict[str, int]
    effective_rates: Dict[str, Any]
    class Config:
        from_attributes = True

# --- Schemas for settings page ---
class AppSetting(AppSettingBase):
    class Config:
        from_attributes = True

class BillingPlan(BillingPlanBase):
    id: int
    class Config:
        from_attributes = True

class SchedulerJob(SchedulerJobBase):
    id: int
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    class Config:
        from_attributes = True
