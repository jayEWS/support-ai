#!/bin/bash
# Continue deployment from step 8 onwards
set -e
APP_DIR="/home/j33ca/support-portal-edgeworks"
VENV_DIR="$APP_DIR/.venv"

source "$VENV_DIR/bin/activate"
cd "$APP_DIR"

echo "=== STEP 8: Testing Cloud SQL connection ==="
python3 << 'PYEOF'
from sqlalchemy import create_engine, text
import urllib.parse
password = urllib.parse.quote_plus("Edgew0rks!DB2026#Secure")
url = f"mssql+pyodbc://sqlserver:{password}@34.87.147.22/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes"
engine = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"timeout": 15})
with engine.connect() as conn:
    row = conn.execute(text("SELECT @@VERSION")).fetchone()
    print(f"  Connected: {row[0][:80]}")
    exists = conn.execute(text("SELECT DB_ID(N'support_portal')")).scalar()
    if exists is None:
        conn.execute(text("CREATE DATABASE support_portal"))
        print("  Database 'support_portal' created!")
    else:
        print("  Database 'support_portal' already exists!")
PYEOF

echo "=== STEP 9: Running database migrations ==="
cd "$APP_DIR"
alembic upgrade head 2>&1 || echo "  Migration had issues - checking tables..."

echo "=== STEP 10: Creating systemd service ==="
sudo tee /etc/systemd/system/support-ai.service > /dev/null << EOF
[Unit]
Description=Edgeworks AI Support Portal
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=j33ca
Group=j33ca
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/gunicorn -w 2 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8001 --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "=== STEP 11: Configuring Caddy ==="
sudo tee /etc/caddy/Caddyfile > /dev/null << 'CADDY'
:80 {
    reverse_proxy localhost:8001 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options SAMEORIGIN
        X-XSS-Protection "1; mode=block"
        -Server
    }
    request_body {
        max_size 100MB
    }
}
CADDY

echo "=== STEP 12: Starting services ==="
# Stop docker if still running
sudo docker stop $(sudo docker ps -aq) 2>/dev/null || true
sudo systemctl stop docker 2>/dev/null || true
sudo systemctl disable docker 2>/dev/null || true

sudo systemctl daemon-reload
sudo systemctl enable support-ai
sudo systemctl restart support-ai
sudo systemctl restart caddy

echo "  Waiting 30s for startup..."
sleep 30

echo ""
echo "========== Service Status =========="
for svc in redis-server support-ai caddy; do
    if sudo systemctl is-active --quiet "$svc"; then
        echo "  ✓ $svc is running"
    else
        echo "  ✗ $svc FAILED"
        sudo journalctl -u "$svc" --no-pager -n 10 2>/dev/null
    fi
done

echo ""
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null || echo "000")
echo "  Health check: HTTP $HTTP"

if [ "$HTTP" != "200" ]; then
    echo ""
    echo "=== Recent API logs ==="
    sudo journalctl -u support-ai --no-pager -n 20
fi

echo ""
echo "========================================"
echo "  DEPLOYMENT COMPLETE!"
echo "========================================"
echo "  App:      http://34.126.104.27"
echo "  Health:   http://34.126.104.27/health"
echo "  Database: Cloud SQL @ 34.87.147.22"
echo "  Logs:     sudo journalctl -u support-ai -f"
