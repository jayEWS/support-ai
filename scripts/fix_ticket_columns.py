"""Add missing columns to Supabase DB tables."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager
from sqlalchemy import text

session = db_manager.get_session()
try:
    # Add missing columns - each in a try/except so we skip if already exists
    columns_to_add = [
        ('app."Tickets"', '"TicketType"', 'VARCHAR(50) DEFAULT \'Support\''),
        ('app."Tickets"', '"AsanaTaskID"', 'VARCHAR(100)'),
        ('app."Tickets"', '"DueAt"', 'TIMESTAMP'),
    ]
    
    for table, column, col_type in columns_to_add:
        try:
            session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
            session.commit()
            print(f"Added {column} to {table}")
        except Exception as e:
            session.rollback()
            if 'already exists' in str(e):
                print(f"  {column} already exists in {table} - OK")
            else:
                print(f"  Error adding {column}: {e}")

    print("\nDone!")
except Exception as e:
    session.rollback()
    print(f"Error: {e}")
finally:
    db_manager.Session.remove()
