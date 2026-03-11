#!/bin/bash
# Rebuild venv, run migrations, start services
set -e
APP_DIR="/home/j33ca/support-portal-edgeworks"
VENV="$APP_DIR/.venv"

echo "=== STEP 1: Check what we have ==="
cd "$APP_DIR"
ls -la
echo ""
echo "Has .env: $(test -f .env && echo YES || echo NO)"
echo "Has app/: $(test -d app && echo YES || echo NO)"
echo "Has main.py: $(test -f main.py && echo YES || echo NO)"
echo "Has .venv: $(test -d .venv && echo YES || echo NO)"

echo "=== STEP 2: Restore .env if missing ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cp /tmp/.env.backup "$APP_DIR/.env"
    echo "  .env restored from backup"
fi

echo "=== STEP 3: Recreate venv ==="
python3 -m venv "$VENV"
echo "  venv created"

echo "=== STEP 4: Install requirements ==="
$VENV/bin/pip install --upgrade pip -q
$VENV/bin/pip install -r "$APP_DIR/requirements.txt" -q 2>&1 | tail -3
$VENV/bin/pip install alembic -q
echo "  Requirements installed"

echo "=== STEP 5: Verify config ==="
cd "$APP_DIR"
$VENV/bin/python3 -c "
from app.core.config import settings
print(f'  DB: {settings.DATABASE_URL[:60]}')
print(f'  Origins: {settings.parsed_origins}')
print('  Config OK')
"

echo "=== STEP 6: Fix alembic % interpolation ==="
sed -i 's|config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)|config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))|' migrations/env.py
echo "  alembic env.py patched"

echo "=== STEP 7: Run migrations ==="
$VENV/bin/alembic upgrade head 2>&1 | tail -5
echo "  Migrations done"

echo "=== STEP 8: Create data dirs ==="
mkdir -p "$APP_DIR/data/knowledge" "$APP_DIR/data/db_storage" "$APP_DIR/data/uploads"

echo "=== STEP 9: Fix permissions ==="
chown -R j33ca:j33ca "$APP_DIR"

echo "=== STEP 10: Restart services ==="
systemctl daemon-reload
systemctl restart support-ai
systemctl restart caddy
echo "  Services restarting..."
sleep 20

echo "=== STEP 11: Health check ==="
for i in 1 2 3 4 5; do
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
        break
    fi
    echo "  Attempt $i: HTTP $HTTP, waiting..."
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

echo ""
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
