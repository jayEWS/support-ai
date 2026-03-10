# GCP VM Direct Deployment Guide

## Quick Setup (No Docker)

You've successfully stopped Docker containers and are ready for direct VM deployment. Here's your step-by-step guide:

### Option 1: Manual File Upload (Recommended)

1. **Prepare your GCP VM connection:**
   ```bash
   # Test SSH connection first
   ssh bang-jay@34.126.104.27
   ```

2. **Upload application files to GCP VM:**
   ```bash
   # Upload the deployment script
   scp deploy/gcp-vm-direct.sh bang-jay@34.126.104.27:/tmp/
   
   # Upload your application code (zip method)
   # First create a zip file
   powershell Compress-Archive -Path . -DestinationPath support-ai.zip -Exclude @('.git','__pycache__','*.pyc','docker-compose*.yml','Dockerfile*')
   
   # Upload the zip
   scp support-ai.zip bang-jay@34.126.104.27:/tmp/
   ```

3. **Run deployment on GCP VM:**
   ```bash
   # SSH into your VM
   ssh bang-jay@34.126.104.27
   
   # Extract code
   cd /tmp
   sudo unzip support-ai.zip -d /opt/support-ai/
   
   # Run deployment script
   sudo chmod +x gcp-vm-direct.sh
   sudo ./gcp-vm-direct.sh
   ```

### Option 2: Git Clone Method (If you have a Git repository)

```bash
# SSH into VM
ssh bang-jay@34.126.104.27

# Clone your repository
sudo git clone https://github.com/your-username/support-ai.git /opt/support-ai

# Upload and run deployment script
# (From your local machine)
scp deploy/gcp-vm-direct.sh bang-jay@34.126.104.27:/tmp/
ssh bang-jay@34.126.104.27 'sudo chmod +x /tmp/gcp-vm-direct.sh && sudo /tmp/gcp-vm-direct.sh'
```

### Option 3: PowerShell with Proper Paths

```powershell
# Create deployment package (Windows/PowerShell)
$excludeList = @('.git','__pycache__','*.pyc','docker-compose*.yml','Dockerfile*','data/db_storage','data/uploads')
Compress-Archive -Path . -DestinationPath "support-ai-deployment.zip" -Force

# Upload to VM
scp support-ai-deployment.zip deploy/gcp-vm-direct.sh bang-jay@34.126.104.27:/tmp/

# Deploy via SSH
ssh bang-jay@34.126.104.27 "cd /tmp && sudo unzip -o support-ai-deployment.zip -d /opt/support-ai/ && sudo chmod +x gcp-vm-direct.sh && sudo ./gcp-vm-direct.sh"
```

## What the Deployment Script Does

The `gcp-vm-direct.sh` script will:

1. **Install System Dependencies:**
   - Python 3.11, PostgreSQL, Redis, Nginx
   - Microsoft SQL Server ODBC drivers
   - Qdrant vector database

2. **Setup Application:**
   - Create `/opt/support-ai/` directory
   - Install Python dependencies from requirements.txt
   - Configure systemd services for API and worker

3. **Configure Services:**
   - PostgreSQL database with `support_portal` database
   - Redis with authentication
   - Qdrant vector database on port 6333
   - Nginx reverse proxy

4. **Security Setup:**
   - Firewall configuration (UFW)
   - SSL-ready Nginx configuration
   - Service user permissions

## After Deployment

1. **Update API Keys:**
   ```bash
   sudo nano /opt/support-ai/.env
   # Add your actual API keys:
   # GROQ_API_KEY=your-groq-api-key
   # OPENAI_API_KEY=your-openai-key
   ```

2. **Restart Services:**
   ```bash
   sudo systemctl restart support-ai-api
   sudo systemctl restart support-ai-worker
   ```

3. **Check Status:**
   ```bash
   # Check if services are running
   sudo systemctl status support-ai-api
   sudo systemctl status support-ai-worker
   
   # View logs
   sudo journalctl -u support-ai-api -f
   ```

4. **Test Application:**
   ```bash
   # Test API endpoint
   curl http://34.126.104.27/api/health
   
   # Access web interface
   # Open browser: http://34.126.104.27
   ```

## Useful Commands

```bash
# View all logs
sudo journalctl -u support-ai-api -u support-ai-worker -f

# Restart all services
sudo systemctl restart support-ai-api support-ai-worker nginx

# Check service status
sudo systemctl status support-ai-api support-ai-worker nginx redis-server postgresql qdrant

# Update application code
cd /opt/support-ai
sudo git pull  # if using git
sudo systemctl restart support-ai-api support-ai-worker
```

## Troubleshooting

1. **Service won't start:**
   ```bash
   sudo journalctl -u support-ai-api --no-pager
   ```

2. **Database connection issues:**
   ```bash
   sudo -u postgres psql -c "\l"  # List databases
   sudo systemctl status postgresql
   ```

3. **Redis connection issues:**
   ```bash
   redis-cli ping
   sudo systemctl status redis-server
   ```

4. **Port issues:**
   ```bash
   sudo netstat -tlnp | grep :8001  # Check if API port is open
   sudo ufw status  # Check firewall
   ```

Your application will be available at: **http://34.126.104.27**