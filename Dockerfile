# Multi-stage Dockerfile for FastAPI Support Portal
# Production-ready with security hardening and optimized caching

# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies (only in builder stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    unixodbc-dev \
    gnupg2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Add Microsoft GPG key for ODBC driver
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list

# Install ODBC driver (required for SQL Server connections)
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and build Python dependencies in isolated layer (for Docker cache)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (ODBC, ffmpeg for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    unixodbc \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy ODBC driver from builder
COPY --from=builder /usr/share/keyrings/microsoft-prod.gpg /usr/share/keyrings/
COPY --from=builder /etc/apt/sources.list.d/mssql-release.list /etc/apt/sources.list.d/
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder (keeps image lean)
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache

# Copy application code
COPY . .

# Create non-root user with minimal privileges (security hardening)
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Pre-create data directories with correct permissions
RUN mkdir -p data/knowledge data/db_storage data/uploads/chat .cache && \
    chown -R appuser:appuser /app/data /app/.cache /app/migrations

# Switch to non-root user
USER appuser

# Health check for orchestrators (Kubernetes, Docker Swarm, ECS)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

# Production-optimized Gunicorn configuration:
# - 2 workers for concurrent requests (increase with more CPU cores)
# - 120s timeout for LLM inference (adjust based on your model latency)
# - --preload shares model cache across workers (saves ~200MB RAM)
# - --graceful-timeout=30 allows proper shutdown sequence
CMD ["gunicorn", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "main:app", \
     "--bind", "0.0.0.0:8001", \
     "--timeout", "120", \
     "--preload", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
