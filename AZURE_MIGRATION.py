#!/usr/bin/env python
"""
Azure SQL Database Migration Guide
Connects your app to Azure SQL instead of local SQL Server
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Azure SQL Connection String Format:
AZURE_CONNECTION_STRING = (
    "mssql+pyodbc://"
    "{username}:{password}"
    "@{server}.database.windows.net:1433"
    "/{database}"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&Encrypt=yes"
    "&TrustServerCertificate=no"
    "&Connection+Timeout=30"
)

# Example with actual values:
EXAMPLE_AZURE_URL = (
    "mssql+pyodbc://"
    "adminuser:Password123@"
    "myserver.database.windows.net:1433"
    "/tcareews"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&Encrypt=yes"
    "&TrustServerCertificate=no"
    "&Connection+Timeout=30"
)

print("""
╔════════════════════════════════════════════════════════════╗
║   🔷 AZURE SQL DATABASE - MIGRATION GUIDE                 ║
╚════════════════════════════════════════════════════════════╝

✅ BENEFITS:
  • Cloud-hosted (no local database needed)
  • Always online, scalable
  • Free tier available
  • Works perfectly with Render deployment
  • Automatic backups
  • Pay-as-you-go (often FREE tier is enough)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ STEP 1: CREATE AZURE SQL DATABASE (Free Tier)

1. Go to: https://portal.azure.com
2. Search: "SQL Databases"
3. Click "Create"
4. Configure:
   - Resource Group: Create new
   - Database name: tcareews
   - Server: Create new
     - Server name: myserver-xyz (must be unique)
     - Location: East US (or closest)
     - Auth: SQL authentication
     - Username: adminuser
     - Password: Password123!Secure
   - Compute + storage: Basic ($5-10/month, or FREE trial)
5. Review + Create

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ STEP 2: GET CONNECTION STRING

1. Azure Portal → Your SQL Database
2. Click "Connection strings"
3. Copy "ODBC" connection string
4. Format will look like:

   Driver={ODBC Driver 18 for SQL Server};
   Server=tcp:myserver.database.windows.net,1433;
   Database=tcareews;
   Uid=adminuser;
   Pwd=Password123;
   Encrypt=yes;
   TrustServerCertificate=no;
   Connection Timeout=30;

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ STEP 3: UPDATE .env FILE

Replace DATABASE_URL with:

DATABASE_URL=mssql+pyodbc://adminuser:Password123%40@myserver.database.windows.net:1433/tcareews?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

⚠️  IMPORTANT:
  • Replace "adminuser" with your Azure username
  • Replace "Password123" with your Azure password  
  • URL-encode password: @ becomes %40, ! becomes %21
  • Replace "myserver" with your actual server name

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ STEP 4: ALLOW LOCAL FIREWALL

Before testing locally:

1. Azure Portal → SQL Server (not database)
2. Click "Firewalls and virtual networks"
3. Add your IP address
4. Or set start: 0.0.0.0, end: 255.255.255.255 (allows all)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ STEP 5: TEST LOCALLY

1. Update .env with Azure URL
2. Run migration:
   python scripts/create_db.py

3. Start server:
   python -m uvicorn main:app --host 127.0.0.1 --port 8001

4. Test:
   curl http://127.0.0.1:8001/
   
✅ If it works, you're connected to Azure!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ STEP 6: DEPLOY TO RENDER

1. In Render Dashboard → Environment Variables
2. Add:
   DATABASE_URL=mssql+pyodbc://adminuser:Password123%40@myserver.database.windows.net:1433/tcareews?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

3. Other variables:
   OPENAI_API_KEY=your-api-key-here
   LLM_PROVIDER=groq
   API_SECRET_KEY=your-secure-secret-key-here

4. Deploy
5. Now your app is ONLINE + uses Azure DB!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 PRICING (Azure SQL)

Free Tier:
  • 12 months free
  • 32 GB storage
  • Perfect for testing/demo

Standard Tier:
  • ~$10-50/month
  • More performance
  • Recommended for production

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 RESULT

Before:
  • Local database on your machine
  • App offline when laptop closed
  • Can't scale

After:
  • ✅ Cloud database (always online)
  • ✅ App deployed on Render (always online)
  • ✅ Accessible from anywhere
  • ✅ URL: https://support-portal.onrender.com
  • ✅ Works 24/7 forever!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❓ QUESTIONS?

Connection not working?
  • Check firewall rules in Azure Portal
  • Verify password special characters are URL-encoded
  • Test: python scripts/create_db.py

Render deployment failing?
  • Check all env vars are set
  • Check DATABASE_URL is correct
  • View logs in Render dashboard

Need help?
  Let me know the error message!

""")
