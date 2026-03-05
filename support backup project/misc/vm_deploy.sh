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

# Auto-detect external IP and build nip.io domain
EXTERNAL_IP=$(curl -sf ifconfig.me || curl -sf ipinfo.io/ip || echo "")
if [ -z "$EXTERNAL_IP" ]; then
    echo "⚠️  Could not detect external IP, using existing BASE_URL"
else
    NIP_DOMAIN=$(echo "$EXTERNAL_IP" | tr '.' '-').nip.io
    echo "  → Detected IP: $EXTERNAL_IP → $NIP_DOMAIN"
    
    # BASE_URL
    sed -i "s|^BASE_URL=.*|BASE_URL=http://${NIP_DOMAIN}:8000|" .env
    
    # GOOGLE_REDIRECT_URI
    if grep -q "^GOOGLE_REDIRECT_URI=" .env; then
        sed -i "s|^GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=http://${NIP_DOMAIN}:8000/api/auth/google/callback|" .env
    else
        echo "GOOGLE_REDIRECT_URI=http://${NIP_DOMAIN}:8000/api/auth/google/callback" >> .env
    fi
fi

# Gemini LLM Provider
sed -i 's|^LLM_PROVIDER=.*|LLM_PROVIDER=gemini|' .env
if grep -q "^GOOGLE_GEMINI_API_KEY=" .env; then
    sed -i 's|^GOOGLE_GEMINI_API_KEY=.*|GOOGLE_GEMINI_API_KEY=AIzaSyA0N2iJTZWZYx1mn7JgPDMsXuQsiRUQfsw|' .env
else
    echo "GOOGLE_GEMINI_API_KEY=AIzaSyA0N2iJTZWZYx1mn7JgPDMsXuQsiRUQfsw" >> .env
fi
if ! grep -q "^GEMINI_MODEL_NAME=" .env; then
    echo "GEMINI_MODEL_NAME=gemini-2.5-flash" >> .env
fi

# Supabase pooler (IPv4, port 6543)
if grep -q "db.wjsaltebtbmnysgcdsoh.supabase.co" .env; then
    sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg2://postgres.wjsaltebtbmnysgcdsoh:Tekansaja123@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres|' .env
fi

# GCS Config (Phase 2) — auto-enable if sa-key.json exists
if [ -f ~/support-portal/sa-key.json ]; then
    echo "  → sa-key.json found, enabling GCS"
    if grep -q "^GCS_ENABLED=" .env; then
        sed -i 's|^GCS_ENABLED=.*|GCS_ENABLED=True|' .env
    else
        echo "GCS_ENABLED=True" >> .env
    fi
    if ! grep -q "^GOOGLE_APPLICATION_CREDENTIALS=" .env; then
        echo "GOOGLE_APPLICATION_CREDENTIALS=/app/sa-key.json" >> .env
    fi
else
    if ! grep -q "^GCS_ENABLED=" .env; then
        echo "GCS_ENABLED=False" >> .env
    fi
fi
if ! grep -q "^GCS_BUCKET_NAME=" .env; then
    echo "GCS_BUCKET_NAME=support-edgeworks-knowledge" >> .env
fi
if ! grep -q "^GCP_PROJECT_ID=" .env; then
    echo "GCP_PROJECT_ID=tcare-edgeworks" >> .env
fi

echo "--- .env preview (sensitive values masked) ---"
grep -E "^(BASE_URL|LLM_PROVIDER|GEMINI_MODEL_NAME|GCS_ENABLED|GCS_BUCKET_NAME|GOOGLE_REDIRECT_URI|DATABASE_URL)" .env | sed 's|://[^@]*@|://***@|'

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
# Mount sa-key.json for GCS access (Phase 2) if it exists
SA_KEY_MOUNT=""
if [ -f ~/support-portal/sa-key.json ]; then
    SA_KEY_MOUNT="-v ~/support-portal/sa-key.json:/app/sa-key.json:ro"
    echo "  → Mounting sa-key.json for GCS access"
fi

sudo docker run -d \
    --name support-ai \
    --restart always \
    -p 8000:8000 \
    -v ~/support-portal/data:/app/data \
    $SA_KEY_MOUNT \
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
if [ -n "$NIP_DOMAIN" ]; then
    echo "Done! App running at http://${NIP_DOMAIN}:8000"
else
    echo "Done! App running at http://localhost:8000"
fi
echo "============================================"
