#!/bin/bash
# ============================================================
# vm_deploy_https.sh - GCP Deploy with HTTPS via Ngrok
# Run this on the VM: bash ~/support-portal/vm_deploy_https.sh <YOUR_NGROK_AUTHTOKEN>
# ============================================================
set -e

NGROK_TOKEN=$1

if [ -z "$NGROK_TOKEN" ]; then
    echo "❌ Error: Ngrok Authtoken isi sebagai argumen pertama!"
    echo "Contoh: bash vm_deploy_https.sh 3A4Gxy..."
    exit 1
fi

echo "=== [1/7] Pull latest code ==="
cd ~/support-portal
git fetch origin main
git reset --hard origin/main

echo "=== [2/7] Setup Ngrok on VM ==="
if ! command -v ngrok &> /dev/null; then
    echo "Installing Ngrok..."
    curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
    echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
    sudo apt-get update && sudo apt-get install ngrok
fi

ngrok config add-authtoken "$NGROK_TOKEN"

# Stop existing ngrok
sudo pkill ngrok || true
sleep 2

# Start ngrok in background
echo "Starting Ngrok Tunnel..."
ngrok http 8000 --log=stdout > ngrok.log &
sleep 10

# Extract HTTPS URL from Ngrok API
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*' | head -n 1)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Error: Gagal mendapatkan URL Ngrok. Cek ngrok.log"
    cat ngrok.log
    exit 1
fi

echo "🚀 NGROK HTTPS URL: $NGROK_URL"

echo "=== [3/7] Update .env for HTTPS ==="
# BASE_URL (Ngrok HTTPS)
sed -i "s|^BASE_URL=.*|BASE_URL=$NGROK_URL|" .env

# GOOGLE_REDIRECT_URI (Sync with Ngrok)
REDIRECT_URI="$NGROK_URL/api/auth/google/callback"
if grep -q "^GOOGLE_REDIRECT_URI=" .env; then
    sed -i "s|^GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=$REDIRECT_URI|" .env
else
    echo "GOOGLE_REDIRECT_URI=$REDIRECT_URI" >> .env
fi

# ALLOWED_ORIGINS (CORS fix for HTTPS)
ALLOW_ORIGIN="\"$NGROK_URL\", \"http://localhost:8000\""
sed -i "s|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=[$ALLOW_ORIGIN]|" .env

# Security Settings for HTTPS
sed -i "s|^COOKIE_SECURE=.*|COOKIE_SECURE=true|" .env
sed -i "s|^COOKIE_SAMESITE=.*|COOKIE_SAMESITE=lax|" .env

# Supabase direct connection
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg2://postgres:Tekansaja123@db.wjsaltebtbmnysgcdsoh.supabase.co:5432/postgres|' .env

echo "--- .env preview (sensitive values masked) ---"
grep -E "^(BASE_URL|GOOGLE_REDIRECT_URI|DATABASE_URL|COOKIE_SECURE)" .env | sed 's|://[^@]*@|://***@|'

echo "=== [4/7] Stop & remove old container ==="
sudo docker stop support-ai 2>/dev/null || true
sudo docker rm support-ai 2>/dev/null || true

echo "=== [5/7] Build new Docker image ==="
sudo docker build --no-cache -t support-ai .

echo "=== [6/7] Upload knowledge files to data/knowledge ==="
mkdir -p ~/support-portal/data/knowledge
mkdir -p ~/support-portal/data/db_storage

if [ -f ~/support-portal/vm_upload.sh ]; then
    bash ~/support-portal/vm_upload.sh 2>/dev/null || true
fi

echo "=== [7/7] Start container ==="
sudo docker run -d \
    --name support-ai \
    --restart always \
    -p 8000:8000 \
    -v ~/support-portal/data:/app/data \
    --env-file ~/support-portal/.env \
    support-ai

echo ""
echo "============================================"
echo "✅ DEPLOY SUCCESSFUL (HTTPS)"
echo "PORTAL URL: $NGROK_URL"
echo "============================================"
echo "⚠️ REMINDER: Update Redirect URI in Google Console to:"
echo "$REDIRECT_URI"
