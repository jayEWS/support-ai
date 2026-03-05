# Production-ready Dockerfile for FastAPI deployment
# Supports: Koyeb, Render, Railway, AWS, GCP, Azure, or local Docker

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (combined for smaller image)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Pre-create data directories
RUN mkdir -p data/knowledge data/db_storage data/uploads/chat

# Health check (start-period allows time for AI models to load)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# 2 workers for concurrent client handling, 120s timeout for AI responses
# --preload shares FAISS index across workers (saves ~200MB RAM)
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--timeout", "120", "--preload", "--graceful-timeout", "30"]
