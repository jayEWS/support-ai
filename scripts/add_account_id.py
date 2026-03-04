"""
Migration: Add AccountID column to Users table and assign EWS IDs to existing records.
Also backfill Mobile column from identifier (phone number) where missing.

Run: python scripts/add_account_id.py
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # 1. Add AccountID column if not exists
    try:
        conn.execute(text("""
            ALTER TABLE app."Users" 
            ADD COLUMN IF NOT EXISTS "AccountID" VARCHAR(20) UNIQUE
        """))
        conn.commit()
        print("✅ AccountID column added (or already exists)")
    except Exception as e:
        conn.rollback()
        print(f"⚠️  Column add: {e}")

    # 2. Get all users ordered by CreatedDate (oldest first get lowest EWS number)
    result = conn.execute(text("""
        SELECT "UserID", "AccountID", "Mobile"
        FROM app."Users"
        ORDER BY "CreatedDate" ASC NULLS LAST, "UserID" ASC
    """))
    users = result.fetchall()
    print(f"📋 Found {len(users)} users")

    # 3. Assign EWS IDs to users without one
    counter = 1
    assigned = 0
    mobile_filled = 0

    for user in users:
        user_id = user[0]
        existing_aid = user[1]
        existing_mobile = user[2]

        updates = []
        params = {"uid": user_id}

        # Assign EWS ID if missing
        if not existing_aid:
            account_id = f"EWS{counter}"
            updates.append('"AccountID" = :aid')
            params["aid"] = account_id
            counter += 1
            assigned += 1
        else:
            # Parse existing EWS number to keep counter in sync
            m = re.match(r'^EWS(\d+)$', existing_aid)
            if m:
                num = int(m.group(1))
                if num >= counter:
                    counter = num + 1

        # Backfill mobile from identifier if it looks like a phone number
        if not existing_mobile and re.match(r'^\+?\d{8,15}$', user_id.replace(' ', '')):
            updates.append('"Mobile" = :mobile')
            params["mobile"] = user_id
            mobile_filled += 1

        if updates:
            sql = f'UPDATE app."Users" SET {", ".join(updates)} WHERE "UserID" = :uid'
            conn.execute(text(sql), params)

    conn.commit()
    print(f"✅ Assigned {assigned} EWS Account IDs (EWS1 to EWS{counter-1})")
    print(f"✅ Backfilled {mobile_filled} Mobile numbers from phone identifiers")
    print("🎉 Migration complete!")
