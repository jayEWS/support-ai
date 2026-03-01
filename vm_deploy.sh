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
# BASE_URL
sed -i 's|^BASE_URL=.*|BASE_URL=http://136.110.61.119:8000|' .env

# GOOGLE_REDIRECT_URI - add if missing, update if exists
if grep -q "^GOOGLE_REDIRECT_URI=" .env; then
    sed -i 's|^GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=http://136.110.61.119:8000/api/auth/google/callback|' .env
else
    echo "GOOGLE_REDIRECT_URI=http://136.110.61.119:8000/api/auth/google/callback" >> .env
fi

# Supabase pooler URL (IPv4, port 6543)
if grep -q "aws-0-ap-southeast-1.pooler.supabase.com:5432" .env; then
    sed -i 's|aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres|aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres|' .env
    sed -i 's|postgresql+psycopg2://postgres:|postgresql+psycopg2://postgres.wjsaltebtbmnysgcdsoh:|' .env
fi

echo "--- .env preview (sensitive values masked) ---"
grep -E "^(BASE_URL|GOOGLE_REDIRECT_URI|DATABASE_URL|EMAIL_PROVIDER)" .env | sed 's|://[^@]*@|://***@|'

echo "=== [3/6] Stop & remove old container ==="
sudo docker stop support-ai 2>/dev/null || true
sudo docker rm support-ai 2>/dev/null || true

echo "=== [4/6] Build new Docker image ==="
sudo docker build -t support-ai .

echo "=== [5/6] Upload knowledge files to data/knowledge ==="
mkdir -p ~/support-portal/data/knowledge
mkdir -p ~/support-portal/data/db_storage

# Run vm_upload.sh if it exists (uploads base64-encoded knowledge TXT files)
if [ -f ~/support-portal/vm_upload.sh ]; then
    echo "Running vm_upload.sh to restore knowledge files..."
    # Extract files to local data dir, then they'll be mounted via volume
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
echo "Done! App running at http://136.110.61.119:8000"
echo "============================================"
