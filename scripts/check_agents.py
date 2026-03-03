"""Check agent departments"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.database import db_manager
agents = db_manager.get_all_agents()
for a in agents:
    uid = a.get('user_id','')
    name = a.get('name','')
    dept = a.get('department','NULL')
    role = a.get('role','')
    print(f"{uid} | {name} | {dept} | {role}")
