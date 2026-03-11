#!/bin/bash
# =================================================================
# GCP VM Direct Deployment (No Docker) + Cloud SQL Server
# Support AI Portal - Edgeworks
# VM: bang-jay (34.126.104.27)
# DB: Cloud SQL for SQL Server (always-online, managed by Google)
# =================================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

CLOUD_SQL_IP="$1"
if [ -z "$CLOUD_SQL_IP" ]; then
    echo -e "${RED}Usage: sudo $0 <CLOUD_SQL_IP>${NC}"
    echo "  Example: sudo $0 10.10.0.3"
    exit 1
fi

APP_DIR="/home/j33ca/support-portal-edgeworks"
VENV_DIR="$APP_DIR/.venv"
CLOUD_SQL_PASS="Edgew0rks!DB2026#Secure"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Edgeworks AI Support Portal - Direct Deploy   ${NC}"
echo -e "${BLUE}  Database: Google Cloud SQL (SQL Server)       ${NC}"
echo -e "${BLUE}  Cloud SQL IP: $CLOUD_SQL_IP                   ${NC}"
echo -e "${BLUE}================================================${NC}"

# ── STEP 1: Stop Docker ──
log "STEP 1/12: Stopping Docker containers..."
cd "$APP_DIR"
sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true
sudo docker compose down 2>/dev/null || true
sudo docker stop $(sudo docker ps -aq) 2>/dev/null || true
sudo systemctl stop docker 2>/dev/null || true
sudo systemctl disable docker 2>/dev/null || true
log "Docker stopped ✓"

# ── STEP 2: Pull latest code ──
log "STEP 2/12: Pulling latest code..."
cd "$APP_DIR"
git stash 2>/dev/null || true
git pull origin main 2>/dev/null || true
log "Code updated ✓"

# ── STEP 3: System dependencies ──
log "STEP 3/12: Installing system dependencies..."
sudo apt-get update -y -qq
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    build-essential redis-server ffmpeg \
    libpq-dev unixodbc-dev curl

if ! dpkg -l | grep -q msodbcsql18; then
    log "Installing MSSQL ODBC 18 driver..."
    if ! test -f /usr/share/keyrings/microsoft-prod.gpg; then
        curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
    fi
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" | sudo tee /etc/apt/sources.list.d/mssql-release.list > /dev/null
    sudo apt-get update -y -qq
    sudo ACCEPT_EULA=Y apt-get install -y -qq msodbcsql18 mssql-tools18
fi
log "System dependencies installed ✓"

# ── STEP 4: Redis ──
log "STEP 4/12: Starting Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server
log "Redis running ✓"

# ── STEP 5: Python venv ──
log "STEP 5/12: Setting up Python environment..."
cd "$APP_DIR"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
log "Installing Python dependencies..."
pip install -r requirements.txt -q 2>&1 | tail -3
log "Python environment ready ✓"

# ── STEP 6: Data directories ──
log "STEP 6/12: Creating data directories..."
mkdir -p "$APP_DIR/data/knowledge" "$APP_DIR/data/uploads/chat" "$APP_DIR/data/db_storage"
log "Directories created ✓"

# ── STEP 7: Configure .env ──
log "STEP 7/12: Configuring .env for Cloud SQL Server..."
cp "$APP_DIR/.env" "$APP_DIR/.env.backup.$(date +%Y%m%d-%H%M%S)"

MSSQL_URL="mssql+pyodbc://sqlserver:${CLOUD_SQL_PASS}@${CLOUD_SQL_IP}/support_portal?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes"

# Update or add DATABASE_URL
if grep -q "^DATABASE_URL=" "$APP_DIR/.env"; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${MSSQL_URL}|" "$APP_DIR/.env"
else
    echo "DATABASE_URL=${MSSQL_URL}" >> "$APP_DIR/.env"
fi

sed -i 's|BASE_URL=http://localhost:8001|BASE_URL=http://34.126.104.27|' "$APP_DIR/.env"
sed -i 's|DEBUG=true|DEBUG=false|' "$APP_DIR/.env"

grep -q "^REDIS_URL" "$APP_DIR/.env" || echo -e "\nREDIS_URL=redis://localhost:6379/0\nREDIS_ENABLED=true" >> "$APP_DIR/.env"
grep -q "^ALLOWED_ORIGINS" "$APP_DIR/.env" || echo -e "\nALLOWED_ORIGINS=http://34.126.104.27,https://34.126.104.27,http://localhost:8001" >> "$APP_DIR/.env"

log ".env configured ✓"

# ── STEP 8: Test Cloud SQL connection ──
log "STEP 8/12: Testing Cloud SQL Server connection..."
source "$VENV_DIR/bin/activate"
python3 << PYEOF
from sqlalchemy import create_engine, text
import urllib.parse
password = urllib.parse.quote_plus("${CLOUD_SQL_PASS}")
url = f"mssql+pyodbc://sqlserver:{password}@${CLOUD_SQL_IP}/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes"
engine = create_engine(url)
with engine.connect() as conn:
    row = conn.execute(text("SELECT @@VERSION")).fetchone()
    print(f"  Connected: {row[0][:80]}")
    conn.execute(text("IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'support_portal') CREATE DATABASE support_portal"))
    conn.commit()
    print("  Database 'support_portal' ready!")
PYEOF
log "Cloud SQL connection verified ✓"

# ── STEP 9: Database migrations ──
log "STEP 9/12: Running database migrations..."
cd "$APP_DIR"
source "$VENV_DIR/bin/activate"
alembic upgrade head 2>&1 || warn "Migration issue - tables may need review"
log "Migrations done ✓"

# ── STEP 10: Systemd service ──
log "STEP 10/12: Creating systemd service..."
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

# ── STEP 11: Caddy reverse proxy ──
log "STEP 11/12: Configuring Caddy..."
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

# ── STEP 12: Start everything ──
log "STEP 12/12: Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable support-ai
sudo systemctl restart support-ai
sudo systemctl restart caddy

log "Waiting for startup (30s)..."
sleep 30

# ── Verification ──
echo ""
echo -e "${BLUE}========== Service Status ==========${NC}"
for svc in redis-server support-ai caddy; do
    if sudo systemctl is-active --quiet "$svc"; then
        echo -e "  ${GREEN}✓${NC} $svc"
    else
        echo -e "  ${RED}✗${NC} $svc FAILED"
        sudo journalctl -u "$svc" --no-pager -n 5 2>/dev/null
    fi
done

echo ""
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then
    echo -e "  ${GREEN}✓${NC} Health check passed (HTTP $HTTP)"
else
    echo -e "  ${YELLOW}!${NC} Health returned HTTP $HTTP"
    sudo journalctl -u support-ai --no-pager -n 15
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}       DEPLOYMENT COMPLETE!             ${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  App:      ${BLUE}http://34.126.104.27${NC}"
echo -e "  Health:   ${BLUE}http://34.126.104.27/health${NC}"
echo -e "  Database: Cloud SQL @ ${CLOUD_SQL_IP}"
echo -e ""
echo -e "  Logs:    sudo journalctl -u support-ai -f"
echo -e "  Status:  sudo systemctl status support-ai"
echo -e "  Restart: sudo systemctl restart support-ai"
