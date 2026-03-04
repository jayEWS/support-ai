"""
Migration script: Add 'Language' column to Users table.
Run once on production to support multi-language feature.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Database

def migrate():
    db = Database()
    engine = db.engine
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(
            __import__('sqlalchemy').text(
                """SELECT column_name FROM information_schema.columns 
                   WHERE table_schema = 'app' AND table_name = 'Users' AND column_name = 'Language'"""
            )
        )
        if result.fetchone():
            print("Column 'Language' already exists in Users table. Nothing to do.")
            return
        
        # Add the column
        conn.execute(__import__('sqlalchemy').text(
            'ALTER TABLE app."Users" ADD COLUMN "Language" VARCHAR(10) NULL'
        ))
        conn.commit()
        print("Successfully added 'Language' column to Users table.")

if __name__ == "__main__":
    migrate()
