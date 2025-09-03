from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, String, Float, Text, DateTime,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# --- Core Company and Asset Models ---

class Company(Base):
    __tablename__ = "companies"
    account_number = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    freshservice_id = Column(Integer, unique=True, index=True)
    datto_site_uid = Column(String, unique=True, nullable=True)
    datto_portal_url = Column(String, nullable=True)
    contract_type = Column(String, nullable=True)
    billing_plan = Column(String, nullable=True)
    status = Column(String, nullable=True)
    contract_term_length = Column(String, nullable=True)
    contract_start_date = Column(DateTime, nullable=True)
    support_level = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    client_start_date = Column(DateTime, nullable=True)
    domains = Column(Text, nullable=True)
    company_owner = Column(String, nullable=True)
    business_type = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    # Relationships
    locations = relationship("ClientLocation", back_populates="company", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="company", cascade="all, delete-orphan")
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    notes = relationship("BillingNote", back_populates="company", cascade="all, delete-orphan")
    attachments = relationship("ClientAttachment", back_populates="company", cascade="all, delete-orphan")
    line_items = relationship("CustomLineItem", back_populates="company", cascade="all, delete-orphan")
    billing_override = relationship("ClientBillingOverride", back_populates="company", uselist=False, cascade="all, delete-orphan")
    kb_articles = relationship("KBArticle", back_populates="company")

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"))
    datto_uid = Column(String, unique=True, index=True)
    hostname = Column(String, index=True)
    friendly_name = Column(String, nullable=True)
    device_type = Column(String, nullable=True)
    billing_type = Column(String, nullable=True)
    status = Column(String, default='Active')
    date_added = Column(DateTime, nullable=True)
    operating_system = Column(String, nullable=True)
    backup_data_bytes = Column(Float, default=0)
    internal_ip = Column(String, nullable=True)
    external_ip = Column(String, nullable=True)
    last_logged_in_user = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    is_64_bit = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    last_reboot = Column(DateTime, nullable=True)
    last_audit_date = Column(DateTime, nullable=True)
    udf_data = Column(Text, nullable=True) # Stored as JSON string
    antivirus_data = Column(Text, nullable=True) # Stored as JSON string
    patch_management_data = Column(Text, nullable=True) # Stored as JSON string
    portal_url = Column(String, nullable=True)
    web_remote_url = Column(String, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="assets")
    billing_override = relationship("AssetBillingOverride", uselist=False, back_populates="asset", cascade="all, delete-orphan")
    contact_links = relationship("AssetContactLink", back_populates="asset", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"))
    freshservice_id = Column(Integer, unique=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    status = Column(String, default='Active')
    date_added = Column(DateTime, nullable=True)
    billing_type = Column(String, default='Regular')

    # Relationships
    company = relationship("Company", back_populates="users")
    billing_override = relationship("UserBillingOverride", uselist=False, back_populates="user", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"))
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, index=True)
    title = Column(String, nullable=True)
    work_phone = Column(String, nullable=True)
    mobile_phone = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    status = Column(String, default='Active')
    other_emails = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="contacts")
    notes_log = relationship("ContactNote", back_populates="contact", cascade="all, delete-orphan")
    asset_links = relationship("AssetContactLink", back_populates="contact", cascade="all, delete-orphan")


# --- Join Table for Asset-Contact Many-to-Many ---

class AssetContactLink(Base):
    __tablename__ = 'asset_contact_links'
    asset_id = Column(Integer, ForeignKey('assets.id'), primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'), primary_key=True)

    asset = relationship("Asset", back_populates="contact_links")
    contact = relationship("Contact", back_populates="asset_links")


# --- Billing and Overrides ---

class BillingPlan(Base):
    __tablename__ = "billing_plans"
    id = Column(Integer, primary_key=True, index=True)
    billing_plan = Column(String, index=True)
    term_length = Column(String)
    support_level = Column(String, default='Billed Hourly')
    per_user_cost = Column(Float, default=0.0)
    per_server_cost = Column(Float, default=0.0)
    per_workstation_cost = Column(Float, default=0.0)
    per_vm_cost = Column(Float, default=0.0)
    per_switch_cost = Column(Float, default=0.0)
    per_firewall_cost = Column(Float, default=0.0)
    per_hour_ticket_cost = Column(Float, default=0.0)
    backup_base_fee_workstation = Column(Float, default=25.0)
    backup_base_fee_server = Column(Float, default=50.0)
    backup_included_tb = Column(Float, default=1.0)
    backup_per_tb_fee = Column(Float, default=15.0)
    # Dynamic feature columns will be added by init_db.py
    # e.g., feature_antivirus = Column(String, default='Not Included')

    __table_args__ = (UniqueConstraint('billing_plan', 'term_length', name='_billing_plan_term_uc'),)


class ClientBillingOverride(Base):
    __tablename__ = "client_billing_overrides"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"), unique=True)
    # Columns match BillingPlan, but are nullable
    billing_plan = Column(String, nullable=True)
    support_level = Column(String, nullable=True)
    per_user_cost = Column(Float, nullable=True)
    # ... all other rate columns from BillingPlan, nullable
    override_billing_plan_enabled = Column(Boolean, default=False)
    override_support_level_enabled = Column(Boolean, default=False)
    # ... all other override_..._enabled flags
    # ... all dynamic feature override columns and flags

    # Relationship
    company = relationship("Company", back_populates="billing_override")


class AssetBillingOverride(Base):
    __tablename__ = "asset_billing_overrides"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), unique=True)
    billing_type = Column(String)
    custom_cost = Column(Float, nullable=True)

    asset = relationship("Asset", back_populates="billing_override")


