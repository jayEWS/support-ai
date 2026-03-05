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
from app.models.models import USE_APP_SCHEMA


# Tables that need tenant_id column added (without schema prefix — added dynamically)
TABLE_NAMES = [
    "Users",
    "Tickets",
    "PortalMessages",
    "Agents",
    "KnowledgeMetadata",
    "ChatSessions",
    "ChatMessages",
    "AuditLogs",
    "Macros",
    "SLARules",
    "TicketQueue",
    "CSATSurveys",
    "AgentPresence",
    "WhatsAppMessages",
    "SystemSettings",
]

def _qualified(table: str) -> str:
    """Return schema-qualified table name for SQL Server, plain for PostgreSQL/SQLite."""
    return f"app.{table}" if USE_APP_SCHEMA else f"\"{table}\""


def get_default_tenant_id():
    """Get the default tenant ID from the Tenants table."""
    with db_manager.get_session() as session:
        tbl = "app.Tenants" if USE_APP_SCHEMA else "\"Tenants\""
        result = session.execute(
            text(f"SELECT \"TenantID\" FROM {tbl} WHERE \"Slug\" = 'default'")
        ).fetchone()
        if result:
            return result[0]
    return "default"


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    session = db_manager.get_session()
    try:
        schema = "app" if USE_APP_SCHEMA else None
        inspector = inspect(db_manager.engine)
        columns = [c["name"] for c in inspector.get_columns(table_name, schema=schema)]
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

    qualified = _qualified(table_name)
    session = db_manager.get_session()
    try:
        # Add nullable column — VARCHAR for Postgres/SQLite, NVARCHAR for SQL Server
        col_type = "NVARCHAR(36)" if USE_APP_SCHEMA else "VARCHAR(36)"
        session.execute(text(
            f"ALTER TABLE {qualified} ADD \"TenantID\" {col_type} NULL"
        ))
        session.commit()
        print(f"  ➕ {table_name}: TenantID column added")

        # Populate with default tenant
        session.execute(text(
            f"UPDATE {qualified} SET \"TenantID\" = :tid WHERE \"TenantID\" IS NULL"
        ), {"tid": default_tenant_id})
        session.commit()
        print(f"  📝 {table_name}: Existing rows set to default tenant")

        # Add index for tenant-scoped queries
        idx_name = f"IX_{table_name}_TenantID"
        try:
            if USE_APP_SCHEMA:
                session.execute(text(
                    f"CREATE NONCLUSTERED INDEX {idx_name} ON {qualified} (TenantID)"
                ))
            else:
                session.execute(text(
                    f"CREATE INDEX {idx_name} ON {qualified} (\"TenantID\")"
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
    print(f"\n🔧 Step 3: Adding TenantID to {len(TABLE_NAMES)} tables...")
    for table in TABLE_NAMES:
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
