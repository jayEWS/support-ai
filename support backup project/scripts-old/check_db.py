from app.core.database import db_manager
import json

def check():
    user_id = "customer@example.com"
    msgs = db_manager.get_messages(user_id)
    print(f"Total messages for {user_id}: {len(msgs)}")
    for m in msgs:
        print(f"Role: {m['role']}")
        print(f"Content: {m['content'][:100]}...")
        print(f"Attachments: {m['attachments']}")
        print("-" * 20)

if __name__ == "__main__":
    check()
