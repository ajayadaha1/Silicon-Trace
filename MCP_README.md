# Silicon Trace MCP Server

The Silicon Trace MCP (Model Context Protocol) server exposes hardware failure data for AI tools and automation.

## Quick Start

### Start All Services (Including MCP)

```powershell
.\start.ps1
```

This starts:
- PostgreSQL database (port 5432)
- FastAPI backend (port 8000)
- Streamlit frontend (port 8501)
- **MCP server (port 8001)** ← NEW

### Access the MCP Server

**Local URL:** `http://localhost:8001/mcp/`

## Using with VS Code / Cursor

The MCP server is automatically configured in `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "silicon-trace": {
      "url": "http://localhost:8001/mcp/"
    }
  }
}
```

**To use:**
1. Open VS Code/Cursor in this workspace
2. Ask Copilot: "Query Silicon Trace for ALIBABA failures"
3. Copilot will use the MCP server to fetch data

## Using with Claude Desktop

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "silicon-trace": {
      "url": "http://localhost:8001/mcp/"
    }
  }
}
```

Then ask Claude: "Connect to Silicon Trace and show me customer statistics"

## Available Tools

### 1. `query_assets`
Query hardware failure assets with filters.

```python
# Examples:
query_assets(customer="ALIBABA", limit=50)
query_assets(status="failed", error_type="L1")
query_assets(date_from="2025-01-01", date_to="2025-12-31")
```

**Parameters:**
- `customer`: Filter by customer name
- `status`: Filter by status
- `error_type`: Filter by error type
- `location`: Filter by location
- `date_from`: Filter from date (YYYY-MM-DD)
- `date_to`: Filter to date (YYYY-MM-DD)
- `limit`: Max results (default 100, max 1000)

### 2. `get_asset_details`
Get complete details for a specific serial number.

```python
get_asset_details("9AMA377P50091_100-000001359")
```

### 3. `get_stats`
Get aggregated statistics.

```python
# Examples:
get_stats(grouping="customer")  # Group by customer
get_stats(grouping="tier")      # Group by test tier
get_stats(grouping="error")     # Group by error type
```

**Grouping options:** `customer`, `error`, `status`, `location`, `tier`, `timeline`

### 4. `search_failures`
Natural language search across all fields.

```python
search_failures("cache error L1", limit=50)
search_failures("ALIBABA")
```

### 5. `analyze_customer`
Get comprehensive insights for a specific customer.

```python
analyze_customer("ALIBABA")
```

Returns:
- Total assets
- Serial numbers
- Error type breakdown
- Status breakdown
- Tier failure analysis

### 6. `count_assets`
Quick count without returning full data.

```python
count_assets(customer="ALIBABA")
count_assets(error_type="L1")
```

## Available Resources

Resources are read-only data sources that AI tools can access:

### 1. `silicon-trace://database/summary`
Overview of database state (total assets, customers, date ranges)

### 2. `silicon-trace://database/customers`
List of all customers with failure counts

### 3. `silicon-trace://database/error-types`
All unique error types with frequency counts

### 4. `silicon-trace://database/tiers`
Tier failure analysis (L1, L2, ATE, SLT, etc.)

## Example Workflows

### Workflow 1: AI Analysis with VS Code

```
You: "How many ALIBABA failures are at L1?"

Copilot:
1. Calls: count_assets(customer="ALIBABA", error_type="L1")
2. Returns: {"count": 15}
3. Responds: "There are 15 ALIBABA failures at L1"
```

### Workflow 2: Customer Analysis with Claude

```
You: "Analyze ALIBABA failures"

Claude:
1. Calls: analyze_customer("ALIBABA")
2. Gets comprehensive breakdown
3. Provides insights and recommendations
```

### Workflow 3: Automation Script

```python
from mcp import ClientSession

async def daily_report():
    session = ClientSession("http://localhost:8001/mcp/")
    
    # Get today's failures
    result = await session.call_tool("query_assets", {
        "date_from": "2026-01-29",
        "limit": 100
    })
    
    # Generate report
    failures = json.loads(result)
    send_email(format_report(failures))
```

## Architecture

```
┌────────────────────────────────────┐
│   Silicon Trace Webapp             │
│   (Unchanged - Still Works)        │
│   ├─ Frontend: localhost:8501      │
│   ├─ Backend: localhost:8000       │
│   └─ Database: PostgreSQL          │
└────────────────────────────────────┘
              ↓ shares database
┌────────────────────────────────────┐
│   MCP Server (NEW)                 │
│   localhost:8001                   │
│   ├─ FastMCP Framework             │
│   ├─ 6 Tools (query, search, etc) │
│   ├─ 4 Resources (summaries)       │
│   └─ Same PostgreSQL Database      │
└────────────────────────────────────┘
              ↑ MCP Protocol
    ┌─────────────────────┐
    │  AI Tools           │
    │  ├─ VS Code Copilot │
    │  ├─ Claude Desktop  │
    │  └─ Custom Scripts  │
    └─────────────────────┘
```

## Troubleshooting

### MCP Server Not Starting

```powershell
# Check logs
docker logs silicon_trace_mcp

# Restart MCP server only
docker-compose restart mcp-server

# Rebuild if needed
docker-compose up -d --build mcp-server
```

### VS Code Can't Connect

1. Verify MCP server is running: `docker ps | findstr mcp`
2. Check `.vscode/mcp.json` exists
3. Restart VS Code
4. Check: `http://localhost:8001/mcp/` in browser

### Test MCP Server

```powershell
# Simple health check
curl http://localhost:8001/mcp/

# Test with MCP client
python -c "
import asyncio
from mcp import ClientSession

async def test():
    session = ClientSession('http://localhost:8001/mcp/')
    result = await session.call_tool('count_assets', {})
    print(result)

asyncio.run(test())
"
```

## Development

### Adding New Tools

Edit `backend/silicon_trace_mcp.py`:

```python
@mcp.tool()
async def your_new_tool(param: str) -> str:
    """Tool description"""
    async with get_session() as session:
        # Your logic here
        return json.dumps(result)
```

Restart MCP server:
```powershell
docker-compose restart mcp-server
```

### Shared Query Logic

Common database queries are in `backend/queries.py` and used by both:
- FastAPI backend (webapp)
- MCP server

This ensures consistency between both access methods.

## Security Notes

**Current Setup (Local Only):**
- MCP server accessible only on localhost
- No external access
- No authentication (trusted local environment)

**For Production/Remote Access:**
- Add API key authentication
- Use HTTPS
- Register with AMD MCP Platform
- Implement user-level access control

## Performance

- Database connection pooling shared between webapp and MCP
- Query limits prevent excessive data transfer (max 1000 results)
- Resources cached where appropriate
- Async operations throughout

## Next Steps

1. **Test the MCP server** with VS Code or Claude Desktop
2. **Build automation** using the MCP tools
3. **Monitor usage** to see which tools are most valuable
4. **Consider AMD platform registration** if others need access

## Support

For issues or questions:
- Check Docker logs: `docker logs silicon_trace_mcp`
- Review MCP server code: `backend/silicon_trace_mcp.py`
- Test queries directly: `backend/queries.py`
