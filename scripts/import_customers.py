"""
Customer Import Script
======================
Supports: Excel (.xls, .xlsx), CSV, JSON, PDF, TXT
Features:
  - Auto-detect country code for mobile numbers (default +65 Singapore)
  - Parse "Name @ Company" format from Last Name column
  - Combine First Name + Last Name intelligently
  - Bulk upsert to database

Usage:
  python scripts/import_customers.py <file_path> [--dry-run] [--country-code 65]
"""

import os
import sys
import re
import csv
import io
import json
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager
from app.core.logging import logger


# ============ COUNTRY CODE DETECTION ============

# Common country codes by prefix patterns (most used in SEA region)
COUNTRY_CODES = {
    "65": "SG",   # Singapore
    "62": "ID",   # Indonesia
    "60": "MY",   # Malaysia
    "66": "TH",   # Thailand
    "63": "PH",   # Philippines
    "84": "VN",   # Vietnam
    "855": "KH",  # Cambodia
    "856": "LA",  # Laos
    "95": "MM",   # Myanmar
    "673": "BN",  # Brunei
    "1": "US",    # USA/Canada
    "44": "UK",   # United Kingdom
    "86": "CN",   # China
    "81": "JP",   # Japan
    "82": "KR",   # South Korea
    "91": "IN",   # India
    "61": "AU",   # Australia
    "64": "NZ",   # New Zealand
    "971": "AE",  # UAE
    "852": "HK",  # Hong Kong
    "886": "TW",  # Taiwan
}

# Singapore mobile patterns (8 digits, starts with 8 or 9)
SG_MOBILE_PATTERN = re.compile(r'^[89]\d{7}$')
# Indonesia mobile patterns (9-12 digits, starts with 8)
ID_MOBILE_PATTERN = re.compile(r'^8\d{8,11}$')


def normalize_phone(raw_phone: str, default_country_code: str = "65") -> str:
    """
    Normalize phone number and auto-add country code if missing.
    
    Rules:
    1. If already has + prefix → keep as is (just clean non-digits after +)
    2. If starts with country code (e.g. 65xxxxxxxx for SG) → add +
    3. If 8 digits starting with 8/9 (SG local) → add +65
    4. If starts with 0 (local format) → replace 0 with country code
    5. Fallback → add default country code
    """
    if not raw_phone:
        return ""
    
    # Convert float to int string (Excel stores numbers as float)
    try:
        if isinstance(raw_phone, float):
            raw_phone = str(int(raw_phone))
        else:
            raw_phone = str(raw_phone)
    except (ValueError, OverflowError):
        raw_phone = str(raw_phone)
    
    # Clean: remove spaces, dashes, parentheses, dots
    phone = re.sub(r'[\s\-\(\)\.]+', '', raw_phone.strip())
    
    # Already has + prefix
    if phone.startswith('+'):
        digits = '+' + re.sub(r'[^\d]', '', phone[1:])
        return digits if len(digits) > 4 else ""
    
    # Remove any remaining non-digit chars
    digits = re.sub(r'[^\d]', '', phone)
    
    if not digits:
        return ""
    
    # Check if already has known country code prefix
    for cc in sorted(COUNTRY_CODES.keys(), key=len, reverse=True):
        if digits.startswith(cc) and len(digits) > len(cc) + 5:
            return f"+{digits}"
    
    # Starts with 0 → local format, replace 0 with country code
    if digits.startswith('0'):
        return f"+{default_country_code}{digits[1:]}"
    
    # Singapore local: 8 digits starting with 8 or 9
    if SG_MOBILE_PATTERN.match(digits):
        return f"+65{digits}"
    
    # Indonesia local: starts with 8, 9-12 digits
    if ID_MOBILE_PATTERN.match(digits) and default_country_code == "62":
        return f"+62{digits}"
    
    # Fallback: add default country code
    return f"+{default_country_code}{digits}"


# ============ NAME @ COMPANY PARSING ============

