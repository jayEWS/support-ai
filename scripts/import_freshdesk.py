"""
Import Freshdesk ticket exports (Excel) into the database.

Usage:
    python scripts/import_freshdesk.py [--folder PATH] [--dry-run]

Default folder: D:\Project\support-portal-edgeworks\Customer
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import pandas as pd
from datetime import datetime
from app.core.database import db_manager
from app.core.logging import logger

DEFAULT_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Customer")

# Files to skip (subset of another file)
SKIP_FILES = {"2023 tickets.xlsx"}  # subset of "2023 tickets - Copy.xlsx"

def parse_datetime(val):
    """Parse various datetime formats from Freshdesk exports."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None
    val_str = str(val).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%b %d, %Y %I:%M %p",     # Dec 13, 2024 12:41 PM
        "%b %d, %Y at %I:%M %p",  # Dec 13, 2024 at 12:41 PM
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt)
        except (ValueError, TypeError):
            continue
    # Try pandas parser as fallback
    try:
        return pd.to_datetime(val_str).to_pydatetime()
    except Exception:
        return None

def safe_str(val, max_len=None):
    """Convert to string, return None for NaN/empty."""
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() == "nan":
        return None
    if max_len:
        s = s[:max_len]
    return s

def safe_int(val):
    """Convert to int, return 0 for NaN/empty."""
    if pd.isna(val) or val is None:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

def process_file(filepath: str, dry_run: bool = False):
    """Process a single Freshdesk export Excel file."""
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Processing: {filename}")
    print(f"{'='*60}")

    if filename in SKIP_FILES:
        print(f"  ⏭️  Skipping (subset of another file)")
        return 0, 0, 0, 0

    df = pd.read_excel(filepath)
    print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")

    # Normalize column names (strip whitespace)
    df.columns = [c.strip() for c in df.columns]

    # --- Extract unique contacts ---
    contacts_data = []
    seen_contacts = set()
    for _, row in df.iterrows():
        contact_id = safe_str(row.get("Contact ID"))
        # If Contact ID is empty, generate from Full name (2023 format)
        if not contact_id:
            full_name = safe_str(row.get("Full name"))
            if full_name:
                contact_id = full_name  # Use full name as contact ID
            else:
                continue
        if contact_id in seen_contacts:
            continue
        seen_contacts.add(contact_id)
        contacts_data.append({
            "freshdesk_id": contact_id,
            "full_name": safe_str(row.get("Full name"), 255),
            "email": safe_str(row.get("Email"), 255),
            "work_phone": safe_str(row.get("Work phone"), 50),
            "mobile_phone": safe_str(row.get("Mobile phone"), 50),
            "company_name": safe_str(row.get("Company Name"), 255),
            "industry": safe_str(row.get("Industry"), 100),
            "timezone": safe_str(row.get("Time zone"), 50),
            "language": safe_str(row.get("Language"), 10),
            "account_tier": safe_str(row.get("Account tier"), 50),
            "health_score": safe_str(row.get("Health score"), 50),
        })

    print(f"  Unique contacts in file: {len(contacts_data)}")

    # --- Extract tickets ---
    tickets_data = []
    for _, row in df.iterrows():
        tid = safe_int(row.get("Ticket ID"))
        if not tid:
            continue
        contact_id = safe_str(row.get("Contact ID"))
        # Fallback: use Full name as contact_id if Contact ID is empty
        if not contact_id:
            contact_id = safe_str(row.get("Full name"))
        tickets_data.append({
            "ticket_id": tid,
            "subject": safe_str(row.get("Subject")),
            "status": safe_str(row.get("Status"), 30),
            "priority": safe_str(row.get("Priority"), 20),
            "source": safe_str(row.get("Source"), 30),
            "ticket_type": safe_str(row.get("Type"), 100),
            "agent": safe_str(row.get("Agent"), 100),
            "group_name": safe_str(row.get("Group"), 100),
            "tags": safe_str(row.get("Tags")),
            "summary": safe_str(row.get("Summary")),
            "product": safe_str(row.get("Product"), 100),
            "contact_id": contact_id,
            "created_time": parse_datetime(row.get("Created time")),
            "due_by_time": parse_datetime(row.get("Due by Time")),
            "resolved_time": parse_datetime(row.get("Resolved time")),
            "closed_time": parse_datetime(row.get("Closed time")),
            "last_update_time": parse_datetime(row.get("Last update time")),
            "initial_response_time": parse_datetime(row.get("Initial response time")),
            "first_response_hrs": safe_str(row.get("First response time (in hrs)"), 30),
            "resolution_hrs": safe_str(row.get("Resolution time (in hrs)"), 30),
            "agent_interactions": safe_int(row.get("Agent interactions")),
            "customer_interactions": safe_int(row.get("Customer interactions")),
            "resolution_status": safe_str(row.get("Resolution status"), 30),
            "first_response_status": safe_str(row.get("First response status"), 30),
            "survey_results": safe_str(row.get("Survey results"), 50),
            "csat_score": safe_str(row.get("Customer Satisfactory Survey"), 50),
        })

    print(f"  Tickets in file: {len(tickets_data)}")

    if dry_run:
        print("  🔍 Dry run - no data inserted")
        return len(contacts_data), 0, len(tickets_data), 0

    # --- Upsert contacts ---
    c_ins, c_upd, c_err = db_manager.bulk_upsert_freshdesk_contacts(contacts_data)
    print(f"  Contacts: {c_ins} inserted, {c_upd} updated, {c_err} errors")

    # --- Upsert tickets ---
    t_ins, t_upd, t_err = db_manager.bulk_upsert_freshdesk_tickets(tickets_data)
    print(f"  Tickets:  {t_ins} inserted, {t_upd} updated, {t_err} errors")

    return c_ins + c_upd, c_err, t_ins + t_upd, t_err

