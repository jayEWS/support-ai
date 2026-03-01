import os
import sqlalchemy
from sqlalchemy import text

# Respect DATABASE_URL so this upgrade helper can be run against either
# local SQL Server or a SQLite demo database.  For SQLite we simply warn and
# exit because the SQL script contains Server-specific statements.
db_url = os.environ.get(
    "DATABASE_URL",
    'mssql+pyodbc://sa:1@localhost:1433/tCareEWS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes'
)
print(f"[apply_upgrade] connecting to {db_url}")
try:
    engine = sqlalchemy.create_engine(db_url)

    if "sqlite" in db_url.lower():
        print("[apply_upgrade] SQLite detected - upgrade script is SQL Server specific, skipping.")
        exit(0)
    with open('upgrade_db.sql', 'r') as f:
        sql_script = f.read()
    
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        # SQL Server 'GO' is not a standard SQL command, it's for management tools.
        # We split by 'GO' to run each block individually.
        commands = sql_script.split('GO')
        for cmd in commands:
            if cmd.strip():
                conn.execute(text(cmd))
    print("SQL Server World-Class Upgrade Complete.")
except Exception as e:
    print(f"Upgrade Error: {e}")
