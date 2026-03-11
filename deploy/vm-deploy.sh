#!/bin/bash
# Deploy fresh code to VM - preserve .env and venv, extract code, restart
set -e
APP_DIR="/home/j33ca/support-portal-edgeworks"
VENV="$APP_DIR/.venv"

echo "=== STEP 1: Backup .env ==="
cp "$APP_DIR/.env" /tmp/.env.backup 2>/dev/null || true
echo "  Done"

echo "=== STEP 2: Clean old code (keep .env, .venv, data, .git) ==="
cd "$APP_DIR"
rm -rf app/ main.py requirements.txt alembic.ini migrations/ gunicorn_conf.py templates/ scripts/ 2>/dev/null || true
echo "  Old code removed"

echo "=== STEP 3: Extract fresh code ==="
tar -xzf /tmp/deploy-code.tar.gz -C "$APP_DIR"
cp /tmp/.env.backup "$APP_DIR/.env" 2>/dev/null || true
echo "  Fresh code deployed, .env preserved"

echo "=== STEP 4: Rebuild venv if needed ==="
if [ ! -f "$VENV/bin/python3" ]; then
    echo "  Creating venv..."
    python3 -m venv "$VENV"
fi
echo "  Installing requirements..."
$VENV/bin/pip install --upgrade pip -q 2>&1 | tail -1
$VENV/bin/pip install -r "$APP_DIR/requirements.txt" -q 2>&1 | tail -3
$VENV/bin/pip install alembic -q 2>&1 | tail -1
echo "  Dependencies ready"

echo "=== STEP 5: Verify config loads ==="
cd "$APP_DIR"
$VENV/bin/python3 -c "
from app.core.config import settings
print(f'  DB: {settings.DATABASE_URL[:60]}')
print(f'  Origins: {settings.parsed_origins}')
print('  Config OK')
" || { echo "CONFIG FAILED"; exit 1; }

echo "=== STEP 6: Fix alembic % in password ==="
sed -i 's|config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)|config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))|' migrations/env.py
echo "  Done"

echo "=== STEP 7: Run migrations ==="
$VENV/bin/alembic upgrade head 2>&1 | tail -5
echo "  Migrations complete"

echo "=== STEP 8: Create data dirs & fix perms ==="
mkdir -p "$APP_DIR/data/knowledge" "$APP_DIR/data/db_storage" "$APP_DIR/data/uploads"
chown -R j33ca:j33ca "$APP_DIR"

echo "=== STEP 9: Restart services ==="
systemctl daemon-reload
systemctl restart support-ai
systemctl restart caddy
echo "  Services restarting..."
sleep 20

echo "=== STEP 10: Health check ==="
for i in 1 2 3 4 5 6; do
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then break; fi
    echo "  Attempt $i: HTTP $HTTP, retrying..."
    sleep 5
done

echo ""
echo "========== Service Status =========="
for svc in redis-server support-ai caddy; do
    if systemctl is-active --quiet "$svc"; then
        echo "  ✓ $svc is running"
    else
        echo "  ✗ $svc FAILED"
    fi
done
echo "  Health: HTTP $HTTP"

if [ "$HTTP" = "200" ]; then
    echo ""
    echo "========================================="
    echo "  ✓ DEPLOYMENT SUCCESSFUL!"
    echo "========================================="
    echo "  App:    http://34.126.104.27"
    echo "  Health: http://34.126.104.27/health"
    echo "  DB:     Cloud SQL @ 34.87.147.22"
else
    echo ""
    echo "=== Recent logs ==="
    journalctl -u support-ai --no-pager -n 30
fi
