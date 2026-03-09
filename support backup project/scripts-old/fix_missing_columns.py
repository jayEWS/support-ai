"""Fix missing columns in Users table"""
import psycopg2

DB_URL = "postgresql://postgres.wjsaltebtbmnysgcdsoh:****************@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Check existing columns
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_schema='app' AND table_name='Users'
    ORDER BY ordinal_position
""")
existing = [r[0] for r in cur.fetchall()]
print(f"Existing columns: {existing}")

# Add missing columns
columns_to_add = {
    "Position": "VARCHAR(100)",
    "OutletPOS": "VARCHAR(100)", 
    "CurrentState": "VARCHAR(50)",
}

for col_name, col_type in columns_to_add.items():
    if col_name not in existing:
        sql = f'ALTER TABLE app."Users" ADD COLUMN "{col_name}" {col_type}'
        print(f"Adding column: {col_name}...")
        cur.execute(sql)
    else:
        print(f"Column {col_name} already exists")

conn.commit()

# Verify
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_schema='app' AND table_name='Users'
    ORDER BY ordinal_position
""")
print(f"Final columns: {[r[0] for r in cur.fetchall()]}")

conn.close()
print("Done!")
