#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct database test for magic link creation and retrieval.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import bcrypt

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

# Fix encoding for Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Set database URL
os.environ['DATABASE_URL'] = 'postgresql+psycopg2://kfkneyixgmvhud:p1cbfb16ba62f8e1f9a8c7e4a33e91b43@ep-shrill-mouse-a5a8p8yq.us-east-1.rds.supabase.co:5432/postgres'

from app.core.database import DatabaseManager
from app.core.logging import logger

def hash_token(token: str) -> str:
    """Hash token using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(token.encode(), salt).decode()

def test_magic_link_flow():
    """Test creating and retrieving magic links"""
    print("\n" + "="*70)
    print("TESTING MAGIC LINK DATABASE OPERATIONS")
    print("="*70)
    
    db = DatabaseManager()
    
    test_email = "db-test@example.com"
    test_token = "test-token-12345"
    
    # Step 1: Create magic link
    print("\n1. Creating magic link...")
    token_hash = hash_token(test_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    success = db.create_magic_link(test_email, token_hash, expires_at)
    if success:
        print(f"   ✓ Magic link created for {test_email}")
        print(f"   Token hash: {token_hash[:30]}...")
    else:
        print(f"   ❌ Failed to create magic link")
        return
    
    # Step 2: Retrieve magic link
    print("\n2. Retrieving magic link...")
    link = db.get_magic_link(test_email, token_hash)
    
    if link:
        print(f"   ✓ Magic link found!")
        print(f"   User ID: {link['user_id']}")
        print(f"   Expires at: {link['expires_at']}")
        print(f"   Is expired: {link['expires_at'] < datetime.now(timezone.utc)}")
    else:
        print(f"   ❌ Could not retrieve magic link")
        print(f"\n   Debugging: Let's check what's in the database...")
        
        # Try to get agent directly
        agent = db.get_agent_by_email(test_email)
        if agent:
            print(f"   - Agent found: {agent}")
        else:
            print(f"   - No agent found with email {test_email}")
        
        # List all agents
        session = db.get_session()
        try:
            from app.models.models import Agent
            all_agents = session.query(Agent).all()
            print(f"   - Total agents in DB: {len(all_agents)}")
            if all_agents:
                print(f"   - First agent: {all_agents[0].email}")
        finally:
            session.close()
        
        return
    
    # Step 3: Check if not expired
    print("\n3. Verifying link is valid...")
    if link['expires_at'] > datetime.now(timezone.utc):
        print("   ✓ Link has not expired")
    else:
        print("   ❌ Link is expired")
    
    # Step 4: Revoke link
    print("\n4. Revoking magic link...")
    db.revoke_magic_link(test_email, token_hash)
    
    # Try to retrieve again
    link = db.get_magic_link(test_email, token_hash)
    if not link:
        print("   ✓ Link successfully revoked")
    else:
        print("   ❌ Link still exists after revocation")
    
    print("\n" + "="*70)
    print("✅ DATABASE TEST COMPLETE")
    print("="*70)

if __name__ == "__main__":
    test_magic_link_flow()
