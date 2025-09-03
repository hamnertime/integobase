import requests
import json
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from .. import models
from ..config import settings

# --- Configuration ---
DATTO_VARIABLE_NAME = "AccountNumber"
BACKUP_UDF_ID = 6
SERVER_TYPE_UDF_ID = 7

# --- Helper Functions ---
def get_datto_access_token(api_endpoint: str, api_key: str, api_secret_key: str) -> str | None:
    """Gets an OAuth access token from the Datto RMM API."""
    token_url = f"{api_endpoint}/auth/oauth/token"
    payload = {'grant_type': 'password', 'username': api_key, 'password': api_secret_key}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': 'Basic cHVibGljLWNsaWVudDpwdWJsaWM='}
    try:
        response = requests.post(token_url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error getting Datto access token: {e}")
        return None

def get_paginated_api_request(api_endpoint: str, access_token: str, api_request_path: str) -> list | None:
    """Handles paginated API requests to Datto RMM."""
    all_items = []
    next_page_url = f"{api_endpoint}/api{api_request_path}"
    headers = {'Authorization': f'Bearer {access_token}'}
    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=headers, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            items_on_page = response_data.get('items') or response_data.get('sites') or response_data.get('devices')
            if items_on_page is None:
                break
            all_items.extend(items_on_page)
            next_page_url = response_data.get('pageDetails', {}).get('nextPageUrl') or response_data.get('nextPageUrl')
            time.sleep(0.5)  # Be respectful of API limits
        except requests.exceptions.RequestException as e:
            print(f"An error occurred during paginated API request for {api_request_path}: {e}")
            return None
    return all_items

def get_site_variable(api_endpoint: str, access_token: str, site_uid: str, variable_name: str) -> str | None:
    """Fetches a specific variable for a given site."""
    request_url = f"{api_endpoint}/api/v2/site/{site_uid}/variables"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get(request_url, headers=headers, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        variables = response.json().get("variables", [])
        for var in variables:
            if var.get("name") == variable_name:
                return var.get("value")
        return None
    except requests.exceptions.RequestException:
        return None

def format_timestamp(ms_timestamp: int | None) -> datetime | None:
    """Converts a millisecond timestamp to a timezone-aware datetime object."""
    if ms_timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        return None

def sync_datto_data(db: Session):
    """
    Main function to sync all sites and devices from Datto RMM into the database.
    """
    print("--- Starting Datto RMM Data Sync ---")

    # Get Datto credentials from settings
    datto_creds = db.query(models.ApiKey).filter(models.ApiKey.service == 'datto').first()
    if not datto_creds:
        print("Datto RMM credentials not found in the database. Aborting sync.")
        return

    # 1. Get Access Token
    token = get_datto_access_token(datto_creds.api_endpoint, datto_creds.api_key, datto_creds.api_secret)
    if not token:
        print("Failed to obtain Datto RMM access token. Aborting sync.")
        return

    # 2. Get All Sites
    sites = get_paginated_api_request(datto_creds.api_endpoint, token, "/v2/account/sites")
    if sites is None:
        print("Could not retrieve sites list from Datto RMM. Aborting sync.")
        return
    print(f"Found {len(sites)} total sites in Datto RMM.")

    assets_to_upsert = []

    # 3. Process each site and its devices
    print("\n--- Processing Sites and Devices ---")
    for i, site in enumerate(sites, 1):
        site_uid, site_name = site.get('uid'), site.get('name')
        if not site_uid:
            continue

        print(f"-> ({i}/{len(sites)}) Processing site: '{site_name}'")

        account_number = get_site_variable(datto_creds.api_endpoint, token, site_uid, DATTO_VARIABLE_NAME)
        if not account_number:
            print(f"   -> Skipping: No '{DATTO_VARIABLE_NAME}' variable found.")
            continue

        # Update the corresponding company record
        company_to_update = db.query(models.Company).filter(models.Company.account_number == account_number).first()
        if company_to_update:
            company_to_update.datto_site_uid = site.get('uid')
            company_to_update.datto_portal_url = site.get('portalUrl')
            print(f"   -> Linked site UID to company with account number {account_number}.")
        else:
            print(f"   -> Warning: No company found with account number '{account_number}'. Devices for this site will be skipped.")
            continue

        # Fetch devices for the site
        devices_in_site = get_paginated_api_request(datto_creds.api_endpoint, token, f"/v2/site/{site_uid}/devices")
        if not devices_in_site:
            print("   -> No devices found in this site.")
            continue

        print(f"   -> Found {len(devices_in_site)} devices. Preparing for DB upsert.")
        for device in devices_in_site:
            udf_dict = device.get('udf', {}) or {}

            # Determine billing type
            billing_type = "Workstation"
            if (device.get('deviceType') or {}).get('category') == 'Server':
                server_type_from_udf = udf_dict.get(f'udf{SERVER_TYPE_UDF_ID}')
                billing_type = 'VM' if server_type_from_udf == 'VM' else 'Server'

            # Parse backup data
            backup_data_bytes = 0
            value_str = udf_dict.get(f'udf{BACKUP_UDF_ID}')
            if value_str and value_str.isdigit():
                backup_data_bytes = int(value_str)

            asset_data = {
                "datto_uid": device.get('uid'),
                "company_account_number": account_number,
                "hostname": device.get('hostname'),
                "friendly_name": device.get('description'),
                "device_type": (device.get('deviceType') or {}).get('category'),
                "billing_type": billing_type,
                "operating_system": device.get('operatingSystem'),
                "status": "Active", # Assuming all synced devices are active
                "date_added": format_timestamp(device.get('creationDate')),
                "backup_data_bytes": backup_data_bytes,
                "internal_ip": device.get('intIpAddress'),
                "external_ip": device.get('extIpAddress'),
                "last_logged_in_user": device.get('lastLoggedInUser'),
                "domain": device.get('domain'),
                "is_64_bit": device.get('a64Bit'),
                "is_online": device.get('online'),
                "last_seen": format_timestamp(device.get('lastSeen')),
                "last_reboot": format_timestamp(device.get('lastReboot')),
                "last_audit_date": format_timestamp(device.get('lastAuditDate')),
                "udf_data": json.dumps(udf_dict),
                "antivirus_data": json.dumps(device.get('antivirus')),
                "patch_management_data": json.dumps(device.get('patchManagement')),
                "portal_url": device.get('portalUrl'),
                "web_remote_url": device.get('webRemoteUrl')
            }
            assets_to_upsert.append(asset_data)

    # 4. Bulk upsert all collected assets
    if assets_to_upsert:
        print(f"\nUpserting {len(assets_to_upsert)} assets into the database...")
        stmt = insert(models.Asset).values(assets_to_upsert)

        # Define the columns to update on conflict
        update_columns = {col.name: col for col in stmt.excluded if col.name not in ["id", "datto_uid"]}

        stmt = stmt.on_conflict_do_update(
            index_elements=['datto_uid'],
            set_=update_columns
        )
        db.execute(stmt)

    db.commit()
    print("--- Datto RMM Data Sync Finished ---")

