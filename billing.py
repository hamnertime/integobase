from collections import defaultdict
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc, extract
import calendar
from . import models, schemas

def get_billing_data_for_client(db: Session, account_number: str, year: int, month: int):
    """
    A comprehensive function to fetch all data and calculate billing details for a specific client and period.
    This is the core logic that powers the breakdown view.
    """
    client_info = db.query(models.Company).filter(models.Company.account_number == account_number).first()
    if not client_info:
        return None

    # --- 1. Fetch all raw data from the database using SQLAlchemy ---
    locations = db.query(models.ClientLocation).filter(models.ClientLocation.company_account_number == account_number).order_by(models.ClientLocation.location_name).all()
    manual_assets = db.query(models.ManualAsset).filter(models.ManualAsset.company_account_number == account_number).order_by(models.ManualAsset.hostname).all()
    manual_users = db.query(models.ManualUser).filter(models.ManualUser.company_account_number == account_number).order_by(models.ManualUser.full_name).all()
    custom_line_items = db.query(models.CustomLineItem).filter(models.CustomLineItem.company_account_number == account_number).order_by(models.CustomLineItem.name).all()
    rate_overrides = db.query(models.ClientBillingOverride).filter(models.ClientBillingOverride.company_account_number == account_number).first()
    all_tickets_this_year = db.query(models.TicketDetail).filter(models.TicketDetail.company_account_number == account_number, extract('year', models.TicketDetail.last_updated_at) == year).all()

    # Eager load related data to prevent numerous queries
    assets_raw = db.query(models.Asset).options(joinedload(models.Asset.contact_links).joinedload(models.AssetContactLink.contact)).filter(models.Asset.company_account_number == account_number).order_by(models.Asset.hostname).all()
    users_raw = db.query(models.User).options(joinedload(models.User.contact).joinedload(models.Contact.asset_links).joinedload(models.AssetContactLink.asset)).filter(models.User.company_account_number == account_number, models.User.status == 'Active').order_by(models.User.full_name).all()
    asset_overrides_raw = db.query(models.AssetBillingOverride).join(models.Asset).filter(models.Asset.company_account_number == account_number).all()
    user_overrides_raw = db.query(models.UserBillingOverride).join(models.User).filter(models.User.company_account_number == account_number).all()

    # Process relationships and create dicts for easier handling
    assets = [{'associated_contacts': ", ".join([f"{link.contact.first_name} {link.contact.last_name}" for link in asset.contact_links]), **asset.__dict__} for asset in assets_raw]
    users = [{'associated_assets': [{'hostname': link.asset.hostname, 'portal_url': link.asset.portal_url} for link in user.contact.asset_links if user.contact], 'contact_id': user.contact.id if user.contact else None, **user.__dict__} for user in users_raw]
    asset_overrides = {override.asset_id: override for override in asset_overrides_raw}
    user_overrides = {override.user_id: override for override in user_overrides_raw}

    # Determine effective billing plan
    billing_plan_name = (client_info.billing_plan or '').strip()
    if rate_overrides and rate_overrides.override_billing_plan_enabled and rate_overrides.billing_plan:
        billing_plan_name = rate_overrides.billing_plan

    contract_term = (client_info.contract_term_length or 'Month to Month').strip()
    plan_details = db.query(models.BillingPlan).filter_by(billing_plan=billing_plan_name, term_length=contract_term).first()

    if not plan_details:
        return None # Unconfigured plan

    # --- 2. Determine Effective Rates ---
    effective_rates = {c.name: getattr(plan_details, c.name) for c in plan_details.__table__.columns}
    if rate_overrides:
        for key in effective_rates:
            override_enabled_key = f'override_{key}_enabled'
            if hasattr(rate_overrides, override_enabled_key) and getattr(rate_overrides, override_enabled_key) and hasattr(rate_overrides, key):
                effective_rates[key] = getattr(rate_overrides, key)

    support_level_display = effective_rates.get('support_level', 'Billed Hourly')

    # --- 2a. Calculate Contract End Date ---
    contract_end_date_str = "N/A"
    contract_expired = False
    if client_info.contract_start_date and client_info.contract_term_length:
        years_to_add = {'1-Year': 1, '2-Year': 2, '3-Year': 3}.get(client_info.contract_term_length, 0)
        if years_to_add > 0:
            end_date = client_info.contract_start_date.replace(year=client_info.contract_start_date.year + years_to_add) - timedelta(days=1)
            contract_end_date_str = end_date.strftime('%Y-%m-%d')
            if datetime.now(timezone.utc).date() > end_date.date():
                contract_expired = True
        elif client_info.contract_term_length == 'Month to Month':
            contract_end_date_str = "Month to Month"

    # --- 3. Calculate Itemized Charges ---
    billed_assets, total_asset_charges, quantities, backup_info = _calculate_asset_charges(assets + manual_assets, asset_overrides, effective_rates)
    billed_users, total_user_charges, user_quantities = _calculate_user_charges(users + manual_users, user_overrides, effective_rates)
    quantities.update(user_quantities)
    billed_line_items, total_line_item_charges = _calculate_line_item_charges(custom_line_items, year, month)
    ticket_charge, hours_for_period, prepaid_monthly, remaining_yearly_hours, billable_hours = _calculate_ticket_charges(all_tickets_this_year, effective_rates, rate_overrides, year, month)
    backup_charge, backup_base_workstation, backup_base_server, included_tb, overage_tb, overage_charge = _calculate_backup_charges(backup_info, effective_rates)

    total_bill = total_asset_charges + total_user_charges + ticket_charge + backup_charge + total_line_item_charges

    # --- 8. Assemble Final Data Package ---
    return {
        "client": client_info, "locations": locations, "assets": assets, "manual_assets": manual_assets,
        "users": users, "manual_users": manual_users, "custom_line_items": custom_line_items,
        "tickets_for_billing_period": [t for t in all_tickets_this_year if t.last_updated_at.month == month],
        "effective_rates": effective_rates, "quantities": quantities,
        "support_level_display": support_level_display, "contract_end_date": contract_end_date_str,
        "contract_expired": contract_expired, "datto_portal_url": client_info.datto_portal_url,
        "receipt_data": {
            "total": total_bill, "total_user_charges": total_user_charges, "total_asset_charges": total_asset_charges,
            "total_line_item_charges": total_line_item_charges, "ticket_charge": ticket_charge, "backup_charge": backup_charge,
            "billed_users": billed_users, "billed_assets": billed_assets, "billed_line_items": billed_line_items,
            "hours_for_billing_period": hours_for_period, "prepaid_hours_monthly": prepaid_monthly, "billable_hours": billable_hours,
            "backup_base_workstation": backup_base_workstation, "backup_base_server": backup_base_server,
            "total_included_tb": included_tb, "overage_tb": overage_tb, "overage_charge": overage_charge,
        }
    }

