"""Quick check: what's in identifier, account_id, mobile for first 10 users"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT "UserID", "AccountID", "Mobile" 
        FROM app."Users" 
        ORDER BY "CreatedDate" ASC NULLS LAST
        LIMIT 15
    '''))
    for row in result:
        uid, aid, mob = row
        print(f"  identifier={uid[:25]:<25}  account_id={str(aid):<12}  mobile={str(mob):<25}")
