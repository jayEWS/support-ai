#!/bin/bash
# Script to install Cloudflare and setup Quick Tunnel for public testing

echo "🌐 Installing Cloudflare (cloudflared)..."

# Download the latest deb package
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb

# Install it
sudo dpkg -i cloudflared-linux-amd64.deb

# Verify installation
if command -v cloudflared &> /dev/null; then
    echo "✅ Cloudflare installed successfully!"
else
    echo "❌ Installation failed. Please check the errors above."
    exit 1
fi

echo "🚀 Starting Public Tunnel in background..."
echo "Please wait a moment for the public URL to generate..."

# Start tunnel and save output to find the URL
nohup cloudflared tunnel --url http://localhost:8001 > tunnel.log 2>&1 &

# Wait for URL to appear in log
sleep 5
URL=$(grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare\.com' tunnel.log | tail -n 1)

if [ -z "$URL" ]; then
    echo "⏳ Still generating URL... try checking 'cat tunnel.log' in a few seconds."
else
    echo "========================================================="
    echo "🎉 YOUR PUBLIC LINK IS READY!"
    echo "LINK: $URL"
    echo "========================================================="
    echo "Share this link with the world! (Anyone can access /chat)"
fi
