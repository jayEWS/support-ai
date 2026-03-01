import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import db_manager
from app.models.models import Base, Agent, Role, Permission, User, Message, Ticket, ChatSession, ChatMessage, AuditLog, KnowledgeMetadata, AuthMFAChallenge, AuthRefreshToken
from app.utils.auth_utils import get_password_hash
from sqlalchemy import text

def cleanup_and_setup_admin():
    session = db_manager.get_session()
    try:
        print("🧹 Clearing mock data...")
        
        # ... (rest of the table skipping)
        tables_to_clear = [
            "app.UserRoles",
            "app.RolePermissions",
            "app.UserPermissions",
            "app.ChatMessages",
            "app.ChatSessions",
            "app.CSATSurveys",
            "app.TicketQueue",
            "app.Tickets",
            "app.PortalMessages",
            "app.Users",
            "app.AuditLogs",
            "app.AuthMFAChallenges",
            "app.AuthRefreshTokens",
            "app.KnowledgeMetadata",
            "app.AgentPresence",
            "app.Agents",
        ]
        
        for table in tables_to_clear:
            try:
                session.execute(text(f"DELETE FROM {table}"))
                print(f"✅ Cleared {table}")
            except Exception as e:
                print(f"❌ Failed to clear {table}: {e}")
        
        session.commit()
        
        print("\n👑 Setting up System Admin...")
        
        # 1. Ensure 'System Admin' role exists
        admin_role = db_manager.create_role("System Admin", "Full system access")
        
        # 2. Create Jay
        jay_data = {
            "user_id": "Jay",
            "name": "Jay",
            "email": "jay@edgeworks.com.sg",
            "department": "Management"
        }
        
        agent_dict = db_manager.create_or_get_agent(**jay_data)
        if agent_dict:
            # Set password from environment variable
            admin_password = os.getenv("ADMIN_PASSWORD")
            if not admin_password:
                print("⚠️  WARNING: ADMIN_PASSWORD env var not set. Using temporary dev default.")
                admin_password = "ChangeMe123!"
            hashed_pw = get_password_hash(admin_password)
            db_manager.update_agent_auth("Jay", hashed_pw)
            
            # 3. Assign System Admin role
            db_manager.assign_role_to_agent("Jay", "System Admin")
            print(f"✅ Success: Jay (jay@edgeworks.com.sg) is now a System Admin.")
            print("🔑 Password set from ADMIN_PASSWORD env var (or temporary default)")
        else:
            print("❌ Failed to create agent Jay.")
            
    except Exception as e:
        session.rollback()
        print(f"💥 Global cleanup error: {e}")
    finally:
        db_manager.Session.remove()

if __name__ == "__main__":
    cleanup_and_setup_admin()
