"""Add Email, Mobile, OutletAddress, Category columns to Users table"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager
from sqlalchemy import text

session = db_manager.get_session()
try:
    cols = [
        ("Email", "VARCHAR(255)"),
        ("Mobile", "VARCHAR(50)"),
        ("OutletAddress", "VARCHAR(500)"),
        ("Category", "VARCHAR(50)"),
    ]
    for col_name, col_type in cols:
        try:
            session.execute(text(f'ALTER TABLE app."Users" ADD COLUMN "{col_name}" {col_type}'))
            session.commit()
            print(f"  Added column: {col_name}")
        except Exception as e:
            session.rollback()
            err = str(e).lower()
            if "already exists" in err or "duplicate" in err:
                print(f"  Column already exists: {col_name}")
            else:
                print(f"  Error adding {col_name}: {e}")
    print("Migration done!")
finally:
    db_manager.Session.remove()
