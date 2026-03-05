"""Quick cleanup script to reset tenant data for re-seeding."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager
from sqlalchemy import text

s = db_manager.get_session()
try:
    s.execute(text('DELETE FROM "FeatureFlags" WHERE "TenantID" IS NOT NULL'))
    s.execute(text('DELETE FROM "TenantUsers"'))
    s.execute(text('DELETE FROM "Subscriptions"'))
    s.execute(text('DELETE FROM "Tenants"'))
    s.commit()
    print("Cleared tenant data for re-seed.")
except Exception as e:
    s.rollback()
    print(f"Error: {e}")
finally:
    db_manager.Session.remove()
