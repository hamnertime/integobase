import os
import sys
import json
import re
from sqlalchemy import text, Column, String, Float, Boolean
from werkzeug.security import generate_password_hash

# Add project root to path to allow sibling imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, Base, SessionLocal
from models import BillingPlan, ClientBillingOverride # Import models to ensure they are registered
from config import settings # To access env vars if needed

def get_config_json():
    """
    Loads configuration from a JSON file, similar to the original script.
    Looks for `config.override.json` first, then `config.json`.
    """
    config_override_path = os.path.join(os.path.dirname(__file__), '..', 'config.override.json')
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')

    if os.path.exists(config_override_path):
        print(f"Using custom configuration from 'config.override.json'.")
        with open(config_override_path, 'r') as f:
            return json.load(f)
    elif os.path.exists(config_path):
        print(f"Using default configuration from 'config.json'.")
        with open(config_path, 'r') as f:
            return json.load(f)
    else:
        print("Error: config.json not found.", file=sys.stderr)
        return {}

def add_dynamic_feature_columns():
    """
    Dynamically adds feature columns to the BillingPlan and ClientBillingOverride
    table definitions before the tables are created. This is a key step to
    replicate the dynamic ALTER TABLE logic from the original script.
    """
    config_data = get_config_json()
    default_features = config_data.get('default_features', [])
    feature_types = sorted(list(set([f[0] for f in default_features])))

    print("Dynamically adding feature columns to ORM models...")
    for feature_type in feature_types:
        column_name = 'feature_' + re.sub(r'[^a-zA-Z0-9_]', '', feature_type.lower().replace(' ', '_'))

        # Add to BillingPlan model
        default_value = 'Not Included'
        if feature_type == 'Email': default_value = 'No Business Email'
        elif feature_type == 'Phone': default_value = 'No Business Phone'
        setattr(BillingPlan, column_name, Column(String, default=default_value))

        # Add to ClientBillingOverride model
        setattr(ClientBillingOverride, column_name, Column(String, nullable=True))
        setattr(ClientBillingOverride, f'override_{column_name}_enabled', Column(Boolean, default=False))
    print("Feature columns added.")


def initialize_database():
    """
    Main function to create and populate the PostgreSQL database.
    """
    # First, dynamically modify the SQLAlchemy models before creating tables
    add_dynamic_feature_columns()

    print("Connecting to the database...")
    db = SessionLocal()

    try:
        print("Dropping all existing tables (for a clean slate)...")
        Base.metadata.drop_all(bind=engine)

        print("Creating new database schema from models...")
        Base.metadata.create_all(bind=engine)
        print("Schema creation complete.")

        # --- Data Population ---
        config_data = get_config_json()
        default_plans_data = config_data.get('default_plans_data', [])
        default_features = config_data.get('default_features', [])
        default_users = config_data.get('default_users', [])

        print("\nPopulating with default data...")

        # 1. API Keys (from .env, which is loaded into settings)
        print("Populating API keys from environment variables...")
        db.execute(text("""
            INSERT INTO api_keys (service, api_key, api_secret, api_endpoint) VALUES
            ('freshservice', :fs_key, NULL, :fs_domain),
            ('datto', :datto_key, :datto_secret, :datto_endpoint)
            ON CONFLICT (service) DO NOTHING;
        """), {
            "fs_key": settings.FRESHSERVICE_API_KEY,
            "fs_domain": f"https://{settings.FRESHSERVICE_DOMAIN}",
            "datto_key": settings.DATTO_API_KEY,
            "datto_secret": settings.DATTO_API_SECRET,
            "datto_endpoint": settings.DATTO_API_ENDPOINT
        })

        # 2. Scheduler Jobs
        print("Populating default job schedules...")
        db.execute(text("""
            INSERT INTO scheduler_jobs (job_name, script_path, interval_minutes, enabled) VALUES
            ('Sync Billing Data (Companies & Users)', 'data_pullers.pull_freshservice', 1440, TRUE),
            ('Sync Datto RMM Assets', 'data_pullers.pull_datto', 1440, TRUE),
            ('Sync Ticket Details & Hours', 'data_pullers.pull_ticket_details', 1440, TRUE)
        """))

        # 3. App Settings
        print("Populating default application settings...")
        db.execute(text("INSERT INTO app_settings (key, value) VALUES ('session_timeout_minutes', '180')"))

        # 4. Feature Options
        print("Populating default feature options...")
        if default_features:
            db.execute(text("INSERT INTO feature_options (feature_type, option_name) VALUES (:type, :name)"),
                       [{"type": f[0], "name": f[1]} for f in default_features])

        # 5. Billing Plans
        print("Populating default billing plans...")
        if default_plans_data:
            plan_insert_sql = f"""
                INSERT INTO billing_plans (billing_plan, term_length, per_user_cost, per_server_cost,
                per_workstation_cost, per_vm_cost, per_switch_cost, per_firewall_cost, per_hour_ticket_cost,
                backup_base_fee_workstation, backup_base_fee_server, backup_included_tb, backup_per_tb_fee,
                support_level, feature_antivirus, feature_soc, feature_password_manager, feature_sat,
                feature_network_management, feature_email_security) VALUES (
                :p1, :p2, :p3, :p4, :p5, :p6, :p7, :p8, :p9, :p10, :p11, :p12, :p13, :p14, :p15, :p16, :p17, :p18, :p19, :p20
                )
            """
            params = [{"p"+str(i+1): val for i, val in enumerate(plan)} for plan in default_plans_data]
            db.execute(text(plan_insert_sql), params)


        # 6. Default Users
        print("Adding default application users...")
        for user_data in default_users:
            username, role, password = user_data
            password_hash = generate_password_hash(password) if password else None
            force_reset = 1 if username.lower() != 'admin' else 0
            db.execute(text("""
                INSERT INTO app_users (username, role, password_hash, force_password_reset)
                VALUES (:user, :role, :hash, :reset)
            """), {"user": username, "role": role, "hash": password_hash, "reset": bool(force_reset)})

        # 7. Default KB Categories
        print("Populating default KB categories...")
        default_kb_categories = [
            'Networking', 'Hardware', 'Software', 'Security', 'Cloud Services',
            'Backups', 'Standard Operating Procedures', 'Client Specific', 'Internal Systems'
        ]
        db.execute(text("INSERT INTO kb_categories (name) VALUES (:name)"),
                   [{"name": cat} for cat in default_kb_categories])


        db.commit()
        print("\n✅ Success! New PostgreSQL database 'integobase_db' created and configured.")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}", file=sys.stderr)
        db.rollback()
    finally:
        db.close()
        print("Database connection closed.")


if __name__ == "__main__":
    initialize_database()
