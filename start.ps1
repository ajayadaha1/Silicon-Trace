#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Silicon Trace - All-in-one startup script

.DESCRIPTION
    Stops any running services, starts Docker containers, and launches the Streamlit frontend.
#>

Write-Host "🔍 Silicon Trace - Starting All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop any existing services
Write-Host "🛑 Stopping existing services..." -ForegroundColor Yellow
docker-compose down 2>$null
Get-Process | Where-Object {$_.ProcessName -like "*streamlit*"} | Stop-Process -Force 2>$null

Write-Host ""
Write-Host "🚀 Starting Docker containers..." -ForegroundColor Green
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start Docker containers" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "⏳ Waiting for backend to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check backend health
$maxRetries = 10
$retries = 0
$backendReady = $false

while ($retries -lt $maxRetries -and -not $backendReady) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
        }
    } catch {
        $retries++
        Start-Sleep -Seconds 2
    }
}

if ($backendReady) {
    Write-Host "✓ Backend is ready" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Backend may not be ready yet" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎨 Starting Streamlit frontend..." -ForegroundColor Green
Write-Host ""
Write-Host "Services running at:" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:8501" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the frontend (backend will continue running)" -ForegroundColor Yellow
Write-Host ""

# Start Streamlit from frontend directory
Set-Location frontend
python -m streamlit run app.py