def update_contact_ticket_counts():
    """Update total_tickets count for each contact based on imported tickets."""
    print("\n📊 Updating contact ticket counts...")
    from sqlalchemy import func as sqlfunc
    session = db_manager.get_session()
    try:
        from app.models.models import FreshdeskContact, FreshdeskTicket
        # Get counts per contact
        counts = session.query(
            FreshdeskTicket.contact_id,
            sqlfunc.count(FreshdeskTicket.id)
        ).group_by(FreshdeskTicket.contact_id).all()

        updated = 0
        for contact_id, count in counts:
            if contact_id:
                contact = session.query(FreshdeskContact).filter_by(freshdesk_id=contact_id).first()
                if contact:
                    contact.total_tickets = count
                    updated += 1
        session.commit()
        print(f"  Updated ticket counts for {updated} contacts")
    except Exception as e:
        session.rollback()
        print(f"  ❌ Error updating counts: {e}")
    finally:
        db_manager.Session.remove()


def main():
    parser = argparse.ArgumentParser(description="Import Freshdesk ticket exports into database")
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help="Folder containing Excel files")
    parser.add_argument("--dry-run", action="store_true", help="Preview without inserting")
    args = parser.parse_args()

    folder = args.folder
    if not os.path.exists(folder):
        print(f"❌ Folder not found: {folder}")
        sys.exit(1)

    # Find Excel files
    files = sorted([f for f in os.listdir(folder) if f.endswith(".xlsx")])
    if not files:
        print(f"❌ No .xlsx files found in {folder}")
        sys.exit(1)

    print(f"📁 Source folder: {folder}")
    print(f"📄 Found {len(files)} Excel files: {files}")
    if args.dry_run:
        print("🔍 DRY RUN MODE - no data will be written")
    print()

    total_contacts, total_contact_err = 0, 0
    total_tickets, total_ticket_err = 0, 0

    for f in files:
        filepath = os.path.join(folder, f)
        c_ok, c_err, t_ok, t_err = process_file(filepath, dry_run=args.dry_run)
        total_contacts += c_ok
        total_contact_err += c_err
        total_tickets += t_ok
        total_ticket_err += t_err

    if not args.dry_run:
        update_contact_ticket_counts()

    print(f"\n{'='*60}")
    print(f"✅ IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  Contacts processed: {total_contacts} (errors: {total_contact_err})")
    print(f"  Tickets processed:  {total_tickets} (errors: {total_ticket_err})")


if __name__ == "__main__":
    main()
