"""Inspect local SQL Server 2025 supportportal database and compare with models."""
from sqlalchemy import create_engine, text, inspect

DB_URL = "mssql+pyodbc://sa:1@localhost/supportportal?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes"
engine = create_engine(DB_URL)

with engine.connect() as conn:
    # Check alembic_version
    print("=== Alembic Version ===")
    try:
        ver = conn.execute(text("SELECT version_num FROM app.alembic_version")).fetchone()
        print(f"  Current: {ver[0] if ver else 'NONE'}")
    except Exception as e:
        print(f"  No alembic_version table: {e}")
    
    # List all tables in [app] schema with columns
    print("\n=== Tables in [app] schema ===")
    rows = conn.execute(text("""
        SELECT t.TABLE_NAME, 
               STRING_AGG(c.COLUMN_NAME + ' (' + c.DATA_TYPE + ')', ', ') as columns
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c 
            ON t.TABLE_NAME = c.TABLE_NAME AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
        WHERE t.TABLE_SCHEMA = 'app' AND t.TABLE_TYPE = 'BASE TABLE'
        GROUP BY t.TABLE_NAME
        ORDER BY t.TABLE_NAME
    """)).fetchall()
    
    for r in rows:
        print(f"\n  [{r[0]}]")
        cols = r[1].split(', ')
        for col in sorted(cols):
            print(f"    - {col}")

    # Count rows per table
    print("\n=== Row Counts ===")
    for r in rows:
        try:
            count = conn.execute(text(f"SELECT COUNT(*) FROM app.[{r[0]}]")).scalar()
            if count > 0:
                print(f"  app.{r[0]}: {count} rows")
        except:
            pass
