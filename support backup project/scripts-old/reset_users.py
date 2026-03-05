"""Reset users with auto-generated names so they go through onboarding again."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager
from sqlalchemy import text

session = db_manager.get_session()
try:
    # Reset users whose name looks auto-generated (cust_xxx or equals their identifier)
    result = session.execute(text("""
        UPDATE app."Users" 
        SET "DisplayName" = NULL, 
            "Company" = NULL, 
            "OutletPOS" = NULL,
            "CurrentState" = 'asking_name'
        WHERE "DisplayName" = "UserID" 
           OR "DisplayName" LIKE 'cust_%'
           OR "DisplayName" LIKE 'User %'
    """))
    session.commit()
    print(f"Reset {result.rowcount} users with auto-generated names")
    
    # Also delete their messages so they start fresh
    result2 = session.execute(text("""
        DELETE FROM app."Messages" 
        WHERE "UserID" IN (
            SELECT "UserID" FROM app."Users" 
            WHERE "CurrentState" = 'asking_name'
        )
    """))
    session.commit()
    print(f"Cleaned {result2.rowcount} old messages")
except Exception as e:
    session.rollback()
    print(f"Error: {e}")
finally:
    db_manager.Session.remove()
