#!/usr/bin/env python
"""
Create a default admin user for testing
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from app.core.database import db_manager
from app.utils.auth_utils import get_password_hash

# Get admin credentials from environment or use a secure fallback for dev
# In production, these MUST be set via environment variables
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    print("⚠️  WARNING: ADMIN_PASSWORD environment variable not set.")
    if os.getenv("ENVIRONMENT") == "production":
        print("❌ ERROR: ADMIN_PASSWORD is required in production.")
        sys.exit(1)
    else:
        ADMIN_PASSWORD = "admin123"  # Insecure default for local dev only
        print(f"Using default dev password: {ADMIN_PASSWORD}")

# Create admin user using create_or_get_agent
agent = db_manager.create_or_get_agent(
    user_id="admin_001",
    name="Admin User",
    email=ADMIN_EMAIL,
    department="Support"
)

# Update password
db_manager.update_agent_auth(
    user_id="admin_001",
    hashed_password=get_password_hash(ADMIN_PASSWORD)
)

try:
    # Insert into database
    result = agent
    print(f"✅ Admin user created/updated successfully!")
    print(f"\n📝 Login Credentials:")
    print(f"   Email: {ADMIN_EMAIL}")
    if os.getenv("ADMIN_PASSWORD"):
        print(f"   Password: [SET VIA ENVIRONMENT]")
    else:
        print(f"   Password: {ADMIN_PASSWORD} (DEV DEFAULT)")
except Exception as e:
    print(f"❌ Error creating user: {str(e)}")
    sys.exit(1)
