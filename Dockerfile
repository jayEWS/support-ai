# Production-ready Dockerfile for FastAPI deployment
# Supports: Koyeb, Render, Railway, AWS, GCP, Azure, or local Docker

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies, including ODBC Driver 18 for SQL Server
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc-dev \
    gcc \
    g++ \
    libpq-dev \
    build-essential \
    ffmpeg \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Security Fix M4: Create non-root user and set ownership
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Pre-create data directories with correct permissions
RUN mkdir -p data/knowledge data/db_storage data/uploads/chat \
    && chown -R appuser:appuser /app/data

# Switch to non-root user
USER appuser

# Health check (start-period allows time for AI models to load)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# 2 workers for concurrent client handling, 120s timeout for AI responses
# --preload shares FAISS index across workers (saves ~200MB RAM)
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--timeout", "120", "--preload", "--graceful-timeout", "30"]
