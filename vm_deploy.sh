#!/bin/bash
# ============================================================
# vm_deploy.sh - Full deploy script for support-ai on GCP VM
# Run this on the VM: bash ~/support-portal/vm_deploy.sh
# ============================================================
set -e

echo "=== [1/6] Pull latest code ==="
cd ~/support-portal
git fetch origin main
git reset --hard origin/main

echo "=== [2/6] Update .env ==="

# BASE_URL (Main Portal on GCP)
GCP_IP="136.110.61.119"
PORT="8000"
sed -i "s|^BASE_URL=.*|BASE_URL=http://$GCP_IP.nip.io:$PORT|" .env

# GOOGLE_REDIRECT_URI (Must match Google Cloud Console)
REDIRECT_URI="http://$GCP_IP.nip.io:$PORT/api/auth/google/callback"
if grep -q "^GOOGLE_REDIRECT_URI=" .env; then
    sed -i "s|^GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=$REDIRECT_URI|" .env
else
    echo "GOOGLE_REDIRECT_URI=$REDIRECT_URI" >> .env
fi

# AI & LLM CONFIGURATION (Ngrok for Chat/AI if provided)
# Note: Set NGROK_URL environment variable before running this script
if [ ! -z "$NGROK_URL" ]; then
    echo "Updating AI_BASE_URL to Ngrok: $NGROK_URL"
    sed -i "s|^AI_BASE_URL=.*|AI_BASE_URL=$NGROK_URL|" .env
fi

# ALLOWED_ORIGINS (CORS fix)
ALLOW_ORIGIN="\"http://$GCP_IP.nip.io:$PORT\", \"http://localhost:8000\""
if [ ! -z "$NGROK_URL" ]; then
    ALLOW_ORIGIN="$ALLOW_ORIGIN, \"$NGROK_URL\""
fi
sed -i "s|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=[$ALLOW_ORIGIN]|" .env

# Supabase direct connection for stability on VM
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg2://postgres:Tekansaja123@db.wjsaltebtbmnysgcdsoh.supabase.co:5432/postgres|' .env

echo "--- .env preview (sensitive values masked) ---"
grep -E "^(BASE_URL|GOOGLE_REDIRECT_URI|DATABASE_URL|AI_BASE_URL)" .env | sed 's|://[^@]*@|://***@|'

echo "=== [3/6] Stop & remove old container ==="
sudo docker stop support-ai 2>/dev/null || true
sudo docker rm support-ai 2>/dev/null || true

echo "=== [4/6] Build new Docker image ==="
# Using --no-cache to ensure fresh build with updated requirements
sudo docker build --no-cache -t support-ai .

echo "=== [5/6] Upload knowledge files to data/knowledge ==="
mkdir -p ~/support-portal/data/knowledge
mkdir -p ~/support-portal/data/db_storage

# Run vm_upload.sh if it exists (uploads base64-encoded knowledge TXT files)
if [ -f ~/support-portal/vm_upload.sh ]; then
    echo "Running vm_upload.sh to restore knowledge files..."
    bash ~/support-portal/vm_upload.sh 2>/dev/null || true
fi

echo "=== [6/6] Start container with volume mount ==="
sudo docker run -d \
    --name support-ai \
    --restart always \
    -p 8000:8000 \
    -v ~/support-portal/data:/app/data \
    --env-file ~/support-portal/.env \
    support-ai

echo ""
echo "=== Waiting 10s for startup... ==="
sleep 10
sudo docker logs support-ai --tail 40

echo ""
echo "=== Health check ==="
curl -sf http://localhost:8000/health && echo " <- OK" || echo " <- FAILED"

echo ""
echo "============================================"
echo "Done! App running at http://$GCP_IP.nip.io:$PORT"
echo "============================================"
