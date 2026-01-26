#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Clear all data from Silicon Trace database and restart fresh.

.DESCRIPTION
    This script will:
    1. Stop the Docker containers
    2. Remove the database volume (all data will be deleted)
    3. Restart the containers with a fresh database
#>

Write-Host "🗑️  Silicon Trace - Database Reset Utility" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Confirm with user
$confirmation = Read-Host "⚠️  This will DELETE ALL data in the database. Are you sure? (yes/no)"
if ($confirmation -ne "yes") {
    Write-Host "❌ Operation cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "🛑 Stopping containers..." -ForegroundColor Yellow
docker-compose down

Write-Host ""
Write-Host "🗑️  Removing database volume..." -ForegroundColor Yellow
docker volume rm silicon_trace_postgres_data -f

Write-Host ""
Write-Host "🚀 Starting containers with fresh database..." -ForegroundColor Green
docker-compose up -d

Write-Host ""
Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "✅ Database has been cleared and reset!" -ForegroundColor Green
Write-Host ""
Write-Host "Services running at:" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:8501" -ForegroundColor White
Write-Host ""