def get_billing_dashboard_data(db: Session):
    # This function can be further optimized, but for now, we'll calculate for the current month
    now = datetime.now(timezone.utc)
    all_companies = db.query(models.Company).all()
    clients_data = []
    for client_info in all_companies:
        data = get_billing_data_for_client(db, client_info.account_number, now.year, now.month)
        if not data:
            clients_data.append({"name": client_info.name, "account_number": client_info.account_number, "billing_plan": "Unconfigured", "total_bill": 0})
            continue

        quantities = data['quantities']
        clients_data.append({
            "account_number": client_info.account_number, "name": client_info.name,
            "billing_plan": data['client'].billing_plan, "support_level": data['support_level_display'],
            "contract_end_date": data['contract_end_date'], "contract_expired": data['contract_expired'],
            "workstations": quantities.get('workstation', 0), "servers": quantities.get('server', 0),
            "vms": quantities.get('vm', 0), "regular_users": quantities.get('paid', 0),
            "total_backup_bytes": sum(a.get('backup_data_bytes', 0) for a in data['assets'] if a.get('backup_data_bytes')),
            "total_hours": sum(t.total_hours_spent for t in data['all_tickets_this_year']),
            "total_bill": data['receipt_data']['total']
        })
    return clients_data


# --- Helper Calculation Functions ---
def _calculate_asset_charges(all_assets, asset_overrides, effective_rates):
    billed_assets, quantities, backup_info = [], defaultdict(int), defaultdict(int)
    total_asset_charges = 0.0
    for asset in all_assets:
        is_manual = not isinstance(asset, models.Asset)
        override = asset_overrides.get(asset.id) if not is_manual else asset
        billing_type = (override.billing_type if override else None) or asset.billing_type or 'Workstation'
        cost = 0.0
        if billing_type == 'Custom': cost = float(override.custom_cost or 0.0) if override else 0.0
        elif billing_type != 'No Charge': cost = float(effective_rates.get(f"per_{billing_type.lower()}_cost", 0.0) or 0.0)
        total_asset_charges += cost
        quantities[billing_type.lower()] += 1
        billed_assets.append({'name': asset.hostname, 'type': billing_type, 'cost': cost})
        if not is_manual and asset.backup_data_bytes:
            backup_info['total_backup_bytes'] += asset.backup_data_bytes
            if asset.billing_type == 'Workstation': backup_info['backed_up_workstations'] += 1
            elif asset.billing_type in ('Server', 'VM'): backup_info['backed_up_servers'] += 1
    return billed_assets, total_asset_charges, quantities, backup_info

