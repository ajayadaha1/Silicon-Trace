# Silicon Trace MCP Server Startup Script
Write-Host "🚀 Starting Silicon Trace with MCP Server..." -ForegroundColor Cyan

# Check if Docker is running
Write-Host "`n📦 Checking Docker..." -ForegroundColor Yellow
$dockerRunning = $false
try {
    docker ps > $null 2>&1
    $dockerRunning = $true
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not running" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

# Stop any existing containers
Write-Host "`n🛑 Stopping existing containers..." -ForegroundColor Yellow
docker-compose down 2>&1 | Out-Null

# Start all services (including MCP server)
Write-Host "`n🏗️  Building and starting services..." -ForegroundColor Yellow
Write-Host "   - PostgreSQL Database (port 5432)" -ForegroundColor White
Write-Host "   - FastAPI Backend (port 8000)" -ForegroundColor White
Write-Host "   - Streamlit Frontend (port 8501)" -ForegroundColor White
Write-Host "   - MCP Server (port 8001) ⭐ NEW" -ForegroundColor Cyan

docker-compose up -d --build

# Wait for services to be ready
Write-Host "`n⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check service health
Write-Host "`n🏥 Checking service health..." -ForegroundColor Yellow

$services = @(
    @{Name="Database"; Container="silicon_trace_db"; Port=5432},
    @{Name="Backend"; Container="silicon_trace_backend"; Port=8000},
    @{Name="Frontend"; Container="silicon_trace_frontend"; Port=8501},
    @{Name="MCP Server"; Container="silicon_trace_mcp"; Port=8001}
)

foreach ($service in $services) {
    $running = docker ps --filter "name=$($service.Container)" --format "{{.Names}}" 2>$null
    if ($running) {
        Write-Host "  ✓ $($service.Name) - Running on port $($service.Port)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $($service.Name) - Not running" -ForegroundColor Red
    }
}

Write-Host "`n" -NoNewline
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✨ Silicon Trace is ready!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

Write-Host "`n📍 Access Points:" -ForegroundColor Yellow
Write-Host "   🌐 Web App:    " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8501" -ForegroundColor Cyan
Write-Host "   🔧 API Docs:   " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "   🤖 MCP Server: " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8001/mcp/" -ForegroundColor Magenta

Write-Host "`n🔌 MCP Integration:" -ForegroundColor Yellow
Write-Host "   ✓ VS Code: Configured in .vscode/mcp.json" -ForegroundColor Green
Write-Host "   ✓ Tools: 6 tools available (query_assets, search_failures, etc.)" -ForegroundColor Green
Write-Host "   ✓ Resources: 4 resources (database summary, customers, etc.)" -ForegroundColor Green

Write-Host "`n📚 Documentation:" -ForegroundColor Yellow
Write-Host "   - MCP Guide: MCP_README.md" -ForegroundColor White
Write-Host "   - Main Docs: README.md" -ForegroundColor White

Write-Host "`n💡 Quick Test MCP:" -ForegroundColor Yellow
Write-Host '   Ask VS Code Copilot: "Query Silicon Trace for all customers"' -ForegroundColor White
Write-Host '   Or in Claude Desktop: "Connect to Silicon Trace and show statistics"' -ForegroundColor White

Write-Host "`n🛠️  Useful Commands:" -ForegroundColor Yellow
Write-Host "   View logs:    docker-compose logs -f mcp-server" -ForegroundColor White
Write-Host "   Restart MCP:  docker-compose restart mcp-server" -ForegroundColor White
Write-Host "   Stop all:     docker-compose down" -ForegroundColor White

Write-Host "`n"
