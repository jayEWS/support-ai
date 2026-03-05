"""Drop orphan Freshdesk tables from database - one-time cleanup script."""
import os
import psycopg2

def main():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    
    cur.execute('DROP TABLE IF EXISTS "FreshdeskTickets" CASCADE;')
    cur.execute('DROP TABLE IF EXISTS "FreshdeskContacts" CASCADE;')
    conn.commit()
    
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Remaining tables ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")
    
    conn.close()
    print("\nFreshdesk tables dropped successfully.")

if __name__ == "__main__":
    main()
