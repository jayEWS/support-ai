from app.core.database import db_manager
from app.models.models import Agent

def seed_rbac():
    # 1. Create Permissions
    permissions = [
        ("knowledge.upload", "Can upload documentation"),
        ("knowledge.delete", "Can delete documentation"),
        ("ticket.view", "Can view all tickets"),
        ("ticket.edit", "Can update ticket status/priority"),
        ("ticket.delete", "Can delete tickets"),
        ("agent.manage", "Can add/edit/remove agents"),
        ("system.settings", "Can access system configuration"),
        ("audit.view", "Can view audit logs"),
        ("analytics.view", "Can view performance dashboards")
    ]
    
    for name, desc in permissions:
        db_manager.create_permission(name, desc)
    
    # 2. Create Roles
    # System Admin - Everything
    db_manager.create_role(
        "System Admin", 
        "Full system access", 
        permissions=[p[0] for p in permissions]
    )
    
    # Admin - Management
    db_manager.create_role(
        "Admin", 
        "Operational management access", 
        permissions=[
            "knowledge.upload", "knowledge.delete", "ticket.view", 
            "ticket.edit", "agent.manage", "analytics.view"
        ]
    )
    
    # Support - Basic
    db_manager.create_role(
        "Support", 
        "Customer support access", 
        permissions=["ticket.view", "ticket.edit", "analytics.view"],
        is_default=True
    )
    
    # 3. Assign System Admin to your account
    db_manager.assign_role_to_agent("admin_main", "System Admin")
    # Also link by email just in case
    session = db_manager.get_session()
    agent = session.query(Agent).filter_by(email="admin@Support.ai").first()
    if agent:
        db_manager.assign_role_to_agent(agent.user_id, "System Admin")
    
    print("✅ RBAC Seeding Complete.")

if __name__ == "__main__":
    seed_rbac()
