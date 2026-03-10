#!/bin/bash
# =================================================================
# Deployment Package Creator for GCP VM
# =================================================================
# This script packages your application for deployment to GCP VM

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Creating deployment package...${NC}"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
PACKAGE_NAME="support-ai-$(date +%Y%m%d-%H%M%S).tar.gz"

# Copy application files (exclude unnecessary files)
echo -e "${GREEN}Copying application files...${NC}"
rsync -av --exclude-from=- . "$TEMP_DIR/" << 'EXCLUDE'
.git/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.coverage
.env.local
.env.development
node_modules/
.docker/
.devcontainer/
.vscode/settings.json
.vscode/launch.json
docker-compose*.yml
Dockerfile*
*.log
data/db_storage/
data/uploads/
.DS_Store
.gitignore
EXCLUDE

# Create the package
echo -e "${GREEN}Creating package: $PACKAGE_NAME${NC}"
cd "$TEMP_DIR"
tar -czf "/tmp/$PACKAGE_NAME" .

# Cleanup
rm -rf "$TEMP_DIR"

echo -e "${GREEN}Package created: /tmp/$PACKAGE_NAME${NC}"
echo -e "${BLUE}Package size: $(du -h /tmp/$PACKAGE_NAME | cut -f1)${NC}"

# Show deployment instructions
echo -e "\n${BLUE}=== DEPLOYMENT INSTRUCTIONS ===${NC}"
echo -e "1. Upload the package to your GCP VM:"
echo -e "   ${GREEN}scp /tmp/$PACKAGE_NAME user@34.126.104.27:/tmp/support-ai-code.tar.gz${NC}"
echo -e ""
echo -e "2. Upload and run the deployment script:"
echo -e "   ${GREEN}scp deploy/gcp-vm-direct.sh user@34.126.104.27:/tmp/${NC}"
echo -e "   ${GREEN}ssh user@34.126.104.27 'sudo chmod +x /tmp/gcp-vm-direct.sh && sudo /tmp/gcp-vm-direct.sh'${NC}"
echo -e ""
echo -e "3. Or combine both steps:"
echo -e "   ${GREEN}scp /tmp/$PACKAGE_NAME deploy/gcp-vm-direct.sh user@34.126.104.27:/tmp/ && \\${NC}"
echo -e "   ${GREEN}ssh user@34.126.104.27 'cd /tmp && sudo ./gcp-vm-direct.sh'${NC}"

# Create PowerShell version for Windows
cat > /tmp/deploy-to-gcp.ps1 << 'PSCRIPT'
# PowerShell deployment script for Windows users
param(
    [Parameter(Mandatory=$true)]
    [string]$VMUser = "your-username",
    
    [Parameter(Mandatory=$true)]
    [string]$VMAddress = "34.126.104.27"
)

$packagePath = "/tmp/support-ai-$(Get-Date -Format 'yyyyMMdd-HHmmss').tar.gz"
$deployScript = "deploy/gcp-vm-direct.sh"

Write-Host "Uploading deployment package..." -ForegroundColor Green
scp $packagePath "${VMUser}@${VMAddress}:/tmp/support-ai-code.tar.gz"

Write-Host "Uploading deployment script..." -ForegroundColor Green  
scp $deployScript "${VMUser}@${VMAddress}:/tmp/gcp-vm-direct.sh"

Write-Host "Running deployment on GCP VM..." -ForegroundColor Green
ssh "${VMUser}@${VMAddress}" "sudo chmod +x /tmp/gcp-vm-direct.sh && sudo /tmp/gcp-vm-direct.sh"

Write-Host "Deployment completed!" -ForegroundColor Green
Write-Host "Application should be available at: http://${VMAddress}" -ForegroundColor Blue
PSCRIPT

echo -e "\n${BLUE}PowerShell script created: /tmp/deploy-to-gcp.ps1${NC}"
echo -e "Usage: ${GREEN}pwsh /tmp/deploy-to-gcp.ps1 -VMUser your-username -VMAddress 34.126.104.27${NC}"