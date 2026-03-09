# 🏢 Edgeworks Office PC Deployment Guide (AWS + Docker + SQL Server)

This guide covers how to run the Support AI Portal in production mode strictly on your **local office PC** acting as a server, utilizing a robust stack:
*   **Database:** Microsoft SQL Server 2025 (`sa:1`)
*   **Hosting:** Local Docker Engine
*   **Cloud Extensibility:** AWS integration for S3 storage / secrets management (optional scaling path).

---

## 🏗️ Prerequisites
Ensure your local Office PC (Windows) has the following installed:
1.  **Docker Desktop** for Windows (ensure WSL 2 engine is enabled).
2.  **Microsoft SQL Server 2025** (Developer or Express edition running locally).
    *   Make sure Mixed Mode Authentication is enabled (SQL Server Authentication).
    *   Ensure TCP/IP is **Enabeld** in SQL Server Configuration Manager (under SQL Server Network Configuration). Ensure port `1433` is open.
3.  **Git** and **Python 3.11** installed.
4.  AWS CLI installed (if syncing files via AWS S3).

---

## 🛠️ Step 1: Database Setup (SQL Server)

1. Open **SQL Server Management Studio (SSMS)**.
2. Login using **SQL Server Authentication**. (User: `sa`, Password: `1`).
3. Right-click Databases -> New Database:
   * Database name: `supportportal`
4. Make sure the `ODBC Driver 18 for SQL Server` is installed on your Windows machine if developing natively. (Docker image handles it via Microsoft repo in the Dockerfile).

---

## Configuration (`.env`)

1. Copy `.env.example` to `.env`.
2. Open `.env` and set your connection strings specifically for Docker to reach your host's SQL server.
    *   *Docker trick:* `host.docker.internal` allows your Docker container to bridge onto your Windows localhost.

```ini
# Core
PROJECT_NAME="Edgeworks Cloud Support Portal"
ENVIRONMENT="production"
DEBUG=False

# Database (SQL Server 2025 inside Docker)
# Format: mssql+pyodbc://username:password@hostname/database?driver=...
DATABASE_URL="mssql+pyodbc://sa:1@host.docker.internal/supportportal?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"

# Security (Generate random hashes via python -c "import secrets; print(secrets.token_hex(32))")
AUTH_SECRET_KEY="<YOUR_SECRET_KEY>"
JWT_SECRET_KEY="<YOUR_JWT_KEY>"

# AI Config
OPENAI_API_KEY="sk-..."
RAG_DATA_DIR="./data/knowledge"
VECTOR_DB_PATH="./data/faiss"
```

## 🐋 Step 3: Launching via Docker

The repository includes a comprehensive `Dockerfile` configured to pre-install PyODBC and all Microsoft ODBC Drivers 18 required for SQL Server connection.

1. Open PowerShell / Command Prompt as Administrator.
2. Navigate to your project directory:
   ```cmd
   cd D:\Project\support-ai
   ```
3. Build the backend image safely:
   ```cmd
   docker build -t support-ai .
   ```
4. Run the container:
   ```cmd
   docker run -d --name support-ai --restart always -p 8001:8001 -p 80:8001 --env-file .env support-ai
   ```

*Check logs if it fails:*
```cmd
docker logs support-ai
```

## 🔄 Step 4: Database Migrations (Run Once)
Since the production database is fresh, you need to apply Alembic schemas.

Run this against your active Docker container:
```cmd
docker exec -it support-ai alembic upgrade head
```

## ☁️ Step 5: (Optional) Integrating AWS S3 for Attachments
If you plan to scale the storage of uploaded CSVs, PDFs, and Chat Images:
1. Add AWS variables to your `.env`:
   ```ini
   AWS_ACCESS_KEY_ID="AKIA..."
   AWS_SECRET_ACCESS_KEY="..."
   AWS_REGION="ap-southeast-1"
   S3_BUCKET_NAME="edgeworks-support-bucket"
   ```
2. The internal `file_handler.py` (which currently saves objects locally) can easily be subclassed to stream arrays strictly to `boto3`.

## ✅ Validation Checklist
- Go to `http://localhost/health` to confirm the SQL database reflects as `"up"`.
- Verify the Web Portal loads on port `80` globally via your Office router's IP if forwarding is configured.
