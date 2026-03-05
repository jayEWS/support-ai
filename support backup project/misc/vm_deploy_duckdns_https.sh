#!/bin/bash
# ============================================================
# vm_deploy_duckdns_https.sh - GCP Deploy with DuckDNS & SSL
# Run this on the VM: bash ~/support-portal/vm_deploy_duckdns_https.sh
# ============================================================
set -e

DOMAIN="support-edgeworks.duckdns.org"
EMAIL="jay@edgeworks.com.sg"

echo "=== [1/7] Pull latest code ==="
cd ~/support-portal
git fetch origin main
git reset --hard origin/main

echo "=== [2/7] Install Nginx & Certbot (SSL) ==="
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Create Nginx config for subdomain
echo "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/support-ai > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/support-ai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "=== [3/7] Generate SSL Certificate (Let's Encrypt) ==="
# Port 80 must be open for this to work
sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL --redirect

echo "=== [4/7] Update .env for Production Domain ==="
sed -i "s|^BASE_URL=.*|BASE_URL=https://$DOMAIN|" .env
sed -i "s|^GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=https://$DOMAIN/api/auth/google/callback|" .env
sed -i "s|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=[\"https://$DOMAIN\", \"http://localhost:8000\"]|" .env
sed -i "s|^COOKIE_SECURE=.*|COOKIE_SECURE=true|" .env
sed -i "s|^COOKIE_SAMESITE=.*|COOKIE_SAMESITE=lax|" .env

# Database connection (Ensure direct connection is used)
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg2://postgres:Tekansaja123@db.wjsaltebtbmnysgcdsoh.supabase.co:5432/postgres|' .env

echo "=== [5/7] Stop & remove old container ==="
sudo docker stop support-ai 2>/dev/null || true
sudo docker rm support-ai 2>/dev/null || true

echo "=== [6/7] Build new Docker image ==="
sudo docker build --no-cache -t support-ai .

echo "=== [7/7] Start container ==="
# Map container to port 8000 (Nginx will proxy to this)
sudo docker run -d \
    --name support-ai \
    --restart always \
    -p 8000:8000 \
    -v ~/support-portal/data:/app/data \
    --env-file ~/support-portal/.env \
    support-ai

echo ""
echo "============================================"
echo "✅ DEPLOY SUCCESSFUL (PERMANENT HTTPS)"
echo "PORTAL URL: https://$DOMAIN"
echo "============================================"
echo "⚠️ REMINDER: Update Redirect URI in Google Console to:"
echo "https://$DOMAIN/api/auth/google/callback"
