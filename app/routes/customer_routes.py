"""
Customer Management API Routes
==============================
Endpoints for listing, creating, importing, and deleting portal customers.
Extracted from main.py for architectural modularity.
"""

import csv
import io
import re
import tempfile
import os
import shutil
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request
from fastapi.responses import JSONResponse

from app.core.database import db_manager
from app.core.auth_deps import require_agent
from app.core.logging import logger
from app.core.config import settings

router = APIRouter(prefix="/api/customers", tags=["Customers"])


def _require_db():
    if db_manager is None:
        raise HTTPException(
            status_code=503, 
            detail="Database unavailable. Please check DATABASE_URL and DB server connectivity."
        )
    return db_manager


# --- Masking Helpers ---

def _mask_phone(phone: str) -> str:
    """Mask phone number: +6281234****90"""
    if not phone or len(phone) < 6:
        return phone
    visible_start = min(5, len(phone) - 2)
    visible_end = 2
    masked_len = len(phone) - visible_start - visible_end
    if masked_len <= 0:
        return phone
    return phone[:visible_start] + "*" * masked_len + phone[-visible_end:]


def _mask_email(email: str) -> str:
    """Mask email: jo***@gm***.com"""
    if not email or "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    parts = domain.rsplit(".", 1)
    domain_name = parts[0]
    tld = "." + parts[1] if len(parts) > 1 else ""
    masked_local = local[:2] + "***" if len(local) > 2 else local[0] + "***"
    masked_domain = domain_name[:2] + "***" if len(domain_name) > 2 else domain_name[0] + "***"
    return f"{masked_local}@{masked_domain}{tld}"


def _mask_customer(c: dict) -> dict:
    """Mask sensitive fields (phone and email) in a customer dict."""
    c = dict(c)
    if c.get("mobile"):
        c["mobile"] = _mask_phone(c["mobile"])
    if c.get("email"):
        c["email"] = _mask_email(c["email"])
    return c


# --- Endpoints ---

@router.get("")
async def list_customers(
    agent: Annotated[dict, Depends(require_agent)], 
    unmask: bool = False,
    page: int = 1,
    per_page: int = 50
):
    """List all customers with pagination. Phone/email masked unless admin requests unmask=true."""
    is_admin = agent.get("role") == "admin"
    db = _require_db()
    customers = db.get_all_users(page=page, per_page=per_page)
    if not (is_admin and unmask):
        customers = [_mask_customer(c) for c in customers]
    return customers


@router.get("/{identifier}")
async def get_customer(
    identifier: str, 
    agent: Annotated[dict, Depends(require_agent)], 
    unmask: bool = False
):
    """Get single customer details. Phone/email masked unless admin requests unmask=true."""
    is_admin = agent.get("role") == "admin"
    db = _require_db()
    user = db.get_user(identifier)
    if not user:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    if not (is_admin and unmask):
        user = _mask_customer(user)
    return user


@router.get("/{identifier}/context")
async def get_customer_context(
    identifier: str, 
    agent: Annotated[dict, Depends(require_agent)]
):
    """Get full customer context: profile, ticket history, stats, recurring patterns."""
    return _require_db().get_customer_context(identifier)


@router.get("/{identifier}/tickets")
async def get_customer_tickets(
    identifier: str, 
    agent: Annotated[dict, Depends(require_agent)]
):
    """Get all tickets for a customer."""
    return _require_db().get_tickets_by_user(identifier)


@router.post("")
async def create_customer(
    request: Request, 
    agent: Annotated[dict, Depends(require_agent)]
):
    """Create or update a single customer."""
    data = await request.json()
    identifier = data.get("identifier") or data.get("phone") or data.get("id")
    name = data.get("name")
    company = data.get("company", "")
    outlet = data.get("outlet") or data.get("outlet_pos") or company
    position = data.get("position", "")
    email = data.get("email", "")
    mobile = data.get("mobile", "")
    category = data.get("category", "")
    outlet_address = data.get("outlet_address", "")
    
    if not identifier or not name:
        return JSONResponse({"error": "identifier and name are required"}, status_code=400)
    
    _require_db().create_or_update_user(
        identifier, 
        name=name, 
        company=company, 
        position=position, 
        outlet_pos=outlet, 
        state="complete", 
        email=email, 
        mobile=mobile, 
        category=category, 
        outlet_address=outlet_address
    )
    return {"status": "success", "identifier": identifier, "name": name}


