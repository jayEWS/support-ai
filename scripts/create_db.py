import os
import sqlalchemy
from sqlalchemy import text

# This helper script was originally written for SQL Server only.  It now
# respects the DATABASE_URL environment variable so developers can switch to
# SQLite (or any other SQLAlchemy-supported dialect) simply by setting the
# variable before running.  If DATABASE_URL is not present we fall back to
# the legacy SQL Server localhost connection used during early development.

from app.models.models import Base

db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    # fallback to local SQL Server - keeps old behaviour if someone runs the
    # script without setting anything.
    db_url = (
        "mssql+pyodbc://sa:1@localhost:1433/master?"
        "driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes"
    )
    print("[create_db] WARNING: DATABASE_URL not set, using default SQL Server URL")

print(f"[create_db] using DATABASE_URL={db_url}")

engine = sqlalchemy.create_engine(db_url)

# Handle SQLite specially; a simple file create + metadata.create_all is
# enough, no need to try COMMIT/CREATE DATABASE logic.
if "sqlite" in db_url.lower():
    # ensure directory exists for file-based DB
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite://", "")
        # strip leading / if present
        if path.startswith("/"):
            path = path[1:]
        dirpath = os.path.dirname(path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)

    # create tables using SQLAlchemy metadata
    try:
        Base.metadata.create_all(engine)
        print(f"SQLite database initialized ({db_url})")
    except Exception as e:
        print(f"Error initializing SQLite database: {e}")

else:
    try:
        # Use autocommit for CREATE DATABASE (SQL Server specific)
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Check if database exists
            check_sql = text("SELECT name FROM sys.databases WHERE name = 'tCareEWS'")
            result = conn.execute(check_sql).fetchone()
            
            if not result:
                print("Database 'tCareEWS' not found. Creating...")
                conn.execute(text("CREATE DATABASE tCareEWS"))
                print("Database 'tCareEWS' created successfully.")
            else:
                print("Database 'tCareEWS' already exists.")
    except Exception as e:
        print(f"Error: {e}")
