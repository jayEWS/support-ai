# ============================================================
# Edgeworks Support AI — Production Dockerfile
# ============================================================
# Multi-stage build for minimal image size and security.
# ============================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Production stage ──
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p data/knowledge data/db_storage data/uploads/chat data/uploads/knowledge \
    && chown -R appuser:appuser /app

# Remove sensitive files that should never be in the image
RUN rm -f .env .env.local .env.production 2>/dev/null || true

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

# Run with Uvicorn (production config)
# Workers should be 2 * CPU cores + 1 (set via UVICORN_WORKERS env var)
CMD ["python", "-m", "uvicorn", "main:app", \
    "--host", "0.0.0.0", \
    "--port", "8001", \
    "--workers", "4", \
    "--limit-concurrency", "100", \
    "--timeout-keep-alive", "30"]