def _calculate_user_charges(all_users, user_overrides, effective_rates):
    billed_users, quantities = [], defaultdict(int)
    total_user_charges = 0.0
    for user in all_users:
        is_manual = not isinstance(user, models.User)
        override = user_overrides.get(user.id) if not is_manual else user
        billing_type = (override.billing_type if override else None) or 'Paid'
        cost = 0.0
        if billing_type == 'Custom': cost = float(override.custom_cost or 0.0) if override else 0.0
        elif billing_type == 'Paid': cost = float(effective_rates.get('per_user_cost', 0.0) or 0.0)
        total_user_charges += cost
        quantities[billing_type.lower()] += 1
        billed_users.append({'name': user.full_name, 'type': billing_type, 'cost': cost})
    return billed_users, total_user_charges, quantities

def _calculate_line_item_charges(custom_line_items, year, month):
    billed_line_items, total_line_item_charges = [], 0.0
    for item in custom_line_items:
        cost, item_type, fee = 0.0, None, 0.0
        if item.monthly_fee is not None:
            fee, item_type = float(item.monthly_fee), 'Recurring'
        elif item.one_off_year == year and item.one_off_month == month:
            fee, item_type = float(item.one_off_fee or 0.0), 'One-Off'
        elif item.yearly_bill_month == month:
            fee, item_type = float(item.yearly_fee or 0.0), 'Yearly'
        if item_type:
            cost = fee
            total_line_item_charges += cost
            billed_line_items.append({'name': item.name, 'type': item_type, 'cost': cost})
    return billed_line_items, total_line_item_charges

def _calculate_ticket_charges(all_tickets_this_year, effective_rates, rate_overrides, year, month):
    hours_for_period = sum(t.total_hours_spent for t in all_tickets_this_year if t.last_updated_at.month == month)
    prepaid_monthly = float((rate_overrides.prepaid_hours_monthly if rate_overrides and rate_overrides.override_prepaid_hours_monthly_enabled else 0) or 0)
    prepaid_yearly = float((rate_overrides.prepaid_hours_yearly if rate_overrides and rate_overrides.override_prepaid_hours_yearly_enabled else 0) or 0)
    hours_used_prior = sum(t.total_hours_spent for t in all_tickets_this_year if t.last_updated_at.month < month)
    remaining_yearly_hours = max(0, prepaid_yearly - hours_used_prior)
    billable_hours = max(0, max(0, hours_for_period - prepaid_monthly) - remaining_yearly_hours)
    ticket_charge = billable_hours * float(effective_rates.get('per_hour_ticket_cost', 0) or 0)
    return ticket_charge, hours_for_period, prepaid_monthly, remaining_yearly_hours, billable_hours

def _calculate_backup_charges(backup_info, effective_rates):
    total_backup_tb = backup_info['total_backup_bytes'] / (1024**4)
    included_tb = (backup_info['backed_up_workstations'] + backup_info['backed_up_servers']) * float(effective_rates.get('backup_included_tb', 1) or 1)
    overage_tb = max(0, total_backup_tb - included_tb)
    base_ws = backup_info['backed_up_workstations'] * float(effective_rates.get('backup_base_fee_workstation', 0) or 0)
    base_srv = backup_info['backed_up_servers'] * float(effective_rates.get('backup_base_fee_server', 0) or 0)
    overage_chg = overage_tb * float(effective_rates.get('backup_per_tb_fee', 0) or 0)
    total_charge = base_ws + base_srv + overage_chg
    return total_charge, base_ws, base_srv, included_tb, overage_tb, overage_chg
