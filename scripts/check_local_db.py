"""Check local SQL Server 2025 connection and list tables."""
from sqlalchemy import create_engine, text

DB_URL = "mssql+pyodbc://sa:1@localhost/supportportal?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes"

engine = create_engine(DB_URL)
with engine.connect() as conn:
    ver = conn.execute(text("SELECT @@VERSION")).scalar()
    print(f"Connected: {ver[:120]}")
    print("---")
    
    rows = conn.execute(text(
        "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_SCHEMA, TABLE_NAME"
    )).fetchall()
    
    if rows:
        print(f"Found {len(rows)} tables:")
        for r in rows:
            print(f"  [{r[0]}].{r[1]}")
    else:
        print("No tables found - database is empty.")
    
    print("---")
    print("Database ready for migrations!")
