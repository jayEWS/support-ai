#!/bin/bash
# =================================================================
# GCP VM Direct Deployment Script for Enterprise AI Support Portal
# =================================================================
# This script deploys the application directly to a GCP VM without Docker
# Run this on your GCP VM: 34.126.104.27

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Enterprise AI Support Portal Setup   ${NC}"
echo -e "${BLUE}     Direct GCP VM Deployment          ${NC}"
echo -e "${BLUE}========================================${NC}"

# Configuration
APP_USER="supportai"
APP_DIR="/opt/support-ai"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="support-ai"
NGINX_CONFIG="/etc/nginx/sites-available/support-ai"

# Function to print status
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root (use sudo)"
   exit 1
fi

print_status "Starting Enterprise AI Support Portal deployment..."

# =================================================================
# STEP 1: System Update and Dependencies
# =================================================================
print_status "Updating system packages..."
apt-get update -y
apt-get upgrade -y

print_status "Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    nginx \
    redis-server \
    postgresql \
    postgresql-contrib \
    supervisor \
    ufw \
    htop \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    ffmpeg \
    libpq-dev \
    unixodbc-dev

# =================================================================
# STEP 2: Install Microsoft SQL Server ODBC Driver
# =================================================================
print_status "Installing Microsoft SQL Server ODBC driver..."
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/ubuntu/$(lsb_release -rs)/prod $(lsb_release -cs) main" > /etc/apt/sources.list.d/mssql-release.list
apt-get update -y
ACCEPT_EULA=Y apt-get install -y msodbcsql18

# =================================================================
# STEP 3: Create Application User and Directory
# =================================================================
print_status "Creating application user and directories..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$APP_DIR" "$APP_USER"
fi

mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/data/knowledge"
mkdir -p "$APP_DIR/data/uploads"
mkdir -p "$APP_DIR/data/db_storage"

# =================================================================
# STEP 4: Setup PostgreSQL Database
# =================================================================
print_status "Setting up PostgreSQL database..."
sudo -u postgres psql -c "CREATE USER support_portal WITH PASSWORD 'secure_db_password_change_in_production';" || true
sudo -u postgres psql -c "CREATE DATABASE support_portal OWNER support_portal;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE support_portal TO support_portal;" || true

# Configure PostgreSQL
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/*/main/postgresql.conf
echo "host support_portal support_portal 127.0.0.1/32 md5" >> /etc/postgresql/*/main/pg_hba.conf
systemctl restart postgresql
systemctl enable postgresql

# =================================================================
# STEP 5: Setup Redis
# =================================================================
print_status "Configuring Redis..."
sed -i 's/^# requirepass foobared/requirepass redis_secure_password_change_me/' /etc/redis/redis.conf
sed -i 's/^bind 127.0.0.1 ::1/bind 127.0.0.1/' /etc/redis/redis.conf
systemctl restart redis-server
systemctl enable redis-server

# =================================================================
# STEP 6: Install Qdrant Vector Database
# =================================================================
print_status "Installing Qdrant vector database..."
curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz -o qdrant.tar.gz
tar -xzf qdrant.tar.gz
mv qdrant /usr/local/bin/
rm qdrant.tar.gz

# Create Qdrant service
cat > /etc/systemd/system/qdrant.service << EOF
[Unit]
Description=Qdrant Vector Database
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/qdrant --config-path /etc/qdrant/config.yaml
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /etc/qdrant
cat > /etc/qdrant/config.yaml << EOF
log_level: INFO
storage:
  storage_path: /var/lib/qdrant
service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334
EOF

mkdir -p /var/lib/qdrant
systemctl daemon-reload
systemctl enable qdrant
systemctl start qdrant

# =================================================================
# STEP 7: Clone Application Code
# =================================================================
print_status "Deploying application code..."
cd "$APP_DIR"

# If this script is being run from the project directory, copy files
if [ -f "/tmp/support-ai-code.tar.gz" ]; then
    print_status "Extracting application code from archive..."
    tar -xzf /tmp/support-ai-code.tar.gz -C "$APP_DIR" --strip-components=1
else
    print_status "Application code should be uploaded to $APP_DIR"
    print_warning "Please upload your application code to $APP_DIR before continuing"
fi

# =================================================================
# STEP 8: Setup Python Virtual Environment
# =================================================================
print_status "Setting up Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies (if requirements.txt exists)
if [ -f "$APP_DIR/requirements.txt" ]; then
    print_status "Installing Python dependencies..."
    pip install -r "$APP_DIR/requirements.txt"
else
    print_warning "requirements.txt not found. Please install dependencies manually."
fi

# =================================================================
# STEP 9: Create Environment Configuration
# =================================================================
print_status "Creating environment configuration..."
cat > "$APP_DIR/.env" << EOF
# ============ DATABASE ============
DATABASE_URL=postgresql://support_portal:secure_db_password_change_in_production@localhost:5432/support_portal

# ============ REDIS ============
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
REDIS_PASSWORD=redis_secure_password_change_me

