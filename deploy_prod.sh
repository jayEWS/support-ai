#!/bin/bash
# Edgeworks Support Portal - Production Setup Script (Free Forever Mode)

echo "🚀 Starting Production Deployment..."

# 1. Enable SWAP (Critical for 1GB/2GB RAM VMs)
if [ ! -f /swapfile ]; then
    echo "📦 Configuring 2GB Swap Memory..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 2. Install Docker & Compose (If missing)
if ! [ -x "$(command -v docker)" ]; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
fi

# 3. Create Data Directories
mkdir -p data/db_storage data/knowledge data/uploads

# 4. Check for .env
if [ ! -f .env ]; then
    echo "⚠️  WARNING: .env file missing! Creating template..."
    cp .env.example .env
    echo "🚨 ACTION REQUIRED: Please edit the .env file with your real keys before proceeding."
    exit 1
fi

# 5. Build and Launch
echo "🔥 Launching Containers (WAL Mode Enabled)..."

# Detect Docker Compose version (V1 vs V2)
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose --version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "❌ ERROR: Docker Compose not found! Please install it."
    exit 1
fi

sudo $DOCKER_COMPOSE -f docker-compose.prod.yml up --build -d

echo "✅ DEPLOYMENT COMPLETE!"
echo "Your API is running on port 8001 (Internal: 8000)."
echo "Check logs with: sudo docker compose -f docker-compose.prod.yml logs -f"
