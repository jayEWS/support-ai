# 🇸🇬 DEPLOYMENT GUIDE — Singapore PC Server

**Edgeworks AI Support Portal — Production Deployment**  
**Target:** Windows PC in Singapore Office  
**Access:** Cloudflare Tunnel → colleagues can use from anywhere, anytime  
**Cost:** $0/month (all services on free tier)

---

## 📋 Prerequisites

| Item | Requirement |
|------|-------------|
| **PC** | Windows 10/11, always powered ON |
| **Python** | 3.11+ ([python.org/downloads](https://python.org/downloads)) |
| **Git** | Git for Windows ([git-scm.com](https://git-scm.com)) |
| **Internet** | Stable connection (for Cloudflare Tunnel + Neon DB) |
| **RAM** | 8GB minimum (16GB recommended for AI embeddings) |

---

## 🔧 STEP 1: Clone the Project

Open **PowerShell** (Admin) and run:

```powershell
# Choose your project folder
cd C:\Project
git clone https://github.com/jayEWS/support-ai.git
cd support-ai
```

---

## 🐍 STEP 2: Setup Python Virtual Environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install all dependencies
pip install -r requirements.txt
```

> ⏱️ First install takes ~5 minutes (downloads AI models + libraries).

---

## 🔑 STEP 3: Create `.env` Configuration File

Create a file named `.env` in the project root folder (`C:\Project\support-ai\.env`).

**Copy-paste this template and fill in your keys:**

```ini
# ============================================
# SUPPORT-AI PRODUCTION CONFIG (.env)
# Singapore PC Server
# ============================================

# ── Database (Neon Cloud PostgreSQL — FREE) ──
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-YOUR-ENDPOINT.ap-southeast-1.aws.neon.tech/neondb?sslmode=require

# ── AI Engine (Groq — FREE) ──
GROQ_API_KEY=gsk_YOUR_GROQ_API_KEY
LLM_PROVIDER=groq
MODEL_NAME=llama-3.3-70b-versatile

# ── Google OAuth (for agent login) ──
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-YOUR_SECRET
GOOGLE_REDIRECT_URI=http://localhost:8001/api/auth/google/callback

# ── Server ──
PORT=8001

# ── Security (generate strong keys for production) ──
AUTH_SECRET_KEY=GENERATE_A_RANDOM_64_CHAR_STRING_HERE
API_SECRET_KEY=GENERATE_ANOTHER_RANDOM_STRING_HERE
```

### 🔐 How to Generate Strong Secret Keys

Open PowerShell and run:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the output into `AUTH_SECRET_KEY` and run again for `API_SECRET_KEY`.

### 🔑 Where to Get API Keys

| Service | URL | Free Tier |
|---------|-----|-----------|
| **Neon PostgreSQL** | [neon.tech](https://neon.tech) | 512MB storage, 1 project |
| **Groq API** | [console.groq.com](https://console.groq.com) | 30 req/min, 14,400/day |
| **Google OAuth** | [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) | Unlimited |

---

## ✅ STEP 4: Test Server Locally

```powershell
# Make sure venv is active
.\.venv\Scripts\Activate.ps1

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8001
```

Open browser → **http://localhost:8001**

You should see:
- ✅ Homepage loads
- ✅ Click "Login with Google" → redirects to Google → logs in
- ✅ Admin dashboard shows tickets, knowledge base, etc.

**If all works, press `Ctrl+C` to stop the server.**

---

## 🌐 STEP 5: Install Cloudflare Tunnel (Public Access)

This makes your Singapore PC accessible from anywhere in the world via HTTPS.

### 5a. Download & Install Cloudflared

Download from: [github.com/cloudflare/cloudflared/releases](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi)

Install the MSI file.

### 5b. Login to Cloudflare

```powershell
cloudflared tunnel login
```

This opens a browser — select your Cloudflare account.

### 5c. Create a Tunnel

```powershell
# Create a named tunnel
cloudflared tunnel create sg-support-ai

# Note the Tunnel ID that's printed (e.g., abc123-def456-...)
```

### 5d. Configure the Tunnel

Create file `C:\Users\YOUR_USER\.cloudflared\config.yml`:

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: C:\Users\YOUR_USER\.cloudflared\YOUR_TUNNEL_ID.json

ingress:
  - hostname: support.yourdomain.com
    service: http://localhost:8001
  - service: http_status:404
```

> **No custom domain?** Use the free `trycloudflare.com` quick tunnel instead:
> ```powershell
> cloudflared tunnel --url http://localhost:8001
> ```
> This gives you a random URL like `https://defend-wednesday-journalist-boot.trycloudflare.com`

### 5e. Install as Windows Service (Auto-Start on Boot)

```powershell
# Run as Administrator!
cloudflared service install
```

Now the tunnel starts automatically when the PC boots.

### 5f. DNS Setup (Custom Domain Only)

```powershell
cloudflared tunnel route dns sg-support-ai support.yourdomain.com
```

---

## 🔄 STEP 6: Update Google OAuth Redirect URI

Go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials):

1. Edit your OAuth 2.0 Client ID
2. Under **Authorized redirect URIs**, add:
   - `http://localhost:8001/api/auth/google/callback` (local testing)
   - `https://your-cloudflare-url/api/auth/google/callback` (production)
3. Click **Save**

Also update your `.env`:

```ini
GOOGLE_REDIRECT_URI=https://your-cloudflare-url/api/auth/google/callback
```

---

## 🚀 STEP 7: Auto-Start Server on Boot

### Option A: Use `NYALAKAN_SERVER.bat` (Recommended)

The file `NYALAKAN_SERVER.bat` is already in the project folder:

1. Right-click `NYALAKAN_SERVER.bat` → **Send to** → **Desktop (Create Shortcut)**
2. Press `Win+R` → type `shell:startup` → Enter
3. Copy the shortcut into the Startup folder
4. Now the server starts automatically when Windows starts!

### Option B: Create a Windows Scheduled Task

```powershell
# Run as Administrator
$Action = New-ScheduledTaskAction -Execute "C:\Project\support-ai\NYALAKAN_SERVER.bat" -WorkingDirectory "C:\Project\support-ai"
$Trigger = New-ScheduledTaskTrigger -AtLogon
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "SupportAI" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Edgeworks AI Support Portal"
```

---

## ⚙️ STEP 8: Windows Power Settings

**CRITICAL** — The PC must never sleep!

1. Open **Settings** → **System** → **Power & Sleep**
2. Set **Screen**: Turn off after 15 minutes
3. Set **Sleep**: **Never** (both battery and plugged in)
4. Open **Control Panel** → **Power Options** → **Change plan settings** → **Change advanced power settings**
5. Set **Hard disk** → **Turn off hard disk after**: **Never**

---

## 🔄 STEP 9: Sync Updates from Indo PC

### On Indo PC (Developer):

```powershell
cd D:\Project\support-ai
git add -A
git commit -m "update: description of changes"
git push origin main
```

### On Singapore PC (Server):

```powershell
cd C:\Project\support-ai
git pull origin main

# Restart the server
# Close the old NYALAKAN_SERVER.bat window
# Double-click NYALAKAN_SERVER.bat again
```

Or use this one-liner:

```powershell
cd C:\Project\support-ai; git pull origin main; .\.venv\Scripts\Activate.ps1; uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
```

---

## 🧪 STEP 10: Verify Everything Works

### Health Check

```powershell
curl http://localhost:8001/health
```

Expected response:
```json
{"status": "healthy", "services": {"database": "up", "redis": "disabled", "ai": "configured"}}
```

### Test from External Network

On your phone or another PC, open:
```
https://your-cloudflare-url/health
```

### Full Checklist

| Test | Expected |
|------|----------|
| `http://localhost:8001` | Homepage loads |
| `http://localhost:8001/login` | Google OAuth works |
| `http://localhost:8001/admin` | Dashboard loads (after login) |
| `http://localhost:8001/health` | Returns `"healthy"` |
| `https://your-tunnel-url/` | Same as above via internet |
| Portal Chat | AI answers questions from knowledge base |
| Knowledge Upload | PDF/TXT files index successfully |
| Ticket Creation | Chat auto-creates tickets |

---

## 🔧 Troubleshooting

### Server won't start

```powershell
# Check if port 8001 is in use
netstat -ano | findstr :8001

# Kill the process using port 8001
taskkill /PID <PID_NUMBER> /F

# Restart
.\.venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8001
```

### "Module not found" errors

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Database connection errors

- Check `.env` → `DATABASE_URL` is correct
- Test: `curl https://console.neon.tech` → dashboard should load
- Neon free tier pauses after 5 min inactivity — first request may be slow

### Google login doesn't work

- Check Google Console → redirect URIs match your tunnel URL
- Check `.env` → `GOOGLE_REDIRECT_URI` matches
- Clear browser cookies and try again

### Cloudflare Tunnel not connecting

```powershell
# Check tunnel status
cloudflared tunnel info sg-support-ai

# Restart tunnel service
Restart-Service Cloudflared

# Check logs
cloudflared tunnel --loglevel debug --url http://localhost:8001
```

---

## 📊 System Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│                    SINGAPORE PC                         │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  FastAPI      │  │  Qdrant      │  │  HuggingFace │  │
│  │  Server       │  │  Vector DB   │  │  Embeddings  │  │
│  │  :8001        │  │  (Local)     │  │  (Local)     │  │
│  └──────┬───────┘  └──────────────┘  └──────────────┘  │
│         │                                               │
│  ┌──────┴───────┐                                       │
│  │  Cloudflare  │                                       │
│  │  Tunnel      │◄── HTTPS from anywhere                │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
          │                        │
          ▼                        ▼
  ┌──────────────┐         ┌──────────────┐
  │  Neon Cloud  │         │  Groq Cloud  │
  │  PostgreSQL  │         │  Llama-3.3   │
  │  (Singapore) │         │  70B (Free)  │
  └──────────────┘         └──────────────┘
```

### Cost Breakdown

| Service | Monthly Cost | Limit |
|---------|-------------|-------|
| Singapore PC | $0 (existing hardware) | Always-on |
| Neon PostgreSQL | $0 (free tier) | 512MB storage |
| Groq API | $0 (free tier) | 14,400 requests/day |
| Cloudflare Tunnel | $0 (free) | Unlimited bandwidth |
| HuggingFace Embeddings | $0 (runs locally) | Unlimited |
| Qdrant Vector DB | $0 (local file) | Limited by disk |
| **Total** | **$0/month** | |

---

## 🆘 Emergency Recovery

### If Singapore PC crashes / restarts:

1. PC boots → Cloudflare Tunnel auto-starts (if installed as service)
2. Double-click `NYALAKAN_SERVER.bat` on Desktop
3. Wait 30 seconds for server to start
4. Everything is back online!

### If database is corrupted:

- Neon Cloud has automatic backups — go to [neon.tech](https://neon.tech) dashboard
- Knowledge base vectors are local — re-index via Admin → Knowledge → "Train AI"

### If you need to move to a different PC:

1. `git clone https://github.com/jayEWS/support-ai.git`
2. Copy `.env` file from old PC
3. Run Steps 2-7 above
4. Data is safe in Neon Cloud — no migration needed!

---

**Last Updated:** March 17, 2026  
**Maintained by:** Jay @ Edgeworks Solutions Pte Ltd
