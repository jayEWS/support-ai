# Neon PostgreSQL Setup Guide

## Why Neon?

- **Free Forever** — 512 MB storage, 0.25 vCPU, always-on
- **Serverless** — Auto-scales, auto-suspends after 5 min idle
- **PostgreSQL 16** — Full compatibility, no vendor lock-in
- **Hosted on GCP** — Low latency from your GCP VM (`asia-southeast1`)

---

## 1. Create a Neon Account

1. Go to [https://neon.tech](https://neon.tech)
2. Sign up with GitHub or Google (no credit card needed)
3. Click **"Create a project"**
   - **Project name**: `support-ai-ews`
   - **Region**: `Asia Pacific (Singapore)` — closest to your GCP VM
   - **PostgreSQL version**: 16 (default)
4. Click **Create project**

## 2. Get Your Connection String

After creating the project, Neon shows a connection string like:

```
postgresql://neondb_owner:xxxxxx@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
```

Copy this — you'll use it as `DATABASE_URL`.

## 3. Update Your `.env` File

Replace the old SQL Server connection string:

```bash
# OLD (SQL Server)
# DATABASE_URL=mssql+pyodbc://sa:1@localhost:1433/tCareEWS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes

# NEW (Neon PostgreSQL)
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-xxx-yyy-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
```

## 4. Deploy to GCP VM

SSH into your VM and update the Docker container:

```bash
# SSH into the VM
gcloud compute ssh ews-support-ai --zone=asia-southeast1-b

# Update the .env file
nano /opt/support-ai/.env
# → Paste the new DATABASE_URL

# Rebuild and restart
cd /opt/support-ai
docker-compose down
docker-compose up -d --build

# Check logs
docker logs support-ai --tail 50
```

You should see:
```
INFO: Initializing PostgreSQL database engine...
INFO: PostgreSQL database tables verified/created.
```

## 5. Seed Initial Data

After the first deployment with the new DB:

```bash
# Inside the container
docker exec -it support-ai bash

# Create admin user
python scripts/update_admin.py

# Initialize RBAC
python scripts/init_rbac.py

# Seed SaaS data (plans, default tenant)
python scripts/seed_saas.py
```

---

## Free Tier Limits

| Resource | Free Tier |
|----------|-----------|
| Storage | 512 MB |
| Compute | 0.25 vCPU (shared) |
| Branches | 10 |
| Data Transfer | Unlimited |
| Auto-suspend | After 5 min idle |
| Scale-to-zero | ✅ Yes |
| Price | **$0/month forever** |

For this app, 512 MB is plenty — typical usage:
- ~10 MB for all tables
- ~50 MB for knowledge metadata + tickets
- 450+ MB headroom for growth

---

## Troubleshooting

### Connection refused / timeout
- Neon auto-suspends after 5 min idle — first request may take ~1s to "wake up"
- This is normal and handled by SQLAlchemy's retry logic

### SSL errors
- Ensure `?sslmode=require` is in your DATABASE_URL
- Neon requires SSL for all connections

### Tables not created
- SQLAlchemy auto-creates tables on startup (`Base.metadata.create_all()`)
- If issues persist, check logs: `docker logs support-ai`