def parse_name_company(first_name: str, last_name: str) -> tuple:
    """
    Parse name and company from the "Name @ Company" format.
    
    Patterns found in data:
    - Last Name: "Jiabao @ Edgeworks"         → name=Jiabao, company=Edgeworks
    - Last Name: "@Cafe & Meal Muji"           → name=(from first_name), company=Cafe & Meal Muji
    - Last Name: "Regina@ Kopi & Tarts"        → name=Regina, company=Kopi & Tarts
    - First Name: "Bryan", Last Name: "@Cafe"  → name=Bryan, company=Cafe
    - First Name: "SYCLE Pete ltd @"           → name=SYCLE Pete ltd, company=""
    
    Returns: (display_name, company)
    """
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    
    name = ""
    company = ""
    
    # Case 1: Last Name has @ pattern
    if last and '@' in last:
        # Split on @
        parts = last.split('@', 1)
        before_at = parts[0].strip()
        after_at = parts[1].strip() if len(parts) > 1 else ""
        
        if before_at and after_at:
            # "Jiabao @ Edgeworks" → name=Jiabao, company=Edgeworks
            name = before_at
            company = after_at
        elif after_at and not before_at:
            # "@Cafe & Meal Muji" → name from first_name, company=Cafe & Meal Muji
            name = first
            company = after_at
        elif before_at and not after_at:
            # "Name @" → name=Name, company=""
            name = before_at
        
        # Clean up "Mr", "Mrs", etc from name
        name = re.sub(r'^(Mr|Mrs|Ms|Dr|Mdm)\s+', '', name, flags=re.IGNORECASE).strip()
        
    # Case 2: First Name has @ pattern
    elif first and '@' in first:
        parts = first.split('@', 1)
        before_at = parts[0].strip()
        after_at = parts[1].strip() if len(parts) > 1 else ""
        
        if before_at:
            name = before_at
        if after_at:
            company = after_at
        
        # Also use Last Name if available and no company yet
        if last and not company:
            company = last
    
    # Case 3: No @ sign - use fields directly
    else:
        if first and last:
            name = f"{first} {last}"
        elif first:
            name = first
        elif last:
            name = last
        # Company stays empty (will use Outlet or Column1 if available)
    
    # Final cleanup
    name = name.strip().strip('@').strip()
    company = company.strip().strip('@').strip()
    
    # If name is still empty, try first_name
    if not name and first:
        name = first.strip().strip('@').strip()
    
    return name, company


# ============ FILE READERS ============

def read_excel(file_path: str) -> list:
    """Read .xls or .xlsx file"""
    import pandas as pd
    df = pd.read_excel(file_path)
    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]
    return df.to_dict('records')


def read_csv(file_path: str) -> list:
    """Read CSV file"""
    import pandas as pd
    # Try different encodings
    for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            df.columns = [str(c).strip() for c in df.columns]
            return df.to_dict('records')
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode CSV file with any supported encoding")


