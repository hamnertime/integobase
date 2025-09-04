from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Base Schemas (for creation/updates) ---

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

class BillingNoteBase(BaseModel):
    note_content: str
    author: Optional[str] = None

class BillingNoteCreate(BillingNoteBase):
    pass

class AppUserBase(BaseModel):
    username: str
    role: str

class AppUserCreate(AppUserBase):
    password: Optional[str] = None # Password is not required on creation

class AppUserUpdate(AppUserBase):
    new_password: Optional[str] = None # For setting/resetting password

class FeatureOptionCreate(BaseModel):
    feature_type: str
    option_name: str

class FeatureTypeCreate(BaseModel):
    feature_type: str

class CustomLinkBase(BaseModel):
    name: str
    url: str
    link_order: int = 0

class CustomLink(CustomLinkBase):
    id: int
    class Config:
        from_attributes = True

# --- Response Schemas (for reading data from the API) ---

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
    force_password_reset: bool
    class Config:
        from_attributes = True

class KBArticle(KBArticleBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    author: AppUser
    company: Optional[CompanyBase] = None
    categories: List[KBCategory] = []
    class Config:
        from_attributes = True

class Company(CompanyBase):
    assets: List[Asset] = []
    contacts: List[Contact] = []
    class Config:
        from_attributes = True

class BillingNote(BillingNoteBase):
    id: int
    created_at: datetime
    company_account_number: str
    class Config:
        from_attributes = True

class ClientAttachment(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    uploaded_at: datetime
    file_size: int
    category: str
    class Config:
        from_attributes = True

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
    total_user_charges: float
    total_asset_charges: float
    total_line_item_charges: float
    ticket_charge: float
    backup_charge: float
    billed_users: List[Dict[str, Any]]
    billed_assets: List[Dict[str, Any]]
    billed_line_items: List[Dict[str, Any]]
    hours_for_billing_period: float
    prepaid_hours_monthly: float
    billable_hours: float
    backup_base_workstation: float
    backup_base_server: float
    total_included_tb: float
    overage_tb: float
    overage_charge: float

class ClientBillingDetails(BaseModel):
    client: Company
    receipt_data: ReceiptData
    quantities: Dict[str, int]
    effective_rates: Dict[str, Any]
    locations: List[Dict[str, Any]]
    assets: List[Asset]
    manual_assets: List[Dict[str, Any]]
    users: List[Dict[str, Any]]
    manual_users: List[Dict[str, Any]]
    custom_line_items: List[Dict[str, Any]]
    tickets_for_billing_period: List[Dict[str, Any]]
    support_level_display: str
    contract_end_date: str
    contract_expired: bool
    datto_portal_url: Optional[str] = None
    class Config:
        from_attributes = True

class BillingPlan(BaseModel):
    billing_plan: str
    class Config:
        from_attributes = True

class SchedulerJob(BaseModel):
    id: int
    job_name: str
    script_path: str
    interval_minutes: int
    enabled: bool
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    class Config:
        from_attributes = True

class SchedulerLog(BaseModel):
    log: str

class FeatureOption(BaseModel):
    id: int
    feature_type: str
    option_name: str
    class Config:
        from_attributes = True
