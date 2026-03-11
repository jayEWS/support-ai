"""
Clean up duplicate dbo tables and verify app schema is in sync with models.
The supportportal database has tables in both [app] and [dbo] schemas.
Only [app] schema is used by the application - dbo tables are leftovers.
"""
from sqlalchemy import create_engine, text, inspect

DB_URL = "mssql+pyodbc://sa:1@localhost/supportportal?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes"
engine = create_engine(DB_URL, isolation_level="AUTOCOMMIT")

with engine.connect() as conn:
    # Get all dbo tables
    dbo_tables = conn.execute(text("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)).fetchall()
    
    print(f"Found {len(dbo_tables)} tables in [dbo] schema to clean up:")
    
    # Check which dbo tables have data
    for (tbl,) in dbo_tables:
        count = conn.execute(text(f"SELECT COUNT(*) FROM dbo.[{tbl}]")).scalar()
        status = f"({count} rows)" if count > 0 else "(empty)"
        print(f"  dbo.{tbl} {status}")
    
    # Get app schema tables for comparison
    app_tables = conn.execute(text("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = 'app' AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)).fetchall()
    app_table_names = {t[0] for t in app_tables}
    dbo_table_names = {t[0] for t in dbo_tables}
    
    print(f"\n=== Comparison ===")
    print(f"  [app] schema tables: {len(app_table_names)}")
    print(f"  [dbo] schema tables: {len(dbo_table_names)}")
    
    # Tables in dbo but not in app (would be lost if dropped)
    dbo_only = dbo_table_names - app_table_names
    if dbo_only:
        print(f"\n  ⚠ Tables ONLY in [dbo] (not in [app]): {dbo_only}")
    
    # Tables in both
    both = dbo_table_names & app_table_names
    print(f"  Duplicate tables in both schemas: {len(both)}")
    
    # Check for data in dbo tables that are duplicated
    print(f"\n=== Dropping {len(dbo_table_names)} [dbo] duplicate tables ===")
    
    # Need to drop in correct order (FKs first)
    # First, get all FK constraints in dbo schema
    fks = conn.execute(text("""
        SELECT fk.name, OBJECT_NAME(fk.parent_object_id) as table_name
        FROM sys.foreign_keys fk
        JOIN sys.schemas s ON fk.schema_id = s.schema_id
        WHERE s.name = 'dbo'
    """)).fetchall()
    
    for fk_name, table_name in fks:
        try:
            conn.execute(text(f"ALTER TABLE dbo.[{table_name}] DROP CONSTRAINT [{fk_name}]"))
            print(f"  Dropped FK: {fk_name} on dbo.{table_name}")
        except Exception as e:
            print(f"  ⚠ Could not drop FK {fk_name}: {e}")
    
    # Now drop the tables
    for (tbl,) in dbo_tables:
        try:
            conn.execute(text(f"DROP TABLE dbo.[{tbl}]"))
            print(f"  ✓ Dropped dbo.{tbl}")
        except Exception as e:
            print(f"  ✗ Could not drop dbo.{tbl}: {e}")
    
    # Verify final state
    remaining = conn.execute(text("""
        SELECT TABLE_SCHEMA, COUNT(*) as cnt
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        GROUP BY TABLE_SCHEMA
    """)).fetchall()
    
    print(f"\n=== Final State ===")
    for schema, cnt in remaining:
        print(f"  [{schema}]: {cnt} tables")
    
    print("\n✓ Database cleanup complete!")
