#!/bin/bash
# Patch production .env values on the VM
# Run as: bash deploy/patch-env.sh
# Must be run ON the VM (or piped via SSH)

ENV_FILE="/home/j33ca/support-portal-edgeworks/.env"
DOMAIN="https://support-edgeworks.duckdns.org"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found"
    exit 1
fi

echo "=== Patching production .env ==="
cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
echo "  Backup created"

patch_env() {
    local key="$1"
    local value="$2"
    # Replace existing key=anything with key=value
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        echo "  ✓ ${key} updated"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
        echo "  ✓ ${key} added"
    fi
}

# --- Core ---
patch_env "ENVIRONMENT"           "production"
patch_env "DEBUG"                 "False"
patch_env "BASE_URL"              "$DOMAIN"

# --- Security ---
patch_env "COOKIE_SECURE"        "True"
patch_env "COOKIE_SAMESITE"      "Lax"

# --- CORS ---
patch_env "ALLOWED_ORIGINS"      "${DOMAIN},https://www.support-edgeworks.duckdns.org"

# --- Google OAuth ---
patch_env "GOOGLE_REDIRECT_URI"  "${DOMAIN}/api/auth/google/callback"

# --- Redis (required for multi-worker session sharing) ---
patch_env "REDIS_ENABLED"        "true"
patch_env "REDIS_URL"            "redis://localhost:6379/0"

echo ""
echo "=== Updated values ==="
grep -E "^(ENVIRONMENT|DEBUG|BASE_URL|COOKIE_SECURE|ALLOWED_ORIGINS|GOOGLE_REDIRECT_URI|REDIS_ENABLED|REDIS_URL)=" "$ENV_FILE"

echo ""
echo "=== Restarting support-ai ==="
systemctl restart support-ai
sleep 10

HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then
    echo "  ✓ Health check passed (HTTP $HTTP)"
    echo ""
    echo "  DONE. Google OAuth redirect URI is now:"
    echo "  ${DOMAIN}/api/auth/google/callback"
    echo ""
    echo "  ⚠  Make sure this URI is listed in Google Cloud Console:"
    echo "  https://console.cloud.google.com/apis/credentials"
else
    echo "  ✗ Health check failed (HTTP $HTTP)"
    echo "  Check logs: journalctl -u support-ai -n 30"
fi
