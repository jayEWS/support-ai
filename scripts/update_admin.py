import os
from app.core.database import db_manager
from app.utils.auth_utils import get_password_hash
from app.models.models import Agent

def update_admin_email():
    session = db_manager.get_session()
    try:
        # Configuration from environment variables
        new_email = os.getenv("ADMIN_EMAIL", "admin@Support.ai")
        new_password = os.getenv("ADMIN_PASSWORD")
        
        if not new_password:
            print("⚠️  WARNING: ADMIN_PASSWORD environment variable not set. Using dev default.")
            new_password = "admin123"
            
        hashed_pw = get_password_hash(new_password)
        
        # Try to find by email
        agent = session.query(Agent).filter_by(email=new_email).first()

        if agent:
            agent.role = "admin"
            agent.hashed_password = hashed_pw
            print(f"Updated account to {new_email} with Admin role.")
        else:
            print(f"Creating fresh Admin account: {new_email}")
            new_admin = Agent(
                user_id="admin_main",
                name="System Administrator",
                email=new_email,
                role="admin",
                hashed_password=hashed_pw,
                department="Management"
            )
            session.add(new_admin)
            
        session.commit()
        print("Success.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
    finally:
        db_manager.Session.remove()

if __name__ == "__main__":
    update_admin_email()
