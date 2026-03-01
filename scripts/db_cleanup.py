import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import db_manager
from app.models.models import Base, Agent, Role, Permission, User, Message, Ticket, ChatSession, ChatMessage, AuditLog, KnowledgeMetadata, AuthMFAChallenge, AuthRefreshToken
from app.utils.auth_utils import get_password_hash
from sqlalchemy import text

def cleanup_and_setup_admin():
    session = db_manager.get_session()
    try:
        # PostgreSQL: Ensure schema exists
        if "postgresql" in settings.DATABASE_URL:
            session.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
            session.commit()

        print("🧹 Clearing all tables defined in models...")
        
        # Get tables in reverse order to handle foreign keys
        for table in reversed(Base.metadata.sorted_tables):
            try:
                # Use quoted names for Postgres
                schema_prefix = f'"{table.schema}".' if table.schema else ""
                table_name = f'{schema_prefix}"{table.name}"'
                session.execute(text(f"DELETE FROM {table_name}"))
                print(f"✅ Cleared {table_name}")
            except Exception as e:
                print(f"⚠️  Skipped {table.name}: {e}")
        
        session.commit()
        
        print("\n👑 Setting up System Admins...")
        
        # 1. Ensure 'System Admin' role exists
        db_manager.create_role("System Admin", "Full system access")
        
        # 2. Setup Admins
        admins = [
            {"user_id": "Jay", "name": "Jay", "email": "jay@edgeworks.com.sg", "dept": "Management"},
            {"user_id": "SupportAdmin", "name": "Support", "email": "support@edgeworks.com.sg", "dept": "Management"}
        ]
        
        admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
        hashed_pw = get_password_hash(admin_password)

        for admin in admins:
            agent_dict = db_manager.create_or_get_agent(
                user_id=admin["user_id"],
                name=admin["name"],
                email=admin["email"],
                department=admin["dept"]
            )
            if agent_dict:
                db_manager.update_agent_auth(admin["user_id"], hashed_pw)
                db_manager.assign_role_to_agent(admin["user_id"], "System Admin")
                print(f"✅ Success: {admin['name']} ({admin['email']}) is now a System Admin.")
            else:
                print(f"❌ Failed to create agent: {admin['name']}")
            
    except Exception as e:
        session.rollback()
        print(f"💥 Global cleanup error: {e}")
    finally:
        db_manager.Session.remove()

if __name__ == "__main__":
    cleanup_and_setup_admin()
