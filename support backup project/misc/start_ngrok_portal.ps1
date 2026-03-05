#!/usr/bin/env powershell
<#
.SYNOPSIS
    Otomatisasi Start Ngrok + Update .env + Start FastAPI
#>

$ErrorActionPreference = "SilentlyContinue"

# 1. Stop existing processes
Write-Host "🛑 Menghentikan proses lama (python & ngrok)..." -ForegroundColor Yellow
Get-Process -Name "python" 2>$null | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "ngrok" 2>$null | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 2. Start Ngrok in the background (pointing to port 8001)
Write-Host "🚀 Menjalankan Ngrok (tunnel ke port 8001)..." -ForegroundColor Cyan
Start-Process -FilePath "ngrok" -ArgumentList "http", "8001" -WindowStyle Minimized
Start-Sleep -Seconds 5

# 3. Use the Python script to fetch the URL and update .env
Write-Host "🔄 Menyinkronkan .env dengan URL Ngrok terbaru..." -ForegroundColor Yellow
# Using absolute path to ensure correct venv execution
& "d:\Project\support-portal-edgeworks\.venv\Scripts\python.exe" "d:\Project\support-portal-edgeworks\scripts\sync_ngrok_env.py"

# 4. Start the FastAPI server using the existing start_server.ps1 script
Write-Host "🎉 Menjalankan Server Utama..." -ForegroundColor Green
# We pass -NoRestart to the original script because this script handles orchestration
# Or just call uvicorn directly for stability
& "d:\Project\support-portal-edgeworks\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8001
