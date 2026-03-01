# 🚀 DEPLOYMENT GUIDE - Get Your App Online Forever

## Problem
- Your local server keeps stopping after a few requests
- ngrok is offline because local server isn't running
- You need a **permanent public URL** that's always online

## Solution: Deploy to Render (FREE)

Render provides:
- ✅ Free tier (always online)
- ✅ Automatic restarts if crash
- ✅ Public URL (myapp.onrender.com)
- ✅ GitHub integration (auto-deploy on push)
- ✅ No credit card needed for free tier

---

## Step 1: Prepare for Deployment

### 1.1 Ensure Dockerfile exists
Your project has a `Dockerfile` - good! Check it:
```bash
cat Dockerfile
```

### 1.2 Update .gitignore
Make sure these are ignored:
```
.env
.venv/
__pycache__/
*.pyc
data/
.DS_Store
```

### 1.3 Commit to Git
```powershell
cd d:\Project\support-portal-edgeworks
git add -A
git commit -m "Production ready: KB URL ingestion, admin user, all RAG improvements"
git push origin master
```

---

## Step 2: Deploy to Render

### Option A: Deploy from GitHub (RECOMMENDED)

1. **Go to Render.com**
   - https://render.com
   - Sign up with GitHub

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Select branch: `master`

3. **Configure Settings**
   ```
   Name: support-portal
   Environment: Docker
   Plan: Free
   Region: Singapore (or closest to you)
   ```

4. **Set Environment Variables**
   In Render dashboard → "Environment":
   ```
   DATABASE_URL=mssql+pyodbc://sa:1@localhost:1433/tCareEWS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes
   OPENAI_API_KEY=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
   LLM_PROVIDER=groq
   GROQ_API_KEY=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
   API_SECRET_KEY=supersecretkey123
   AUTH_SECRET_KEY=your-secret-auth-key-123456789
   ```

5. **Deploy**
   - Click "Create Web Service"
   - Wait 5-10 minutes for build & deployment
   - Get your public URL: `https://support-portal.onrender.com`

---

### Option B: Deploy via CLI (Docker Compose)

If you prefer deploying from your machine:

```powershell
# 1. Build Docker image
docker build -t support-portal .

# 2. Test locally
docker run -p 8001:8000 `
  -e DATABASE_URL="mssql+pyodbc://..." `
  -e OPENAI_API_KEY="..." `
  support-portal

# 3. Push to Docker Hub
docker tag support-portal:latest username/support-portal:latest
docker push username/support-portal:latest

# 4. On Render, create Web Service and link the Docker image
```

---

## Step 3: After Deployment

### 3.1 Test Your Public URL
```bash
# Check health
curl https://support-portal.onrender.com/

# Login endpoint
https://support-portal.onrender.com/login

# Chat endpoint
https://support-portal.onrender.com/chat
```

### 3.2 Important Database Issue ⚠️

**Your database is LOCAL** (SQL Server on your machine).

**This won't work on Render** because Render can't access your local network.

**Solutions**:

**Option 1: Cloud Database (BEST)**
- Move SQL Server to Azure SQL Database (free tier available)
- Or use AWS RDS
- Update `DATABASE_URL` to cloud database

**Option 2: Keep Local, Use ngrok for DB**
```powershell
# Forward SQL Server to internet
ngrok tcp 1433

# Use ngrok URL in Render's DATABASE_URL
```

**Option 3: SQLite (EASIEST for demo)**
- Switch to SQLite instead of SQL Server
- Works with Render free tier
- Good for testing

   *Tip:* after you set `DATABASE_URL=sqlite:///./data.db` you can run
   `python scripts/create_db.py` to ensure the file and tables are created.  The
   helper script has been enhanced to auto‑detect SQLite and will initialize
   the schema automatically.

---

## Step 4: Recommended Configuration

### For TESTING (Quick):
```yaml
# Use SQLite instead of SQL Server
DATABASE_URL=sqlite:///./data.db
LLM_PROVIDER=groq
GROQ_API_KEY=your_key
```

If you already have an existing SQL Server database and want to preserve the
data, run the migration helper before switching the URL:

```powershell
# make sure DATABASE_URL currently points at your SQL Server instance
python scripts/migrate_to_sqlite.py    # output will be ./data.db by default
```

This will copy every table row‑by‑row into a new SQLite file.  After it
finishes you can set the environment variable above and restart the server.

### For PRODUCTION (Real):
```yaml
DATABASE_URL=mssql+pyodbc://user:pass@azure-sql-server.database.windows.net:1433/database_name?driver=ODBC+Driver+17+for+SQL+Server
LLM_PROVIDER=groq
RAG_HYBRID_SEARCH_ENABLED=true
```

> 💡 **Groq availability**: the free Groq API key can be used 24/7. there is no
expiration on the key itself, although you should watch the per‑minute and
daily rate limits documented by Groq. As long as your server is running (e.g.
on Render, a VPS, or your local machine with `start_server.ps1`), it will be
able to call Groq at any hour.

> 🛠 **Keeping the service online**: for continuous operation deploy the
application to a hosting provider (Render, Azure Web App, etc.) or use the
`start_server.ps1` script locally which automatically restarts the FastAPI
process if it crashes.

---

## Step 5: Monitor & Maintain

### Check Deployment Status
- Render Dashboard → Your service
- View logs
- Check CPU/Memory usage

### Auto-Restart on Crash
Render automatically restarts if service crashes

### Custom Domain
- Render free tier: `support-portal.onrender.com`
- Paid tier: Add custom domain

---

## QUICK START (5 minutes)

1. **Ensure your code is in Git**
   ```powershell
   git status  # Should be clean
   git push    # Push to GitHub
   ```

2. **Go to render.com**
   - Sign up with GitHub
   - Click "New Web Service"
   - Select your repo
   - Click "Deploy"

3. **Wait for build** (5-10 min)

4. **Get public URL**
   - Example: `https://support-portal-abc123.onrender.com`
   - Share this URL anywhere!

---

## TROUBLESHOOTING

### "Build failed"
- Check logs in Render dashboard
- Usually missing dependencies
- Run locally first: `pip install -r requirements.txt`

### "Service won't start"
- Check DATABASE_URL is correct
- Check all required env vars are set
- Check port is 8000 (Render default)

### "Database connection error"
- SQL Server is LOCAL - won't work on Render
- Use cloud database or SQLite
- Or use ngrok to tunnel local database

### "Service keeps crashing"
- Check logs for errors
- Increase memory in Render settings
- Check background tasks aren't causing issues

---

## Alternative Hosting

| Platform | Cost | Best For | Setup Time |
|----------|------|----------|-----------|
| **Render** | FREE | Quick demo | 5 min |
| **Railway** | FREE | Production-ready | 10 min |
| **AWS** | $0-100 | Enterprise | 30 min |
| **Heroku** | Paid only | Was popular | N/A |
| **DigitalOcean** | $5/mo | VPS control | 20 min |

---

## Your Next Actions

1. ✅ Fix local server crashes (identify root cause)
2. 📝 Get a cloud database (Azure SQL free tier)
3. 🚀 Deploy to Render
4. 🔗 Share public URL with team

---

## Expected Result

**Before**: Local server at `http://127.0.0.1:8001` (offline when you close laptop)

**After**: Public URL like `https://support-portal.onrender.com` (online 24/7)

✨ Your app will be accessible from anywhere, anytime!

---

**Questions?** Let me know which step you need help with.
