# Support AI - Free Tier Deployment Guide

This project has been optimized to run completely free using lightweight, file-based services by default.

## 🚀 Quick Start (Local)

1.  **Clone & Install**:
    ```bash
    git clone <repo>
    cd support-ai
    pip install -r requirements.txt
    ```

2.  **Configure Environment**:
    Copy `.env.example` to `.env` (or just rely on defaults).
    You only need **ONE** key: `GOOGLE_GEMINI_API_KEY` (Get it free from [Google AI Studio](https://aistudio.google.com/)).

    ```bash
    # Linux/Mac
    export GOOGLE_GEMINI_API_KEY="your_key_here"
    
    # Windows (PowerShell)
    $env:GOOGLE_GEMINI_API_KEY="your_key_here"
    ```

3.  **Run**:
    ```bash
    python main.py
    ```
    or
    ```bash
    uvicorn main:app --reload
    ```

## 🛠️ What's Changed for Free Tier?

*   **Database**: Defaults to **SQLite** (`data/db_storage/app.db`). No external SQL Server required.
*   **Vector Search**: Defaults to **Local Qdrant** (`data/qdrant_storage`). No cloud vector DB required.
*   **LLM**: Defaults to **Google Gemini** (Free Tier).
*   **Hosting**: Ready for **Hugging Face Spaces**.

## ☁️ Deploy to Hugging Face Spaces (Free)

1.  Create a new Space (Docker SDK).
2.  Upload this repository.
3.  Set `GOOGLE_GEMINI_API_KEY` in the Space Secrets.
4.  The app will automatically start using SQLite and Local Vector Store. No other setup needed!

## 🔐 Advanced Configuration

If you want to upgrade later, just set the environment variables:
*   `DATABASE_URL` -> Switch to Postgres/SQL Server.
*   `QDRANT_URL` -> Switch to Qdrant Cloud.
*   `REDIS_URL` -> Enable Redis for multi-worker scaling.
