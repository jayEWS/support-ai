#!/usr/bin/env python
"""Initialize high-volume mock data for world-class dashboard review."""

from app.core.database import db_manager
from app.utils.auth_utils import get_password_hash
from datetime import datetime, timedelta
import random

# 1. Team Config
print("Populating Team Members...")
team_configs = [
    ('agent_john_demo', 'John Support', 'john@support.ai', 'Support'),
    ('agent_jane_demo', 'Jane Support', 'jane@support.ai', 'Support'),
    ('agent_sarah_prod', 'Sarah Specialist', 'sarah@support.ai', 'Product specialist'),
    ('agent_mike_pm', 'Mike Manager', 'mike@support.ai', 'Project manager'),
    ('agent_lisa_sales', 'Lisa Sales', 'lisa@support.ai', 'Sales'),
    ('agent_kevin_hr', 'Kevin HR', 'kevin@support.ai', 'HR'),
    ('agent_dev_1', 'Dev One', 'dev1@support.ai', 'developer'),
    ('agent_qa_1', 'QA Lead', 'qa1@support.ai', 'QA'),
    ('agent_dep_deploy', 'Cloud Deploy', 'deploy@support.ai', 'Deployment')
]

hashed_pw = get_password_hash("password123")
for uid, name, email, dept in team_configs:
    db_manager.create_or_get_agent(uid, name, email, '["general"]')
    db_manager.update_agent_auth(uid, hashed_pw, role='admin' if uid == 'agent_john_demo' else 'agent')
    db_manager.update_agent_department(uid, dept)
    db_manager.update_agent_presence(uid, 'available', 0)

# 2. Knowledge Base & Macros
print("Populating Knowledge & Macros...")
for f in ["Policy.pdf", "API.md", "FAQ.txt", "Roadmap.xlsx", "Security.pdf"]:
    db_manager.save_knowledge_metadata(f, f"data/knowledge/{f}")

for n, c, cat in [("Greet", "Hi!", "General"), ("Wait", "Hold on.", "General"), ("Done", "Fixed!", "Closing")]:
    db_manager.create_macro(n, c, cat)

# 3. Generating 30+ Distributed Tickets for Analytics
print("Generating distributed ticket data for Analytics...")
priorities = ["Urgent", "High", "Medium", "Low"]
statuses = ["open", "pending", "resolved"]
users = [("u1", "Alice", "Google"), ("u2", "Bob", "Apple"), ("u3", "Charlie", "Meta"), ("u4", "Diana", "Amazon")]

for i in range(1, 35):
    uid, name, comp = random.choice(users)
    prio = random.choice(priorities)
    stat = random.choice(statuses)
    agent = random.choice(team_configs)[0] if stat != "open" else None
    
    tid = db_manager.create_ticket(
        user_id=uid,
        summary=f"Sample issue number {i}",
        full_history=f"USER: Help with issue {i}\n",
        status=stat,
        priority=prio,
        due_at=datetime.now() + timedelta(days=1)
    )
    
    if agent:
        # Mock assignment
        sid = db_manager.create_chat_session(tid, agent, uid)
        db_manager.save_chat_message(sid, uid, 'user', 'Need help')
        db_manager.save_chat_message(sid, agent, 'agent', 'Assisting now')
        
        # Add random CSAT for resolved
        if stat == "resolved":
            db_manager.submit_csat(tid, random.randint(3, 5), "Good service")

# 4. Audit Logs
for i in range(1, 6):
    db_manager.log_action('agent_john_demo', 'login', 'agent', 'agent_john_demo')

print("\n✅ High-volume analytic data initialized!")
