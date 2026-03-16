# Edgeworks AI Support Portal: Free Hosting Strategy

To continue building and hosting your project for **$0/month**, move from a paid GCP VM to these "Modern Cloud" free-tier services. This setup is perfect for development and low-traffic production.

## 🛠️ The "Always Free" Stack

| Component | Provider | Free Tier Limit |
|-----------|----------|-----------------|
| **Backend / Web + DB** | [Hugging Face Spaces](https://huggingface.co/spaces) | 2 vCPU, 16GB RAM (Always On) |
| **Database (MSSQL)** | **SQL Server Edge** | Running inside your Space (Local to app) |
| **Vector DB** | [Qdrant Cloud](https://qdrant.tech) | 1GB RAM, 1 Cluster |
| **Redis** (Real-time) | [Upstash](https://upstash.com) | 10,000 requests/day |
| **AI (LLM)** | [Google AI Studio](https://aistudio.google.com) | Gemini 1.5 Flash (15 RPM / 1M TPM) |

---

### 1. Database (The "Magic" Method)

Since you've had trouble with Azure registration, we'll run **SQL Server Edge** directly inside your Hugging Face Space. This is a lightweight version of SQL Server that runs alongside your app.

1.  **Hugging Face Space Setup**:
    -   When creating a new Space, choose **Docker** and select **Blank**.
    -   In the Settings, add these **Secret Variables**:
        -   `SA_PASSWORD`: Set this to a strong password (e.g., `SuperSecret!123`).
        -   `ACCEPT_EULA`: `Y`
        -   `DATABASE_URL`: `mssql+pyodbc://sa:[YOUR_SA_PASSWORD]@localhost:1433/portal?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no`
        -   `GOOGLE_GEMINI_API_KEY`: Your Gemini API key.
2.  **Deployment Code**:
    -   I've created a special **[Dockerfile.hf](file:///d:/Project/support-ai/Dockerfile.hf)** and an **[entrypoint.sh](file:///d:/Project/support-ai/scripts/entrypoint.sh)** script in your project.
    -   When you push your code to Hugging Face, **rename `Dockerfile.hf` to `Dockerfile`** so they can build it.

### 2. Connection String
Your application will talk to `localhost` inside the Hugging Face container on port `1433`. The `entrypoint.sh` script will automatically:
- Start SQL Server.
- Create the `portal` database.
- Run your `alembic` migrations.
- Start your FastAPI app.

### 2. Redis (Upstash)
1. Create a Redis database on [Upstash](https://upstash.com).
2. Copy the **Redis URL**.
3. It looks like: `redis://default:[TOKEN]@xxx.upstash.io:6379`

### 3. Vector DB (Qdrant)
1. Create a cluster on [Qdrant Cloud](https://cloud.qdrant.io/).
2. Copy the **Endpoint URL** and generate an **API Key**.

### 4. AI (Gemini)
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).

---

## ☁️ Step 2: Hosting on Hugging Face Spaces (Recommended for AI)

Hugging Face Spaces is currently the best free host for Docker apps. It offers more RAM than Render/Fly free tiers.

### 1. Create a new Space
- Go to [Hugging Face New Space](https://huggingface.co/new-space).
- **Space Name:** `support-ai-portal` (or similar).
- **SDK:** `Docker` (Choose "Blank").
- **Public/Private:** Public is free.

### 2. Configure Environment Variables
In your Space **Settings > Variables and Secrets**, add the following:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Your Supabase URL |
| `REDIS_URL` | Your Upstash Redis URL |
| `REDIS_ENABLED` | `True` |
| `QDRANT_HOST` | Your Qdrant Cloud URL (e.g., `xxx.qdrant.tech`) |
| `QDRANT_API_KEY` | Your Qdrant API Key |
| `GOOGLE_GEMINI_API_KEY` | Your Gemini API Key from AI Studio |
| `AUTH_SECRET_KEY` | `your-secret-long-string` |
| `API_SECRET_KEY` | `your-api-long-string` |
| `DEBUG` | `False` |

---

## 🔄 Step 3: Deployment Workflow

1. **Push Code to Space Repo**:
   Hugging Face uses Git. Clone your Space repo, copy your project files into it, and push:
   ```bash
   git clone https://huggingface.co/spaces/your-username/support-ai-portal
   cp -r support-ai/* support-ai-portal/
   cd support-ai-portal
   git add .
   git commit -m "Initial deploy"
   git push
   ```

2. **Database Migration**:
   Run this locally (from your PC) to setup your Supabase tables:
   ```bash
   # In PowerShell/Bash
   $env:DATABASE_URL="your_supabase_url"
   alembic upgrade head
   ```

3. **Knowledge Re-indexing**:
   Since your vector data is moving to Qdrant Cloud, re-upload your knowledge files through the Admin Dashboard once the app is live.

---

## 🎯 Best for WhatsApp
Hugging Face Spaces provides a persistent HTTPS URL (e.g., `https://username-space.hf.space`). 
- Use this URL in your Meta App Dashboard as your **Webhook Callback URL**.
- It stays active 24/7 (unlike Render's free tier which sleeps).

---

> [!IMPORTANT]
> **Cost Comparison**:
> - **GCP VM**: ~$20-$50/month
> - **This Stack**: **$0/month**
