"""
SaaS Seed Script
==================
Initializes default plans, feature flags, and default tenant for the SaaS platform.

Usage:
    python scripts/seed_saas.py

This is safe to run multiple times (idempotent).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager
from app.models.tenant_models import Base as TenantBase
from app.repositories.tenant_repo import TenantRepository
from app.core.logging import logger


def seed_plans(tenant_repo: TenantRepository):
    """Create the default subscription plans."""
    plans = [
        {
            "name": "Free",
            "price_monthly": 0,
            "max_agents": 1,
            "max_ai_messages": 100,
            "max_tickets": 50,
            "max_knowledge_files": 10,
            "max_storage_mb": 100,
            "features": {
                "sla_engine": False,
                "whatsapp": False,
                "live_chat": False,
                "ai_dashboard": False,
                "custom_branding": False,
                "api_access": False,
                "priority_support": False,
            },
        },
        {
            "name": "Starter",
            "price_monthly": 99,
            "max_agents": 3,
            "max_ai_messages": 1500,
            "max_tickets": 500,
            "max_knowledge_files": 50,
            "max_storage_mb": 500,
            "features": {
                "sla_engine": False,
                "whatsapp": False,
                "live_chat": True,
                "ai_dashboard": False,
                "custom_branding": False,
                "api_access": True,
                "priority_support": False,
            },
        },
        {
            "name": "Growth",
            "price_monthly": 299,
            "max_agents": 10,
            "max_ai_messages": 10000,
            "max_tickets": 2000,
            "max_knowledge_files": 200,
            "max_storage_mb": 2000,
            "features": {
                "sla_engine": True,
                "whatsapp": True,
                "live_chat": True,
                "ai_dashboard": True,
                "custom_branding": True,
                "api_access": True,
                "priority_support": False,
            },
        },
        {
            "name": "Enterprise",
            "price_monthly": 999,
            "max_agents": -1,  # Unlimited
            "max_ai_messages": -1,
            "max_tickets": -1,
            "max_knowledge_files": -1,
            "max_storage_mb": -1,
            "features": {
                "sla_engine": True,
                "whatsapp": True,
                "live_chat": True,
                "ai_dashboard": True,
                "custom_branding": True,
                "api_access": True,
                "priority_support": True,
                "dedicated_support": True,
                "sla_prediction": True,
                "escalation_prediction": True,
            },
        },
    ]

    for plan_data in plans:
        features = plan_data.pop("features")
        try:
            result = tenant_repo.create_plan(features=features, **plan_data)
            print(f"  ✅ Plan '{result['name']}' → ${result['price']}/mo")
        except Exception as e:
            print(f"  ⚠️ Plan '{plan_data['name']}': {e}")


def seed_default_tenant(tenant_repo: TenantRepository):
    """Create the default tenant for backward compatibility."""
    try:
        existing = tenant_repo.get_tenant_by_slug("default")
        if existing:
            print("  ✅ Default tenant already exists")
            return

        result = tenant_repo.create_tenant(
            name="Edgeworks Internal",
            slug="default",
            industry="Technology",
            plan_name="Enterprise",
            trial_days=0,
        )
        print(f"  ✅ Default tenant created: {result['id']}")
    except Exception as e:
        print(f"  ⚠️ Default tenant: {e}")


def seed_global_feature_flags(tenant_repo: TenantRepository):
    """Set global default feature flags."""
    defaults = {
        "sla_engine": True,
        "whatsapp": True,
        "live_chat": True,
        "ai_dashboard": False,
        "custom_branding": False,
        "api_access": True,
        "priority_support": False,
        "ai_observability": True,
        "usage_tracking": True,
    }
    for key, enabled in defaults.items():
        try:
            tenant_repo.set_feature_flag(None, key, enabled)
            status = "✅" if enabled else "⬜"
            print(f"  {status} {key}: {enabled}")
        except Exception as e:
            print(f"  ⚠️ {key}: {e}")


def main():
    if not db_manager:
        print("❌ Database not available. Check DATABASE_URL.")
        sys.exit(1)

    print("\n🚀 SaaS Seed Script")
    print("=" * 50)

    # Create new SaaS tables
    print("\n📊 Creating SaaS tables...")
    try:
        TenantBase.metadata.create_all(db_manager.engine)
        print("  ✅ All SaaS tables created/verified")
    except Exception as e:
        print(f"  ❌ Table creation failed: {e}")
        sys.exit(1)

    tenant_repo = TenantRepository(db_manager.Session)

    # Seed plans
    print("\n💰 Seeding subscription plans...")
    seed_plans(tenant_repo)

    # Seed default tenant
    print("\n🏢 Setting up default tenant...")
    seed_default_tenant(tenant_repo)

    # Seed feature flags
    print("\n🚩 Setting global feature flags...")
    seed_global_feature_flags(tenant_repo)

    print("\n" + "=" * 50)
    print("✅ SaaS seed complete!\n")


if __name__ == "__main__":
    main()