def read_json(file_path: str) -> list:
    """Read JSON file (array of objects or object with data key)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # Try common keys
        for key in ['data', 'customers', 'records', 'items', 'results']:
            if key in data and isinstance(data[key], list):
                return data[key]
        # Single record
        return [data]
    return []


def read_pdf(file_path: str) -> list:
    """Read PDF file - extract tables or text lines"""
    try:
        import pdfplumber
        rows = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                # Try table extraction first
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if not table:
                            continue
                        headers = [str(h or '').strip().lower() for h in table[0]]
                        for row in table[1:]:
                            if row:
                                record = {headers[i]: str(v or '').strip() for i, v in enumerate(row) if i < len(headers)}
                                rows.append(record)
                else:
                    # Fallback: extract text lines
                    text = page.extract_text()
                    if text:
                        lines = text.strip().split('\n')
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            # Try to parse "name phone company" pattern
                            parts = re.split(r'\t+|\s{2,}', line)
                            if len(parts) >= 2:
                                rows.append({
                                    'name': parts[0],
                                    'phone': parts[1] if len(parts) > 1 else '',
                                    'company': parts[2] if len(parts) > 2 else '',
                                })
        return rows
    except ImportError:
        # Fallback to PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            rows = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    lines = text.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        parts = re.split(r'\t+|\s{2,}', line)
                        if len(parts) >= 2:
                            rows.append({
                                'name': parts[0],
                                'phone': parts[1] if len(parts) > 1 else '',
                                'company': parts[2] if len(parts) > 2 else '',
                            })
            return rows
        except ImportError:
            raise ImportError("Install pdfplumber or PyPDF2 for PDF support: pip install pdfplumber")


def read_text(file_path: str) -> list:
    """Read plain text file - expects tab/comma separated or one-per-line"""
    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if not lines:
        return rows
    
    # Detect delimiter
    first_line = lines[0].strip()
    if '\t' in first_line:
        delimiter = '\t'
    elif ',' in first_line:
        delimiter = ','
    elif '|' in first_line:
        delimiter = '|'
    else:
        delimiter = None
    
    if delimiter:
        # First line might be header
        headers_line = lines[0].strip().split(delimiter)
        has_header = any(h.strip().lower() in ('name', 'nama', 'phone', 'mobile', 'company', 'email', 'id', 'identifier') 
                        for h in headers_line)
        
        if has_header:
            headers = [h.strip().lower() for h in headers_line]
            for line in lines[1:]:
                parts = line.strip().split(delimiter)
                if parts:
                    record = {headers[i]: parts[i].strip() for i in range(min(len(headers), len(parts)))}
                    rows.append(record)
        else:
            # No header - assume name, phone, company order
            for line in lines:
                parts = line.strip().split(delimiter)
                if parts:
                    rows.append({
                        'name': parts[0].strip(),
                        'phone': parts[1].strip() if len(parts) > 1 else '',
                        'company': parts[2].strip() if len(parts) > 2 else '',
                    })
    else:
        # One item per line - treat as name
        for line in lines:
            line = line.strip()
            if line:
                rows.append({'name': line})
    
    return rows


def read_file(file_path: str) -> list:
    """Read file based on extension"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in ('.xls', '.xlsx'):
        return read_excel(file_path)
    elif ext == '.csv':
        return read_csv(file_path)
    elif ext == '.json':
        return read_json(file_path)
    elif ext == '.pdf':
        return read_pdf(file_path)
    elif ext in ('.txt', '.text', '.tsv'):
        return read_text(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .xls, .xlsx, .csv, .json, .pdf, .txt")


# ============ COLUMN MAPPING ============

def normalize_row(row: dict) -> dict:
    """Normalize column names from various formats to standard keys"""
    r = {}
    for k, v in row.items():
        if v is None or (isinstance(v, float) and str(v) == 'nan'):
            continue
        key = str(k).strip().lower().replace(' ', '_')
        r[key] = v
    return r


def extract_fields(row: dict, default_country_code: str = "65") -> dict:
    """Extract standardized fields from a normalized row"""
    r = normalize_row(row)
    
    # --- Extract raw fields ---
    account_id = r.get('account_id') or r.get('id') or r.get('identifier') or r.get('customer_id', '')
    first_name = r.get('first_name') or r.get('firstname', '')
    last_name = r.get('last_name') or r.get('lastname') or r.get('name') or r.get('nama') or r.get('customer_name') or r.get('full_name', '')
    email = r.get('email') or r.get('e-mail', '')
    mobile = r.get('mobile') or r.get('phone') or r.get('nomor') or r.get('telepon') or r.get('whatsapp') or r.get('mobile_number') or r.get('phone_number', '')
    company_raw = r.get('company') or r.get('perusahaan', '')
    outlet = r.get('outlet') or r.get('outlet_pos') or r.get('toko', '')
    position = r.get('position') or r.get('jabatan', '')
    column1 = r.get('column1', '')  # Category: Retail/FNB
    remark = r.get('remark') or r.get('remarks') or r.get('note') or r.get('notes', '')
    
    # --- Parse Name @ Company ---
    display_name, company_from_at = parse_name_company(
        str(first_name) if first_name else '',
        str(last_name) if last_name else ''
    )
    
    # --- Determine Company ---
    # Priority: explicit Company column > @ parsed > Outlet > Column1
    company = ''
    if company_raw and str(company_raw).strip() and str(company_raw) != 'nan':
        company = str(company_raw).strip()
    elif company_from_at:
        company = company_from_at
    elif outlet and str(outlet).strip() and str(outlet) != 'nan':
        company = str(outlet).strip()
    
    # --- Determine Outlet ---
    outlet_final = ''
    if outlet and str(outlet).strip() and str(outlet) != 'nan':
        outlet_final = str(outlet).strip()
    elif company_from_at:
        outlet_final = company_from_at
    
    # --- Normalize Phone ---
    phone = normalize_phone(mobile, default_country_code)
    
    # --- Determine Identifier ---
    # Priority: phone > account_id > generated from name
    identifier = ''
    if phone:
        identifier = phone
    elif account_id and str(account_id).strip():
        identifier = str(account_id).strip()
    elif display_name:
        identifier = f"imp_{display_name.lower().replace(' ', '_')}"
    
    # --- Position from Column1 if available ---
    if not position and column1 and str(column1) != 'nan':
        position = str(column1).strip()
    
    return {
        'identifier': identifier,
        'name': display_name,
        'company': company,
        'outlet_pos': outlet_final or company,
        'position': position,
        'email': str(email).strip() if email and str(email) != 'nan' else '',
        'account_id': str(account_id).strip() if account_id else '',
    }


# ============ MAIN IMPORT ============

def import_customers(file_path: str, default_country_code: str = "65", dry_run: bool = False):
    """
    Import customers from file to database.
    """
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return
    
    print(f"{'='*60}")
    print(f"  CUSTOMER IMPORT")
    print(f"{'='*60}")
    print(f"  File: {file_path}")
    print(f"  Format: {os.path.splitext(file_path)[1]}")
    print(f"  Default Country Code: +{default_country_code}")
    print(f"  Mode: {'DRY RUN (no DB changes)' if dry_run else 'LIVE IMPORT'}")
    print(f"{'='*60}")
    print()
    
    # Read file
    print("[1/3] Reading file...")
    try:
        rows = read_file(file_path)
    except Exception as e:
        print(f"[ERROR] Failed to read file: {e}")
        return
    
    print(f"  Found {len(rows)} rows")
    print()
    
    # Process rows
    print("[2/3] Processing rows...")
    imported = 0
    skipped = 0
    errors = []
    
    for i, row in enumerate(rows, 1):
        try:
            fields = extract_fields(row, default_country_code)
            
            name = fields['name']
            identifier = fields['identifier']
            
            if not name and not identifier:
                skipped += 1
                continue
            
            if not identifier:
                identifier = f"imp_{i}"
            
            if not name:
                name = f"Customer {identifier[-6:]}"
            
            # Preview in dry run
            if dry_run and imported < 20:
                phone_display = identifier if identifier.startswith('+') else '-'
                print(f"  [{i:4d}] {name:<30s} | {fields['company']:<30s} | {phone_display:<15s} | {fields['position']}")
            
            if not dry_run:
                db_manager.create_or_update_user(
                    identifier=identifier,
                    name=name,
                    company=fields['company'],
                    position=fields['position'],
                    outlet_pos=fields['outlet_pos'],
                    state="complete"
                )
            
            imported += 1
            
            # Progress
            if i % 500 == 0:
                print(f"  ... processed {i}/{len(rows)} rows ({imported} imported)")
                
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")
            skipped += 1
    
    # Summary
    print()
    print(f"{'='*60}")
    print(f"  IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"  Total rows:    {len(rows)}")
    print(f"  Imported:      {imported}")
    print(f"  Skipped:       {skipped}")
    if errors:
        print(f"  Errors:        {len(errors)}")
        for err in errors[:10]:
            print(f"    - {err}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more")
    print(f"{'='*60}")
    
    if dry_run:
        print()
        print("  This was a DRY RUN. No data was written to database.")
        print("  Run again without --dry-run to import for real.")


# ============ CLI ============

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import customers from file to database")
    parser.add_argument("file", help="Path to file (Excel, CSV, JSON, PDF, TXT)")
    parser.add_argument("--dry-run", action="store_true", help="Preview import without writing to DB")
    parser.add_argument("--country-code", default="65", help="Default country code (default: 65 for Singapore)")
    
    args = parser.parse_args()
    import_customers(args.file, args.country_code, args.dry_run)