class UserBillingOverride(Base):
    __tablename__ = "user_billing_overrides"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    billing_type = Column(String)
    custom_cost = Column(Float, nullable=True)
    employment_type = Column(String, nullable=True)

    user = relationship("User", back_populates="billing_override")


# --- Client-Specific Data ---

class ClientLocation(Base):
    __tablename__ = "client_locations"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"))
    location_name = Column(String)
    address = Column(String, nullable=True)

    company = relationship("Company", back_populates="locations")
    __table_args__ = (UniqueConstraint('company_account_number', 'location_name', name='_company_location_uc'),)


class BillingNote(Base):
    __tablename__ = "billing_notes"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"))
    note_content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    author = Column(String)

    company = relationship("Company", back_populates="notes")


class ContactNote(Base):
    __tablename__ = "contact_notes"
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    note_content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    author = Column(String)

    contact = relationship("Contact", back_populates="notes_log")


class ClientAttachment(Base):
    __tablename__ = "client_attachments"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"))
    original_filename = Column(String)
    stored_filename = Column(String, unique=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    file_size = Column(Integer)
    category = Column(String)

    company = relationship("Company", back_populates="attachments")


class CustomLineItem(Base):
    __tablename__ = "custom_line_items"
    id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"))
    name = Column(String)
    monthly_fee = Column(Float, nullable=True)
    one_off_fee = Column(Float, nullable=True)
    one_off_month = Column(Integer, nullable=True)
    one_off_year = Column(Integer, nullable=True)
    yearly_fee = Column(Float, nullable=True)
    yearly_bill_month = Column(Integer, nullable=True)
    yearly_bill_day = Column(Integer, nullable=True)

    company = relationship("Company", back_populates="line_items")


class TicketDetail(Base):
    __tablename__ = "ticket_details"
    ticket_id = Column(Integer, primary_key=True, index=True)
    company_account_number = Column(String, ForeignKey("companies.account_number"), nullable=True)
    subject = Column(String)
    last_updated_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True), nullable=True)
    total_hours_spent = Column(Float)


# --- Application & System Models ---

class AppUser(Base):
    __tablename__ = "app_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String, nullable=True)
    role = Column(String, default='Read-Only')
    force_password_reset = Column(Boolean, default=True)


class SchedulerJob(Base):
    __tablename__ = "scheduler_jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, unique=True)
    script_path = Column(String)
    interval_minutes = Column(Integer)
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    last_status = Column(String, nullable=True)
    last_run_log = Column(Text, nullable=True)


class APIKey(Base):
    __tablename__ = "api_keys"
    service = Column(String, primary_key=True, index=True)
    api_key = Column(String)
    api_secret = Column(String, nullable=True)
    api_endpoint = Column(String, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = Column(String, primary_key=True, index=True)
    value = Column(String)


class CustomLink(Base):
    __tablename__ = "custom_links"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    url = Column(String)
    link_order = Column(Integer, default=0)


class FeatureOption(Base):
    __tablename__ = "feature_options"
    id = Column(Integer, primary_key=True, index=True)
    feature_type = Column(String)
    option_name = Column(String)

    __table_args__ = (UniqueConstraint('feature_type', 'option_name', name='_feature_option_uc'),)


# --- Knowledge Base ---

class KBArticle(Base):
    __tablename__ = "kb_articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("app_users.id"))
    visibility = Column(String, default='Internal')
    company_account_number = Column(String, ForeignKey("companies.account_number"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author = relationship("AppUser")
    company = relationship("Company", back_populates="kb_articles")
    categories = relationship("KBCategory", secondary="kb_article_category_link", back_populates="articles")


class KBCategory(Base):
    __tablename__ = "kb_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    articles = relationship("KBArticle", secondary="kb_article_category_link", back_populates="categories")


class KBArticleCategoryLink(Base):
    __tablename__ = 'kb_article_category_link'
    article_id = Column(Integer, ForeignKey('kb_articles.id'), primary_key=True)
    category_id = Column(Integer, ForeignKey('kb_categories.id'), primary_key=True)
