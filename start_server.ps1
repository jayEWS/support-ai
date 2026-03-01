#!/usr/bin/env powershell
<#
.SYNOPSIS
    Start the Support Portal server with automatic restart on crash
.DESCRIPTION
    Starts the FastAPI server and automatically restarts it if it stops
#>

param(
    [int]$Port = 8001,
    [string]$Host = "127.0.0.1",
    [switch]$NoRestart
)

$ErrorActionPreference = "SilentlyContinue"

function Start-Server {
    Write-Host "`n╔════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  🚀 Support Portal Server Starting    ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════╝`n" -ForegroundColor Cyan
    
    Write-Host "📍 URL: http://$Host`:$Port" -ForegroundColor Green
    Write-Host "🌐 Dashboard: http://$Host`:$Port/login" -ForegroundColor Green
    # show database configuration for clarity
    if ($env:DATABASE_URL) {
        Write-Host "🗄️  Database URL: $env:DATABASE_URL" -ForegroundColor Green
    }
    Write-Host "`n⏳ Starting server..." -ForegroundColor Yellow
    
    cd d:\Project\support-portal-edgeworks
    & ".\.venv\Scripts\python.exe" -m uvicorn main:app --host $Host --port $Port
    
    Write-Host "`n⚠️  Server stopped" -ForegroundColor Yellow
}

# Kill existing processes
Write-Host "🛑 Stopping any existing Python processes..." -ForegroundColor Yellow
Get-Process -Name "python" 2>$null | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

if ($NoRestart) {
    Start-Server
} else {
    $attempt = 0
    while ($true) {
        $attempt++
        Write-Host "`n[Attempt $attempt] Starting server..." -ForegroundColor Cyan
        Start-Server
        Write-Host "Restarting in 3 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
    }
}

Write-Host "`n✅ Server stopped" -ForegroundColor Green