@router.post("/import")
async def import_customers(
    agent: Annotated[dict, Depends(require_agent)],
    file: UploadFile = File(...)
):
    """Bulk import customers from Excel, CSV, JSON, PDF, or TXT file."""
    # Note: local imports to avoid circular dependencies and keep scripts isolated
    from scripts.import_customers import extract_fields
    
    filename = file.filename.lower()
    content = await file.read()
    rows = []

    try:
        if filename.endswith(".csv"):
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)

        elif filename.endswith((".xlsx", ".xls")):
            import pandas as pd
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1], delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                df = pd.read_excel(tmp_path)
                df.columns = [str(c).strip() for c in df.columns]
                rows = df.to_dict("records")
            finally:
                os.unlink(tmp_path)

        elif filename.endswith(".json"):
            text = content.decode("utf-8")
            import json as _json
            data = _json.loads(text)
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                for key in ["data", "customers", "records", "items", "results"]:
                    if key in data and isinstance(data[key], list):
                        rows = data[key]
                        break
                if not rows:
                    rows = [data]

        elif filename.endswith(".pdf"):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                from scripts.import_customers import read_pdf
                rows = read_pdf(tmp_path)
            finally:
                os.unlink(tmp_path)

        elif filename.endswith((".txt", ".text", ".tsv")):
            text = content.decode("utf-8-sig")
            lines = text.strip().split("\n")
            if not lines:
                return JSONResponse({"error": "File is empty"}, status_code=400)
            
            first_line = lines[0].strip()
            delimiter = "\t" if "\t" in first_line else ("," if "," in first_line else ("|" if "|" in first_line else None))
            
            if delimiter:
                headers_line = lines[0].strip().split(delimiter)
                has_header = any(h.strip().lower() in ("name", "nama", "phone", "mobile", "company", "email") for h in headers_line)
                if has_header:
                    headers = [h.strip().lower() for h in headers_line]
                    for line in lines[1:]:
                        parts = line.strip().split(delimiter)
                        if parts:
                            rows.append({headers[i]: parts[i].strip() for i in range(min(len(headers), len(parts)))})
                else:
                    for line in lines:
                        parts = line.strip().split(delimiter)
                        if parts:
                            rows.append({"name": parts[0], "phone": parts[1] if len(parts) > 1 else "", "company": parts[2] if len(parts) > 2 else ""})
            else:
                for line in lines:
                    if line.strip():
                        rows.append({"name": line.strip()})
        else:
            return JSONResponse({"error": "Unsupported format. Supported: Excel, CSV, JSON, PDF, TXT"}, status_code=400)

    except Exception as e:
        return JSONResponse({"error": f"Failed to parse file: {str(e)}"}, status_code=400)

    if not rows:
        return JSONResponse({"error": "File is empty or has no data rows"}, status_code=400)

    imported = 0
    skipped = 0
    errors_list = []
    db = _require_db()

    for i, row in enumerate(rows, 1):
        try:
            fields = extract_fields(row, default_country_code="65")
            name = fields["name"]
            identifier = fields["identifier"]

            if not name and not identifier:
                skipped += 1
                continue

            if not identifier:
                identifier = f"imp_{i}"
            if not name:
                name = f"Customer {identifier[-6:]}"

            db.create_or_update_user(
                identifier=identifier,
                name=name,
                email=fields["email"],
                mobile=fields["mobile"],
                company=fields["company"],
                position=fields["position"],
                outlet_pos=fields["outlet_pos"],
                outlet_address=fields.get("outlet_address", ""),
                category=fields.get("category", ""),
                state="complete"
            )
            imported += 1
        except Exception as e:
            errors_list.append(f"Row {i}: {str(e)}")
            skipped += 1

    return {
        "status": "success",
        "imported": imported,
        "skipped": skipped,
        "total_rows": len(rows),
        "errors": errors_list[:10]
    }


@router.delete("/{identifier}")
async def delete_customer(
    identifier: str, 
    agent: Annotated[dict, Depends(require_agent)]
):
    """Delete a customer record."""
    db = _require_db()
    user = db.get_user(identifier)
    if not user:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    try:
        session = db.get_session()
        from app.models.models import User
        # P0 Fix: Use tenant-scoped query instead of session.get() to prevent cross-tenant deletion
        query = session.query(User).filter_by(identifier=identifier)
        tenant_id = getattr(session, '_tenant_id', None)
        if hasattr(User, 'tenant_id') and agent.get('tenant_id'):
            query = query.filter(User.tenant_id == agent['tenant_id'])
        u = query.first()
        if u:
            session.delete(u)
            session.commit()
        return {"status": "success", "message": f"Deleted customer {identifier}"}
    except Exception as e:
        logger.error(f"Delete customer error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.Session.remove()
