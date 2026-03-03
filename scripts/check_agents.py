"""Check agent departments"""
from app.core.database import db_manager
agents = db_manager.get_all_agents()
print(f"{'USER_ID':25s} | {'NAME':20s} | {'DEPARTMENT':20s} | {'ROLE':10s}")
print("-" * 85)
for a in agents:
    print(f"{a.get('user_id',''):25s} | {a.get('name',''):20s} | {str(a.get('department','(null)')):20s} | {a.get('role','')}")
