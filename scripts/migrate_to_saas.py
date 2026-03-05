"""
SaaS Migration Script
=======================
Adds tenant_id columns to existing operational tables for multi-tenant isolation.

This script:
1. Creates the new SaaS tables (Tenants, Plans, etc.)
2. Adds tenant_id column to existing tables
3. Populates default tenant_id for existing data
4. Creates indexes for tenant-scoped queries

Usage:
    python scripts/migrate_to_saas.py

IMPORTANT: Run seed_saas.py FIRST to create plans and default tenant.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from app.core.database import db_manager
from app.core.config import settings
from app.core.logging import logger


# Tables that need tenant_id column added
TABLES_TO_MIGRATE = [
    "app.Users",
    "app.Tickets",
    "app.PortalMessages",
    "app.Agents",
    "app.KnowledgeMetadata",
    "app.ChatSessions",
    "app.ChatMessages",
    "app.AuditLogs",
    "app.Macros",
    "app.SLARules",
    "app.TicketQueue",
    "app.CSATSurveys",
    "app.AgentPresence",
    "app.WhatsAppMessages",
    "app.SystemSettings",
]


def get_default_tenant_id():
    """Get the default tenant ID from the Tenants table."""
    with db_manager.get_session() as session:
        result = session.execute(
            text("SELECT TenantID FROM app.Tenants WHERE Slug = 'default'")
        ).fetchone()
        if result:
            return result[0]
    return "default"


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    session = db_manager.get_session()
    try:
        # Parse schema and table
        parts = table_name.split(".")
        schema = parts[0] if len(parts) > 1 else "app"
        table = parts[-1]

        inspector = inspect(db_manager.engine)
        columns = [c["name"] for c in inspector.get_columns(table, schema=schema)]
        return column_name in columns
    except Exception as e:
        logger.warning(f"Could not check column {column_name} in {table_name}: {e}")
        return False
    finally:
        db_manager.Session.remove()


def add_tenant_column(table_name: str, default_tenant_id: str):
    """Add TenantID column to an existing table and populate with default."""
    if column_exists(table_name, "TenantID"):
        print(f"  ⏭️  {table_name}: TenantID already exists")
        return

    session = db_manager.get_session()
    try:
        # Add nullable column first
        session.execute(text(
            f"ALTER TABLE {table_name} ADD TenantID NVARCHAR(36) NULL"
        ))
        session.commit()
        print(f"  ➕ {table_name}: TenantID column added")

        # Populate with default tenant
        session.execute(text(
            f"UPDATE {table_name} SET TenantID = :tid WHERE TenantID IS NULL"
        ), {"tid": default_tenant_id})
        session.commit()
        print(f"  📝 {table_name}: Existing rows set to default tenant")

        # Add index for tenant-scoped queries
        idx_name = f"IX_{table_name.replace('.', '_')}_TenantID"
        try:
            session.execute(text(
                f"CREATE NONCLUSTERED INDEX {idx_name} ON {table_name} (TenantID)"
            ))
            session.commit()
            print(f"  📇 {table_name}: Index created")
        except Exception:
            print(f"  ⚠️  {table_name}: Index may already exist")

    except Exception as e:
        session.rollback()
        print(f"  ❌ {table_name}: Error - {e}")
    finally:
        db_manager.Session.remove()


def create_saas_tables():
    """Create the new SaaS infrastructure tables."""
    from app.models.tenant_models import Base as TenantBase
    try:
        TenantBase.metadata.create_all(db_manager.engine)
        print("  ✅ SaaS tables created/verified")
    except Exception as e:
        print(f"  ❌ SaaS table creation failed: {e}")
        return False
    return True


def main():
    if not db_manager:
        print("❌ Database not available. Check DATABASE_URL.")
        sys.exit(1)

    print("\n🔄 SaaS Migration Script")
    print("=" * 60)

    # Step 1: Create SaaS tables
    print("\n📊 Step 1: Creating SaaS infrastructure tables...")
    if not create_saas_tables():
        sys.exit(1)

    # Step 2: Get default tenant
    print("\n🏢 Step 2: Resolving default tenant...")
    try:
        default_tid = get_default_tenant_id()
        print(f"  ✅ Default tenant: {default_tid}")
    except Exception as e:
        print(f"  ⚠️  No default tenant found ({e}). Run seed_saas.py first.")
        default_tid = "default"

    # Step 3: Add tenant_id to existing tables
    print(f"\n🔧 Step 3: Adding TenantID to {len(TABLES_TO_MIGRATE)} tables...")
    for table in TABLES_TO_MIGRATE:
        add_tenant_column(table, default_tid)

    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("\nNext steps:")
    print("  1. Run: python scripts/seed_saas.py  (if not already done)")
    print("  2. Set MULTI_TENANT_ENABLED=True in .env")
    print("  3. Restart the application")
    print()


if __name__ == "__main__":
    main()
