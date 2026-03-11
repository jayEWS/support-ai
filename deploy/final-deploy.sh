#!/bin/bash
# Final deployment: extract fresh code, preserve .env, migrate, restart
set -e
APP_DIR="/home/j33ca/support-portal-edgeworks"
VENV="$APP_DIR/.venv"

echo "=== STEP 1: Backup .env and data ==="
cp "$APP_DIR/.env" /tmp/.env.backup
cp -r "$APP_DIR/data" /tmp/data.backup 2>/dev/null || true
echo "  .env and data backed up"

echo "=== STEP 2: Extract fresh code ==="
cd "$APP_DIR"
# Remove old app code but keep .env, .venv, data, .git
find "$APP_DIR" -maxdepth 1 -not -name '.env' -not -name '.venv' -not -name 'data' -not -name '.git' -not -name '.' -not -name '..' -exec rm -rf {} + 2>/dev/null || true

# Extract fresh code
tar -xzf /tmp/deploy-code.tar.gz -C "$APP_DIR"
echo "  Fresh code extracted"

# Restore .env
cp /tmp/.env.backup "$APP_DIR/.env"
echo "  .env restored"

# Restore data directory
cp -r /tmp/data.backup/* "$APP_DIR/data/" 2>/dev/null || true

echo "=== STEP 3: Verify config ==="
cd "$APP_DIR"
$VENV/bin/python3 -c "
from app.core.config import settings
print(f'  DB: {settings.DATABASE_URL[:60]}')
print(f'  Origins: {settings.parsed_origins}')
print('  Config OK')
"

echo "=== STEP 4: Fix alembic % interpolation ==="
# The % in Cloud SQL password causes configparser issues
# Fix: override set_main_option to escape % chars
cd "$APP_DIR"
# Create a wrapper that escapes % for configparser
sed -i 's|config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)|config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))|' migrations/env.py
echo "  alembic env.py patched for % escaping"

echo "=== STEP 5: Run migrations ==="
$VENV/bin/alembic upgrade head 2>&1 | tail -5
echo "  Migrations complete"

echo "=== STEP 6: Fix permissions ==="
sudo chown -R j33ca:j33ca "$APP_DIR"
echo "  Permissions fixed"

echo "=== STEP 7: Restart services ==="
sudo systemctl daemon-reload
sudo systemctl restart support-ai
sudo systemctl restart caddy
echo "  Services restarting..."
sleep 15

echo "=== STEP 8: Health check ==="
for i in 1 2 3; do
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
        break
    fi
    echo "  Attempt $i: HTTP $HTTP, waiting..."
    sleep 10
done

echo ""
echo "========== Service Status =========="
for svc in redis-server support-ai caddy; do
    if sudo systemctl is-active --quiet "$svc"; then
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
    sudo journalctl -u support-ai --no-pager -n 30
fi
