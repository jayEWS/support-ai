"""Quick script to inspect the 'jay' database schema for SQL Expert debugging."""
import pyodbc
import sys

conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=34.87.147.22;DATABASE=support_portal;UID=sqlserver;PWD=Edgew0rks!DB2026#Secure;TrustServerCertificate=yes;Encrypt=yes'
try:
    conn = pyodbc.connect(conn_str)
except Exception as e:
    print(f"Connection failed: {e}")
    import sys; sys.exit(1)

cursor = conn.cursor()

# Get column details for POS-related tables
target_tables = ['pos_transactions', 'pos_devices', 'pos_issues', 'inventory_items', 'vouchers', 'Invoices', 'outlets']
for tbl in target_tables:
    print(f"\n{'=' * 60}")
    print(f"COLUMNS in [app].[{tbl}]:")
    print(f"{'=' * 60}")
    try:
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA='app' AND TABLE_NAME='{tbl}' 
            ORDER BY ORDINAL_POSITION
        """)
        for row in cursor.fetchall():
            size = f"({row.CHARACTER_MAXIMUM_LENGTH})" if row.CHARACTER_MAXIMUM_LENGTH else ""
            null = "NULL" if row.IS_NULLABLE == "YES" else "NOT NULL"
            print(f"  {row.COLUMN_NAME:<30} {row.DATA_TYPE}{size:<15} {null}")
    except Exception as e:
        print(f"  Error: {e}")

print()
print("=" * 60)
print("Searching for tables like Transaction/Cash/Payment/Sale/Order:")
print("=" * 60)
cursor.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_TYPE='BASE TABLE' 
    AND (TABLE_NAME LIKE '%Transaction%' OR TABLE_NAME LIKE '%Cash%' OR TABLE_NAME LIKE '%Payment%' 
         OR TABLE_NAME LIKE '%Sale%' OR TABLE_NAME LIKE '%Order%' OR TABLE_NAME LIKE '%Draw%'
         OR TABLE_NAME LIKE '%Detail%' OR TABLE_NAME LIKE '%Header%')
    ORDER BY TABLE_NAME
""")
matches = cursor.fetchall()
for row in matches:
    print(f"  [{row.TABLE_SCHEMA}].[{row.TABLE_NAME}]")
if not matches:
    print("  (no matches)")

print()
print("=" * 60)
print("STORED PROCEDURES:")
print("=" * 60)
cursor.execute("SELECT SCHEMA_NAME(schema_id) as [schema], name FROM sys.procedures ORDER BY name")
procs = cursor.fetchall()
for row in procs:
    print(f"  [{row[0]}].[{row[1]}]")
if not procs:
    print("  (none)")
print(f"\n  Total: {len(procs)} procedures")

print()
print("=" * 60)
print("VIEWS:")
print("=" * 60)
cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS ORDER BY TABLE_SCHEMA, TABLE_NAME")
for row in cursor.fetchall():
    print(f"  [{row.TABLE_SCHEMA}].[{row.TABLE_NAME}]")

conn.close()
