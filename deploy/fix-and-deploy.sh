#!/bin/bash
# Deploy fixes to GCP VM - apply ALLOWED_ORIGINS fix, run migrations, restart service
set -e
APP_DIR="/home/j33ca/support-portal-edgeworks"
VENV="$APP_DIR/.venv"

echo "=== STEP 1: Fix ALLOWED_ORIGINS in config.py ==="
cd "$APP_DIR"

# Remove old field_validator import if exists
sed -i '/^from pydantic import field_validator$/d' app/core/config.py

# Change ALLOWED_ORIGINS type from list to str
sed -i 's/ALLOWED_ORIGINS: list = \[\]/ALLOWED_ORIGINS: str = ""/' app/core/config.py

# Remove old field_validator block (6 lines after ALLOWED_ORIGINS)
# Find and remove @field_validator, @classmethod, def parse_cors_origins, and body
sed -i '/@field_validator.*ALLOWED_ORIGINS/,/return v or \[\]/d' app/core/config.py

# Add parsed_origins property after ALLOWED_ORIGINS line
sed -i '/ALLOWED_ORIGINS: str = ""/a\    \n    @property\n    def parsed_origins(self) -> list:\n        """Parse comma-separated ALLOWED_ORIGINS string into a list."""\n        if not self.ALLOWED_ORIGINS:\n            return []\n        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]' app/core/config.py

echo "  config.py patched"

echo "=== STEP 2: Fix main.py CORS ==="
sed -i 's/settings\.ALLOWED_ORIGINS if settings\.ALLOWED_ORIGINS else \[\]/settings.parsed_origins/' app/routes/websocket_routes.py
sed -i 's/_cors_origins = settings\.ALLOWED_ORIGINS if settings\.ALLOWED_ORIGINS else \[\]/_cors_origins = settings.parsed_origins/' main.py
echo "  main.py and websocket_routes.py patched"

echo "=== STEP 3: Verify config loads ==="
$VENV/bin/python3 -c "
from app.core.config import settings
print(f'  DB: {settings.DATABASE_URL[:60]}')
print(f'  Origins: {settings.parsed_origins}')
print('  ✓ Config OK')
"

echo "=== STEP 4: Install alembic if missing ==="
$VENV/bin/pip install alembic -q 2>&1 | tail -2

echo "=== STEP 5: Run migrations on Cloud SQL ==="
cd "$APP_DIR"
$VENV/bin/alembic upgrade head 2>&1 | tail -5

echo "=== STEP 6: Restart services ==="
sudo systemctl restart support-ai
sleep 10

echo "=== STEP 7: Health check ==="
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null || echo "000")
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
    echo "  ✗ Service not healthy. Checking logs..."
    sudo journalctl -u support-ai --no-pager -n 20
fi
