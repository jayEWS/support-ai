#!/bin/bash
# ============================================================
# DuckDNS + Nginx + SSL Setup for support-edgeworks.duckdns.org
# Run on VM: bash ~/support-portal/scripts/setup_domain.sh
# ============================================================

set -e

DOMAIN="support-edgeworks.duckdns.org"
DUCKDNS_TOKEN="50b347d4-2188-48a6-8205-85bc56acab69"
EMAIL="jay@edgeworks.com.sg"
APP_PORT=8000

echo "========================================="
echo "  Setting up: https://$DOMAIN"
echo "========================================="

# --- Step 1: DuckDNS auto-update cron ---
echo "[1/6] Setting up DuckDNS auto-update..."
mkdir -p ~/duckdns
cat > ~/duckdns/duck.sh <<DUCK
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=support-edgeworks&token=${DUCKDNS_TOKEN}&ip=" | curl -k -o ~/duckdns/duck.log -K -
DUCK
chmod 700 ~/duckdns/duck.sh
bash ~/duckdns/duck.sh
echo "  DuckDNS update result: $(cat ~/duckdns/duck.log)"

# Add cron job if not already present
if ! crontab -l 2>/dev/null | grep -q "duckdns"; then
    (crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
    echo "  Cron job added (every 5 min)"
else
    echo "  Cron job already exists"
fi

# --- Step 2: Install Nginx + Certbot ---
echo "[2/6] Installing Nginx + Certbot..."
sudo apt-get update -qq
sudo apt-get install -y -qq nginx certbot python3-certbot-nginx > /dev/null 2>&1
echo "  Nginx + Certbot installed"

# --- Step 3: Nginx config ---
echo "[3/6] Configuring Nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/support-ai > /dev/null <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    client_max_body_size 50M;
}
NGINX

sudo ln -sf /etc/nginx/sites-available/support-ai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
echo "  Nginx configured and running"

# --- Step 4: Firewall rules ---
echo "[4/6] Ensuring firewall allows HTTP/HTTPS..."
gcloud compute firewall-rules create allow-http-https \
    --allow tcp:80,tcp:443 \
    --target-tags=http-server,https-server \
    --project=agen-support 2>/dev/null && echo "  Firewall rule created" || echo "  Firewall rule already exists"

# Also tag this VM
INSTANCE_NAME=$(hostname)
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F'/' '{print $NF}')
gcloud compute instances add-tags "$INSTANCE_NAME" --tags=http-server,https-server --zone="$ZONE" --project=agen-support 2>/dev/null || true

# --- Step 5: SSL Certificate ---
echo "[5/6] Getting SSL certificate from Let's Encrypt..."
sudo certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m ${EMAIL}
echo "  SSL certificate installed!"

# --- Step 6: Update .env and restart container ---
echo "[6/6] Updating .env and restarting container..."
cd ~/support-portal

# Update BASE_URL
if grep -q "^BASE_URL=" .env; then
    sed -i "s|^BASE_URL=.*|BASE_URL=https://${DOMAIN}|" .env
else
    echo "BASE_URL=https://${DOMAIN}" >> .env
fi

# Update GOOGLE_REDIRECT_URI
if grep -q "^GOOGLE_REDIRECT_URI=" .env; then
    sed -i "s|^GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=https://${DOMAIN}/api/auth/google/callback|" .env
else
    echo "GOOGLE_REDIRECT_URI=https://${DOMAIN}/api/auth/google/callback" >> .env
fi

# Restart container
sudo docker rm -f support-ai 2>/dev/null || true
sudo docker run -d --name support-ai --restart always \
    -p ${APP_PORT}:${APP_PORT} \
    --env-file .env \
    support-ai:latest

echo ""
echo "========================================="
echo "  ✅ SETUP COMPLETE!"
echo "========================================="
echo ""
echo "  🔐 Admin:  https://${DOMAIN}/login"
echo "  💬 Chat:   https://${DOMAIN}/"
echo "  📊 Admin:  https://${DOMAIN}/admin"
echo ""
echo "  ⚠️  Don't forget to update Google OAuth Console:"
echo "     Redirect URI: https://${DOMAIN}/api/auth/google/callback"
echo "     JS Origins:   https://${DOMAIN}"
echo ""
