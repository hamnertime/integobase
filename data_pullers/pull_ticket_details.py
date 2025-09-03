import requests
import base64
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from .. import models

# --- Configuration ---
FRESHSERVICE_DOMAIN = "integotecllc.freshservice.com"
ACCOUNT_NUMBER_FIELD = "account_number"
MAX_RETRIES = 3
DEFAULT_TICKET_HOURS = 0.25  # 15 minutes

# --- Helper Functions ---
def get_latest_ticket_timestamp(db: Session) -> datetime:
    """Gets the timestamp of the most recently updated ticket in the local DB."""
    latest_timestamp = db.scalar(select(func.max(models.TicketDetail.last_updated_at)))
    if latest_timestamp:
        # Add a second to avoid re-fetching the last record
        return latest_timestamp + timedelta(seconds=1)
    else:
        # If no tickets exist, sync for the past year
        print("No existing tickets found. Performing initial sync for the past year.")
        return datetime.now(timezone.utc) - timedelta(days=365)

def get_fs_company_map_from_api(base_url: str, headers: dict) -> dict | None:
    """Fetches all companies from Freshservice and returns a map of fs_id to account_number."""
    all_companies = []
    page = 1
    print("Fetching company map directly from Freshservice API for ticket linking...")
    while True:
        params = {'page': page, 'per_page': 100}
        try:
            response = requests.get(f"{base_url}/api/v2/departments", headers=headers, params=params, timeout=90)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"  -> Rate limit hit, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            data = response.json()
            companies_on_page = data.get('departments', [])
            if not companies_on_page:
                break
            all_companies.extend(companies_on_page)
            page += 1
            time.sleep(0.5)
        except requests.exceptions.RequestException as e:
            print(f"FATAL error fetching companies for mapping: {e}")
            return None

    fs_id_to_account_map = {}
    for company in all_companies:
        fs_id = company.get('id')
        custom_fields = company.get('custom_fields', {}) or {}
        account_number = custom_fields.get(ACCOUNT_NUMBER_FIELD)
        if fs_id and account_number:
            fs_id_to_account_map[fs_id] = str(account_number)

    print(f"Successfully built a map of {len(fs_id_to_account_map)} companies.")
    return fs_id_to_account_map

def get_updated_tickets(base_url: str, headers: dict, since_timestamp: datetime) -> list | None:
    """Fetches closed tickets that have been updated since a given timestamp."""
    all_tickets = []
    since_str = since_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
    # Status 5 is 'Closed' in Freshservice
    query = f"(updated_at:>'{since_str}' AND status:5)"
    page = 1
    print(f"Fetching CLOSED tickets updated since {since_str}...")

    while True:
        params = {'query': f'"{query}"', 'page': page, 'per_page': 100}
        try:
            response = requests.get(f"{base_url}/api/v2/tickets/filter", headers=headers, params=params, timeout=90)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"  -> Rate limit hit, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            data = response.json()
            tickets_on_page = data.get('tickets', [])
            if not tickets_on_page:
                break
            all_tickets.extend(tickets_on_page)
            print(f"  -> Fetched page {page}, total tickets so far: {len(all_tickets)}")
            page += 1
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            print(f"FATAL error fetching tickets: {e}")
            return None
    return all_tickets

def get_time_entries_for_ticket(base_url: str, headers: dict, ticket_id: int) -> float:
    """Calculates the total hours spent on a ticket from its time entries."""
    total_hours = 0
    endpoint = f"{base_url}/api/v2/tickets/{ticket_id}/time_entries"
    for _ in range(MAX_RETRIES):
        try:
            response = requests.get(endpoint, headers=headers, timeout=60)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"    [!] Rate limit on ticket #{ticket_id}. Retrying in {retry_after}s...")
                time.sleep(retry_after)
                continue
            if response.status_code == 404:
                return 0  # Ticket might have been deleted
            response.raise_for_status()
            time_entries = response.json().get('time_entries', [])
            for entry in time_entries:
                time_str = entry.get('time_spent', '00:00')
                try:
                    h, m = map(int, time_str.split(':'))
                    total_hours += h + (m / 60.0)
                except ValueError:
                    # Handle cases like "01:23:45"
                    parts = list(map(int, time_str.split(':')))
                    if len(parts) == 3:
                        h, m, s = parts
                        total_hours += h + m / 60.0 + s / 3600.0
            return total_hours
        except requests.exceptions.RequestException as e:
            print(f"  -> WARN: Could not fetch time for ticket {ticket_id}: {e}")
            time.sleep(5)
    print(f"  -> ERROR: Failed to fetch time for ticket {ticket_id} after {MAX_RETRIES} retries.")
    return 0

def sync_ticket_details_data(db: Session, full_sync: bool = False):
    """
    Main function to sync ticket details from Freshservice into the database.
    """
    print("--- Starting Ticket Details Sync ---")

    fs_creds = db.query(models.ApiKey).filter(models.ApiKey.service == 'freshservice').first()
    if not fs_creds:
        print("Freshservice credentials not found in the database. Aborting sync.")
        return

    auth_str = f"{fs_creds.api_key}:X"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {"Content-Type": "application/json", "Authorization": f"Basic {encoded_auth}"}
    base_url = f"https://{FRESHSERVICE_DOMAIN}"

    company_map = get_fs_company_map_from_api(base_url, headers)
    if not company_map:
        print("Could not build company map from Freshservice API. Aborting ticket sync.")
        return

    if full_sync:
        print("Full sync requested. Clearing all existing ticket data...")
        db.query(models.TicketDetail).delete()
        db.commit()
        last_sync_time = datetime.now(timezone.utc) - timedelta(days=365)
    else:
        last_sync_time = get_latest_ticket_timestamp(db)

    tickets = get_updated_tickets(base_url, headers, last_sync_time)
    if tickets is None:
        print("Aborting due to ticket fetch failure.")
        return

    tickets_to_upsert = []
    if not tickets:
        print("No new or updated tickets found.")
    else:
        print(f"\nProcessing {len(tickets)} tickets and fetching their time entries...")
        for ticket in tickets:
            department_id = ticket.get('department_id')
            account_number = company_map.get(department_id)
            if not account_number:
                continue

            ticket_id = ticket['id']
            print(f"  -> Processing Ticket #{ticket_id}...")

            total_hours = get_time_entries_for_ticket(base_url, headers, ticket_id)
            if total_hours == 0:
                total_hours = DEFAULT_TICKET_HOURS
                print(f"    -> No time entries found. Assigning default {DEFAULT_TICKET_HOURS} hours.")

            tickets_to_upsert.append({
                "ticket_id": ticket_id,
                "company_account_number": account_number,
                "subject": ticket.get('subject', 'No Subject'),
                "last_updated_at": ticket.get('updated_at'),
                "closed_at": ticket.get('updated_at'), # For closed tickets, updated_at is the closed time
                "total_hours_spent": total_hours
            })

    if tickets_to_upsert:
        print(f"\nUpserting details for {len(tickets_to_upsert)} tickets...")
        stmt = insert(models.TicketDetail).values(tickets_to_upsert)
        update_cols = {c.name: c for c in stmt.excluded if c.name not in ['ticket_id']}
        stmt = stmt.on_conflict_do_update(index_elements=['ticket_id'], set_=update_cols)
        db.execute(stmt)
        db.commit()

    print("--- Ticket Details Sync Finished ---")

