import os
import sqlalchemy
from sqlalchemy import text

# use DATABASE_URL so this helper can run against whichever backend is active
db_url = os.environ.get(
    "DATABASE_URL",
    'mssql+pyodbc://sa:1@localhost:1433/tCareEWS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes'
)

if "sqlite" in db_url.lower():
    print("[fix_table] SQLite detected; migration not required or must be handled manually.")
    exit(0)

try:
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        # Check if column exists first
        check_sql = text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'app' AND TABLE_NAME = 'Tickets' AND COLUMN_NAME = 'AsanaTaskID'")
        result = conn.execute(check_sql).fetchone()
        
        if not result:
            print("Adding AsanaTaskID column...")
            conn.execute(text("ALTER TABLE app.Tickets ADD AsanaTaskID NVARCHAR(100)"))
            print("Column added.")
        else:
            print("Column already exists.")
except Exception as e:
    print(f"Error: {e}")
