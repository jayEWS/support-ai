# =================================================================
# PowerShell Deployment Package Creator for GCP VM
# =================================================================

param(
    [string]$VMUser = "your-username",
    [string]$VMAddress = "34.126.104.27"
)

Write-Host "========================================" -ForegroundColor Blue
Write-Host "  Creating GCP VM Deployment Package   " -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue

# Create timestamp
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$packageName = "support-ai-$timestamp.tar.gz"
$tempDir = New-TemporaryFile | %{ Remove-Item $_; New-Item -ItemType Directory -Path $_ }

Write-Host "Creating deployment package..." -ForegroundColor Green

# Files to exclude from deployment
$excludePatterns = @(
    ".git",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".coverage", 
    ".env.local",
    ".env.development",
    "node_modules",
    ".docker",
    ".devcontainer", 
    ".vscode\settings.json",
    ".vscode\launch.json",
    "docker-compose*.yml",
    "Dockerfile*",
    "*.log",
    "data\db_storage",
    "data\uploads",
    ".DS_Store"
)

# Copy files excluding patterns
Get-ChildItem -Path . -Recurse | Where-Object {
    $file = $_
    $exclude = $false
    foreach ($pattern in $excludePatterns) {
        if ($file.FullName -like "*$pattern*") {
            $exclude = $true
            break
        }
    }
    !$exclude
} | Copy-Item -Destination {
    $relativePath = $_.FullName.Substring((Get-Location).Path.Length + 1)
    $destPath = Join-Path $tempDir.FullName $relativePath
    $destDir = Split-Path $destPath -Parent
    if (!(Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    $destPath
} -Force

Write-Host "Package created in: $($tempDir.FullName)" -ForegroundColor Green

# Create deployment instructions
$deploymentInstructions = @"

========================================
    DEPLOYMENT INSTRUCTIONS
========================================

1. Manual Upload Method:
   Upload files to your GCP VM using SCP:
   
   scp -r "$($tempDir.FullName)\*" ${VMUser}@${VMAddress}:/tmp/support-ai-code/
   scp deploy\gcp-vm-direct.sh ${VMUser}@${VMAddress}:/tmp/

2. Run deployment on GCP VM:
   ssh ${VMUser}@${VMAddress}
   sudo chmod +x /tmp/gcp-vm-direct.sh
   sudo /tmp/gcp-vm-direct.sh

3. Alternative - Use WSL with tar:
   wsl tar -czf /tmp/$packageName -C "$($tempDir.FullName)" .
   wsl scp /tmp/$packageName ${VMUser}@${VMAddress}:/tmp/support-ai-code.tar.gz

========================================
    QUICK DEPLOYMENT COMMANDS
========================================

# If you have WSL/Git Bash:
tar -czf /tmp/$packageName -C "$($tempDir.FullName)" .
scp /tmp/$packageName deploy/gcp-vm-direct.sh ${VMUser}@${VMAddress}:/tmp/
ssh ${VMUser}@${VMAddress} 'sudo /tmp/gcp-vm-direct.sh'

# Application will be available at:
http://${VMAddress}

========================================
    POST-DEPLOYMENT SETUP
========================================

1. SSH into your VM and update the .env file:
   sudo nano /opt/support-ai/.env
   
2. Add your API keys:
   GROQ_API_KEY=your-actual-groq-api-key
   OPENAI_API_KEY=your-openai-key (if using OpenAI)
   
3. Restart services:
   sudo systemctl restart support-ai-api
   sudo systemctl restart support-ai-worker

4. Check service status:
   sudo systemctl status support-ai-api
   sudo journalctl -u support-ai-api -f

"@

Write-Host $deploymentInstructions -ForegroundColor Yellow

# Create a simple deployment script for this session
$quickDeploy = @"
# Quick deployment commands (run in PowerShell/Terminal)

# 1. Create tar package (requires WSL or Git Bash)
wsl tar -czf /tmp/$packageName -C "$($tempDir.FullName)" .

# 2. Upload to GCP VM
scp /tmp/$packageName deploy/gcp-vm-direct.sh ${VMUser}@${VMAddress}:/tmp/

# 3. Run deployment
ssh ${VMUser}@${VMAddress} 'sudo chmod +x /tmp/gcp-vm-direct.sh && sudo /tmp/gcp-vm-direct.sh'

# 4. Check deployment
curl http://${VMAddress}/api/health
"@

$quickDeploy | Out-File -FilePath ".\quick-deploy-commands.txt" -Encoding UTF8

Write-Host "`nQuick deployment commands saved to: quick-deploy-commands.txt" -ForegroundColor Cyan
Write-Host "Temporary package directory: $($tempDir.FullName)" -ForegroundColor Cyan

# Ask if user wants to proceed with automatic deployment
$proceed = Read-Host "`nDo you want to proceed with automatic deployment? (y/N)"

if ($proceed -eq 'y' -or $proceed -eq 'Y') {
    if ($VMUser -eq "your-username") {
        $VMUser = Read-Host "Enter your GCP VM username"
    }
    
    Write-Host "`nAttempting automatic deployment..." -ForegroundColor Green
    
    try {
        # Check if we have WSL available for tar
        if (Get-Command wsl -ErrorAction SilentlyContinue) {
            Write-Host "Creating tar archive using WSL..." -ForegroundColor Green
            wsl tar -czf /tmp/$packageName -C "$($tempDir.FullName)" .
            
            Write-Host "Uploading files to GCP VM..." -ForegroundColor Green
            scp /tmp/$packageName deploy/gcp-vm-direct.sh "${VMUser}@${VMAddress}:/tmp/"
            
            Write-Host "Running deployment script on GCP VM..." -ForegroundColor Green
            ssh "${VMUser}@${VMAddress}" "sudo chmod +x /tmp/gcp-vm-direct.sh && sudo /tmp/gcp-vm-direct.sh"
            
            Write-Host "`nDeployment completed successfully!" -ForegroundColor Green
            Write-Host "Application should be available at: http://${VMAddress}" -ForegroundColor Blue
            
        } else {
            Write-Host "WSL not available. Please use manual deployment method." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Automatic deployment failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Please use the manual deployment method above." -ForegroundColor Yellow
    }
}

Write-Host "`nDeployment package preparation completed!" -ForegroundColor Green