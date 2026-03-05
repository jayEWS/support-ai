#!/usr/bin/env python
"""
Quick Azure SQL Setup - Interactive Configuration
Run this to easily configure Azure connection
"""

import os
import sys
from pathlib import Path

def url_encode_password(password):
    """URL encode special characters in password"""
    password = password.replace("@", "%40")
    password = password.replace("!", "%21")
    password = password.replace("#", "%23")
    password = password.replace("$", "%24")
    password = password.replace("%", "%25")
    password = password.replace("&", "%26")
    password = password.replace("=", "%3D")
    return password

def main():
    print("\n" + "="*60)
    print("🔷 AZURE SQL DATABASE - QUICK SETUP")
    print("="*60 + "\n")
    
    print("Before running this, you should have:")
    print("  ✓ Created Azure SQL Database")
    print("  ✓ Created server with username & password")
    print("  ✓ Noted down server name\n")
    
    # Get inputs
    server_name = input("Enter Azure Server Name (e.g., myserver.database.windows.net): ").strip()
    username = input("Enter SQL Username (e.g., adminuser): ").strip()
    password = input("Enter SQL Password: ").strip()
    database = input("Enter Database Name (default: tcareews): ").strip() or "tcareews"
    
    if not server_name or not username or not password:
        print("\n❌ Error: All fields required!")
        sys.exit(1)
    
    # Build connection string
    encoded_password = url_encode_password(password)
    
    database_url = (
        f"mssql+pyodbc://{username}:{encoded_password}"
        f"@{server_name}:1433/{database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=no"
        f"&Connection+Timeout=30"
    )
    
    # Update .env
    env_path = Path("d:/Project/support-portal-edgeworks/.env")
    
    if env_path.exists():
        with open(env_path, "r") as f:
            content = f.read()
        
        # Replace or add DATABASE_URL
        if "DATABASE_URL=" in content:
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                if line.startswith("DATABASE_URL="):
                    new_lines.append(f"DATABASE_URL={database_url}")
                else:
                    new_lines.append(line)
            content = "\n".join(new_lines)
        else:
            content += f"\nDATABASE_URL={database_url}\n"
        
        with open(env_path, "w") as f:
            f.write(content)
        
        print("\n" + "="*60)
        print("✅ SUCCESS!")
        print("="*60)
        print(f"\n📝 Updated .env file with Azure connection")
        print(f"\n🔗 Connection String (hidden for security):")
        print(f"   Server: {server_name}")
        print(f"   Database: {database}")
        print(f"   Username: {username}")
        print(f"\n📌 Next Steps:")
        print(f"   1. Update Firewall in Azure Portal:")
        print(f"      - Add your IP address")
        print(f"      - Or set 0.0.0.0 - 255.255.255.255 for any IP")
        print(f"\n   2. Test locally:")
        print(f"      python scripts/create_db.py")
        print(f"\n   3. Run server:")
        print(f"      python -m uvicorn main:app --host 127.0.0.1 --port 8001")
        print(f"\n   4. Deploy to Render:")
        print(f"      - Add same DATABASE_URL to Render environment")
        print(f"      - Deploy!")
        print("\n" + "="*60)
    else:
        print(f"\n❌ Error: .env file not found at {env_path}")
        print(f"✅ Here's your connection string to use:")
        print(f"\nDATABASE_URL={database_url}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