# ============ QDRANT ============
QDRANT_HOST=localhost
QDRANT_PORT=6333

# ============ SECURITY ============
SECRET_KEY=your-super-secret-jwt-signing-key-change-this-in-production
JWT_SECRET_KEY=your-jwt-secret-key-change-this-in-production
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,https://34.126.104.27

# ============ AI CONFIGURATION ============
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key-here
MODEL_NAME=llama-3.3-70b-versatile
TEMPERATURE=0.1

# ============ APPLICATION SETTINGS ============
DEBUG=false
BASE_URL=https://34.126.104.27
ENVIRONMENT=production
EOF

# =================================================================
# STEP 10: Set Permissions
# =================================================================
print_status "Setting file permissions..."
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod 600 "$APP_DIR/.env"

# =================================================================
# STEP 11: Database Migration
# =================================================================
print_status "Running database migrations..."
cd "$APP_DIR"
sudo -u "$APP_USER" bash -c "source $VENV_DIR/bin/activate && alembic upgrade head" || print_warning "Migration failed - run manually"

# =================================================================
# STEP 12: Create Systemd Services
# =================================================================
print_status "Creating systemd service files..."

# Main API service
cat > /etc/systemd/system/support-ai-api.service << EOF
[Unit]
Description=Support AI API Server
After=network.target postgresql.service redis-server.service qdrant.service
Requires=postgresql.service redis-server.service qdrant.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
ExecStart=$VENV_DIR/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 127.0.0.1:8001 --timeout 120 --graceful-timeout 30
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Background Worker service
cat > /etc/systemd/system/support-ai-worker.service << EOF
[Unit]
Description=Support AI Background Worker
After=network.target postgresql.service redis-server.service qdrant.service
Requires=postgresql.service redis-server.service qdrant.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
ExecStart=$VENV_DIR/bin/python scripts/start_worker.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# =================================================================
# STEP 13: Configure Nginx
# =================================================================
print_status "Configuring Nginx..."
cat > "$NGINX_CONFIG" << EOF
server {
    listen 80;
    server_name 34.126.104.27 localhost;
    
    client_max_body_size 100M;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Static files
    location /static/ {
        alias $APP_DIR/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
    
    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Default location (serve main app)
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable the site
ln -sf "$NGINX_CONFIG" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
nginx -t

# =================================================================
# STEP 14: Configure Firewall
# =================================================================
print_status "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# =================================================================
# STEP 15: Start Services
# =================================================================
print_status "Starting all services..."
systemctl daemon-reload

# Enable services
systemctl enable support-ai-api
systemctl enable support-ai-worker
systemctl enable nginx

# Start services
systemctl start support-ai-api
systemctl start support-ai-worker
systemctl restart nginx

# =================================================================
# STEP 16: Verification
# =================================================================
print_status "Verifying deployment..."

# Check service status
services=("postgresql" "redis-server" "qdrant" "support-ai-api" "support-ai-worker" "nginx")
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        print_status "$service is running ✓"
    else
        print_error "$service is not running ✗"
    fi
done

# Check API endpoint
sleep 5
if curl -f http://localhost/api/health &>/dev/null; then
    print_status "API health check passed ✓"
else
    print_warning "API health check failed - check logs with: journalctl -u support-ai-api -f"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}   Deployment Complete!                 ${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${BLUE}Application URL:${NC} http://34.126.104.27"
echo -e "${BLUE}API Health:${NC} http://34.126.104.27/api/health"
echo -e "${BLUE}Logs:${NC} journalctl -u support-ai-api -f"
echo -e "${BLUE}Status:${NC} systemctl status support-ai-api"
echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "1. Update .env file with your API keys"
echo -e "2. Restart services: sudo systemctl restart support-ai-api"
echo -e "3. Monitor logs for any issues"
echo -e "4. Set up SSL certificate for production use"

# =================================================================
# STEP 17: Create Management Scripts
# =================================================================
print_status "Creating management scripts..."

cat > "$APP_DIR/scripts/restart-services.sh" << 'EOF'
#!/bin/bash
echo "Restarting Support AI services..."
sudo systemctl restart support-ai-api
sudo systemctl restart support-ai-worker
sudo systemctl restart nginx
echo "Services restarted!"
EOF

cat > "$APP_DIR/scripts/view-logs.sh" << 'EOF'
#!/bin/bash
echo "Select which logs to view:"
echo "1. API logs"
echo "2. Worker logs"
echo "3. Nginx logs"
echo "4. All logs"
read -p "Enter choice (1-4): " choice

case $choice in
    1) sudo journalctl -u support-ai-api -f ;;
    2) sudo journalctl -u support-ai-worker -f ;;
    3) sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log ;;
    4) sudo journalctl -u support-ai-api -u support-ai-worker -f ;;
    *) echo "Invalid choice" ;;
esac
EOF

chmod +x "$APP_DIR/scripts/"*.sh
chown "$APP_USER:$APP_USER" "$APP_DIR/scripts/"*.sh

print_status "Management scripts created in $APP_DIR/scripts/"
print_status "Deployment script completed successfully!"