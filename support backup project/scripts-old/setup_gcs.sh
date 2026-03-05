#!/bin/bash
# ============================================================
# setup_gcs.sh — One-command GCS setup for Support AI
# 
# Prerequisites:
#   1. GCS bucket sudah dibuat di GCP Console
#   2. Service account JSON key sudah di-download
#   3. Key file sudah di-upload ke VM
#
# Usage:
#   # Upload key ke VM dulu dari PC lokal:
#   scp ~/Downloads/sa-key.json jay@136.110.61.119:~/support-portal/sa-key.json
#
#   # Lalu SSH ke VM dan jalankan:
#   cd ~/support-portal && bash scripts/setup_gcs.sh
#
#   # Atau dengan custom bucket name:
#   bash scripts/setup_gcs.sh --bucket my-custom-bucket --project my-project-id
# ============================================================
set -e

# Defaults
BUCKET_NAME="support-edgeworks-knowledge"
PROJECT_ID="tcare-edgeworks"
SA_KEY_PATH="$HOME/support-portal/sa-key.json"
ENV_FILE="$HOME/support-portal/.env"
CONTAINER_NAME="support-ai"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket)  BUCKET_NAME="$2"; shift 2;;
        --project) PROJECT_ID="$2"; shift 2;;
        --key)     SA_KEY_PATH="$2"; shift 2;;
        --help)
            echo "Usage: bash setup_gcs.sh [--bucket NAME] [--project ID] [--key /path/to/sa-key.json]"
            exit 0;;
        *) echo "Unknown arg: $1"; exit 1;;
    esac
done

echo "============================================"
echo "  GCS Setup for Support AI — Phase 2"
echo "============================================"
echo ""
echo "  Bucket:     $BUCKET_NAME"
echo "  Project:    $PROJECT_ID"
echo "  SA Key:     $SA_KEY_PATH"
echo "  Container:  $CONTAINER_NAME"
echo ""

# ── Step 1: Check SA key file ──
echo "=== [1/5] Checking Service Account key ==="
if [ ! -f "$SA_KEY_PATH" ]; then
    echo "❌ Service account key not found: $SA_KEY_PATH"
    echo ""
    echo "Upload it from your PC first:"
    echo "  scp ~/Downloads/sa-key.json jay@136.110.61.119:~/support-portal/sa-key.json"
    echo ""
    exit 1
fi

# Validate JSON
if ! python3 -c "import json; json.load(open('$SA_KEY_PATH'))" 2>/dev/null; then
    echo "❌ Invalid JSON in $SA_KEY_PATH"
    exit 1
fi

SA_EMAIL=$(python3 -c "import json; print(json.load(open('$SA_KEY_PATH')).get('client_email', 'unknown'))")
echo "  ✅ Key found — SA: $SA_EMAIL"

# ── Step 2: Update .env ──
echo ""
echo "=== [2/5] Updating .env ==="

# GCS_ENABLED
if grep -q "^GCS_ENABLED=" "$ENV_FILE"; then
    sed -i "s|^GCS_ENABLED=.*|GCS_ENABLED=True|" "$ENV_FILE"
else
    echo "GCS_ENABLED=True" >> "$ENV_FILE"
fi

# GCS_BUCKET_NAME
if grep -q "^GCS_BUCKET_NAME=" "$ENV_FILE"; then
    sed -i "s|^GCS_BUCKET_NAME=.*|GCS_BUCKET_NAME=$BUCKET_NAME|" "$ENV_FILE"
else
    echo "GCS_BUCKET_NAME=$BUCKET_NAME" >> "$ENV_FILE"
fi

# GCP_PROJECT_ID
if grep -q "^GCP_PROJECT_ID=" "$ENV_FILE"; then
    sed -i "s|^GCP_PROJECT_ID=.*|GCP_PROJECT_ID=$PROJECT_ID|" "$ENV_FILE"
else
    echo "GCP_PROJECT_ID=$PROJECT_ID" >> "$ENV_FILE"
fi

# GOOGLE_APPLICATION_CREDENTIALS (path inside container)
if grep -q "^GOOGLE_APPLICATION_CREDENTIALS=" "$ENV_FILE"; then
    sed -i "s|^GOOGLE_APPLICATION_CREDENTIALS=.*|GOOGLE_APPLICATION_CREDENTIALS=/app/sa-key.json|" "$ENV_FILE"
else
    echo "GOOGLE_APPLICATION_CREDENTIALS=/app/sa-key.json" >> "$ENV_FILE"
fi

echo "  ✅ .env updated:"
grep -E "^(GCS_|GCP_|GOOGLE_APPLICATION)" "$ENV_FILE"

# ── Step 3: Restart container with SA key mount ──
echo ""
echo "=== [3/5] Restarting container with SA key ==="

sudo docker stop $CONTAINER_NAME 2>/dev/null || true
sudo docker rm $CONTAINER_NAME 2>/dev/null || true

sudo docker run -d \
    --name $CONTAINER_NAME \
    --restart always \
    -p 8000:8000 \
    -v ~/support-portal/data:/app/data \
    -v "$SA_KEY_PATH":/app/sa-key.json:ro \
    --env-file "$ENV_FILE" \
    support-ai

echo "  ✅ Container started with SA key mounted"

# ── Step 4: Wait and check logs ──
echo ""
echo "=== [4/5] Waiting for startup (15s)... ==="
sleep 15

echo "--- Container logs (GCS related) ---"
sudo docker logs $CONTAINER_NAME 2>&1 | grep -i "gcs\|bucket\|storage\|cloud" || echo "  (no GCS logs yet)"

echo ""
echo "--- Health check ---"
curl -sf http://localhost:8000/health && echo " <- OK" || echo " <- FAILED (container may still be starting)"

# ── Step 5: Run migration ──
echo ""
echo "=== [5/5] Migrating knowledge files to GCS ==="
echo "Running migrate_to_gcs.py inside container..."
echo ""

sudo docker exec $CONTAINER_NAME python scripts/migrate_to_gcs.py

# ── Done ──
echo ""
echo "============================================"
echo "  ✅ GCS Setup Complete!"
echo "============================================"
echo ""
echo "  Bucket:  gs://$BUCKET_NAME/knowledge/"
echo "  Status:  curl http://localhost:8000/api/gcs/status"
echo ""
echo "  All future knowledge uploads will auto-sync to GCS."
echo "  Existing files have been migrated above."
echo "============================================"
