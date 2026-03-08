from app.core.database import db_manager
from sqlalchemy import text

def check():
    session = db_manager.get_session()
    res = session.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='WhatsAppMessages'")).fetchone()
    if res:
        print(res[0])
    else:
        print("Table not found")

if __name__ == "__main__":
    check()
