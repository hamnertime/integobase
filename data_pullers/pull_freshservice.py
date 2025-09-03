import requests
import base64
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from .. import models

# --- Configuration ---
FRESHSERVICE_DOMAIN = "integotecllc.freshservice.com" # This could be moved to config
ACCOUNT_NUMBER_FIELD = "account_number"
PHONE_NUMBER_FIELD = "company_main_number"
CLIENT_START_DATE_FIELD = "company_start_date"
BUSINESS_TYPE_FIELD = "profit_or_non_profit"
ADDRESS_FIELD = "address"
COMPANIES_PER_PAGE = 100
USERS_PER_PAGE = 100

# --- Helper Functions ---
def get_paginated_api_request(endpoint: str, headers: dict, element_key: str) -> list | None:
    """Handles paginated API requests to Freshservice."""
    all_items = []
    page = 1
    while True:
        params = {'page': page, 'per_page': COMPANIES_PER_PAGE}
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=90)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"  -> Rate limit hit, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            data = response.json()
            items_on_page = data.get(element_key, [])
            if not items_on_page:
                break
            all_items.extend(items_on_page)
            page += 1
            time.sleep(0.5) # Be respectful of API limits
        except requests.exceptions.RequestException as e:
            print(f"An error occurred during paginated API request for {endpoint}: {e}")
            return None
    return all_items

def sync_freshservice_data(db: Session):
    """
    Main function to sync all companies and users from Freshservice into the database.
    """
    print("--- Starting Freshservice Data Sync ---")

    # Get Freshservice credentials from settings
    fs_creds = db.query(models.ApiKey).filter(models.ApiKey.service == 'freshservice').first()
    if not fs_creds:
        print("Freshservice credentials not found in the database. Aborting sync.")
        return

    auth_str = f"{fs_creds.api_key}:X"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {"Content-Type": "application/json", "Authorization": f"Basic {encoded_auth}"}
    base_url = f"https://{FRESHSERVICE_DOMAIN}"

    # 1. Fetch all companies (departments)
    print("Fetching companies from Freshservice...")
    companies_endpoint = f"{base_url}/api/v2/departments"
    companies = get_paginated_api_request(companies_endpoint, headers, 'departments')
    if companies is None:
        print("Could not retrieve companies list from Freshservice. Aborting sync.")
        return
    print(f"Found {len(companies)} companies in Freshservice.")

    # 2. Fetch all users (requesters)
    print("\nFetching users from Freshservice...")
    users_endpoint = f"{base_url}/api/v2/requesters"
    users = get_paginated_api_request(users_endpoint, headers, 'requesters')
    if users is None:
        print("Could not retrieve users list from Freshservice. Aborting sync.")
        return
    print(f"Found {len(users)} users in Freshservice.")

    # 3. Process and prepare data for upsert
    companies_to_upsert = []
    locations_to_upsert = []
    fs_id_to_account_map = {}

    print("\nProcessing company and location data...")
    for c in companies:
        custom_fields = c.get('custom_fields', {}) or {}
        account_number = custom_fields.get(ACCOUNT_NUMBER_FIELD)
        if not account_number:
            continue

        fs_id_to_account_map[c.get('id')] = str(account_number)

        company_data = {
            "account_number": str(account_number),
            "name": c.get('name'),
            "freshservice_id": c.get('id'),
            "contract_type": custom_fields.get('type_of_client'),
            "billing_plan": custom_fields.get('plan_selected'),
            "support_level": custom_fields.get('support_level'),
            "phone_number": custom_fields.get(PHONE_NUMBER_FIELD),
            "client_start_date": custom_fields.get(CLIENT_START_DATE_FIELD),
            "domains": ', '.join(c.get('domains', [])),
            "company_owner": c.get('head_name'),
            "business_type": custom_fields.get(BUSINESS_TYPE_FIELD)
        }
        companies_to_upsert.append(company_data)

        address = custom_fields.get(ADDRESS_FIELD)
        if address:
            location_data = {
                "company_account_number": str(account_number),
                "location_name": "Main Office",
                "address": address
            }
            locations_to_upsert.append(location_data)

    users_to_upsert = []
    contacts_to_upsert = []
    processed_emails = set()

    print("\nProcessing user and contact data...")
    for user in users:
        email = user.get('primary_email')
        if not email or email in processed_emails:
            continue

        if not user.get('active', False):
            continue

        # Link user to a company via department IDs
        account_num = None
        for dept_id in (user.get('department_ids') or []):
            if dept_id in fs_id_to_account_map:
                account_num = fs_id_to_account_map[dept_id]
                break

        if not account_num:
            continue

        users_to_upsert.append({
            "company_account_number": str(account_num),
            "freshservice_id": user.get('id'),
            "full_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "email": email,
            "status": 'Active' if user.get('active') else 'Inactive',
            "date_added": user.get('created_at')
        })

        contacts_to_upsert.append({
            "company_account_number": str(account_num),
            "first_name": user.get('first_name'),
            "last_name": user.get('last_name'),
            "email": email,
            "title": user.get('job_title'),
            "work_phone": user.get('work_phone_number'),
            "mobile_phone": user.get('mobile_phone_number'),
            "status": 'Active' if user.get('active') else 'Inactive',
            "other_emails": ', '.join(user.get('other_emails', [])),
            "address": user.get('address'),
            "notes": user.get('description')
        })
        processed_emails.add(email)


    # 4. Perform bulk upserts
    with db.begin():
        if companies_to_upsert:
            print(f"\nUpserting {len(companies_to_upsert)} companies...")
            stmt = insert(models.Company).values(companies_to_upsert)
            update_cols = {c.name: c for c in stmt.excluded if c.name not in ['account_number']}
            stmt = stmt.on_conflict_do_update(index_elements=['account_number'], set_=update_cols)
            db.execute(stmt)

        if locations_to_upsert:
            print(f"Upserting {len(locations_to_upsert)} locations...")
            stmt = insert(models.ClientLocation).values(locations_to_upsert)
            update_cols = {c.name: c for c in stmt.excluded if c.name not in ['id']}
            stmt = stmt.on_conflict_do_update(index_elements=['company_account_number', 'location_name'], set_=update_cols)
            db.execute(stmt)

        if users_to_upsert:
            print(f"Upserting {len(users_to_upsert)} users...")
            stmt = insert(models.User).values(users_to_upsert)
            update_cols = {c.name: c for c in stmt.excluded if c.name not in ['id', 'freshservice_id']}
            stmt = stmt.on_conflict_do_update(index_elements=['freshservice_id'], set_=update_cols)
            db.execute(stmt)

        if contacts_to_upsert:
            print(f"Upserting {len(contacts_to_upsert)} contacts...")
            stmt = insert(models.Contact).values(contacts_to_upsert)
            update_cols = {c.name: c for c in stmt.excluded if c.name not in ['id', 'email']}
            stmt = stmt.on_conflict_do_update(index_elements=['email'], set_=update_cols)
            db.execute(stmt)

    print("--- Freshservice Data Sync Finished ---")

