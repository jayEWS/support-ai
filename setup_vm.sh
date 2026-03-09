#!/bin/bash
# VM Setup Script for Support Portal Deployment

set -e

PROJECT_DIR="support-portal-edgeworks"
ARCHIVE="support-portal.tar.gz"

# 1. Extraction (Skip if archive is missing - e.g. for Git clones)
if [ -f "$ARCHIVE" ]; then
    echo "📂 Extracting project files..."
    mkdir -p "$PROJECT_DIR"
    tar -xzf "$ARCHIVE" -C "$PROJECT_DIR"
    cd "$PROJECT_DIR"
else
    echo "ℹ️  Archive not found. Assuming files are already in place."
fi

# FIX CRLF to LF for all script files (crucial for Windows-to-Linux upload)
echo "🧹 Fixing line endings for scripts..."
find . -name "*.sh" -exec sed -i 's/\r$//' {} +

echo "🔧 Configuring environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from template."
else
    echo ".env already exists. Skipping creation."
fi

# Generate secrets if they are default/empty
AUTH_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

# Update secrets in .env
sed -i "s|^AUTH_SECRET_KEY=.*|AUTH_SECRET_KEY=${AUTH_KEY}|" .env
sed -i "s|^API_SECRET_KEY=.*|API_SECRET_KEY=${API_KEY}|" .env

# Enable production mode
sed -i "s|^DEBUG=true|DEBUG=false|" .env
sed -i "s|^COOKIE_SECURE=false|COOKIE_SECURE=true|" .env
sed -i "s|^COOKIE_SAMESITE=lax|COOKIE_SAMESITE=strict|" .env

# Set DATABASE_URL - Defaulting to SQL Server for production readiness
if grep -q "sqlite" .env || (grep -q "localhost" .env && ! grep -q "mssql" .env); then
    echo "🔧 Configuring production DATABASE_URL (SQL Server)..."
    
    # Active configuration for local SQL Server 2025 (matching user request sa:1)
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=mssql+pyodbc://sa:1@172.17.0.1/supportportal?driver=ODBC+Driver+18+for+SQL+Server\&TrustServerCertificate=yes|" .env
    
    echo "✅ Database set to SQL Server (Docker Host 172.17.0.1)."
fi

# Final Check
if grep -q "sqlite" .env; then
    echo "⚠️  WARNING: System is still using SQLite. SQL Server is recommended for 24/7 uptime."
fi

echo "🚀 Launching deployment script..."
chmod +x deploy_prod.sh
./deploy_prod.sh
