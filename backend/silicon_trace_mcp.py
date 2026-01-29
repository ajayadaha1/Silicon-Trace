"""
Silicon Trace MCP Server
Exposes hardware failure data via Model Context Protocol.
"""

from fastmcp import FastMCP
from database import get_session
from queries import (
    query_assets_from_db,
    get_asset_by_serial,
    get_database_summary,
    get_statistics,
    search_assets,
    get_customer_insights
)
import json
import os
from typing import Optional

# Initialize MCP server
mcp = FastMCP("Silicon Trace")


@mcp.tool()
async def query_assets(
    customer: Optional[str] = None,
    status: Optional[str] = None,
    error_type: Optional[str] = None,
    location: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Query hardware failure assets with multiple filter options.
    
    Args:
        customer: Filter by customer name (e.g., 'ALIBABA', 'TENCENT')
        status: Filter by status (e.g., 'failed', 'closed')
        error_type: Filter by error type (e.g., 'L1', 'L2', 'Cache')
        location: Filter by location (e.g., 'ATE', 'SLT')
        date_from: Filter from date (ISO format: YYYY-MM-DD)
        date_to: Filter to date (ISO format: YYYY-MM-DD)
        limit: Maximum number of results (default 100, max 1000)
    
    Returns:
        JSON string with array of matching assets
    
    Examples:
        query_assets(customer="ALIBABA", limit=50)
        query_assets(status="failed", error_type="L1")
        query_assets(date_from="2025-01-01", date_to="2025-12-31")
    """
    if limit > 1000:
        limit = 1000
    
    async with get_session() as session:
        assets = await query_assets_from_db(
            session,
            customer=customer,
            status=status,
            error_type=error_type,
            location=location,
            date_from=date_from,
            date_to=date_to,
            limit=limit
        )
        
        # Format response
        result = []
        for asset in assets:
            result.append({
                "serial_number": asset.serial_number,
                "customer": asset.data.get("Customer"),
                "status": asset.data.get("status"),
                "error_type": asset.data.get("error_type"),
                "location": asset.data.get("Location"),
                "failtype": asset.data.get("Failtype"),
                "date": asset.data.get("Mfg Date Code"),
                "l1": asset.data.get("L1"),
                "l2": asset.data.get("L2"),
                "ate": asset.data.get("ATE"),
                "slt": asset.data.get("SLT")
            })
        
        return json.dumps({
            "count": len(result),
            "limit": limit,
            "assets": result
        }, indent=2)


@mcp.tool()
async def get_asset_details(serial_number: str) -> str:
    """
    Get complete details for a specific serial number.
    Includes all fields, source files, and metadata.
    
    Args:
        serial_number: The serial number to look up
    
    Returns:
        JSON object with full asset data
    
    Example:
        get_asset_details("9AMA377P50091_100-000001359")
    """
    async with get_session() as session:
        asset = await get_asset_by_serial(session, serial_number)
        
        if not asset:
            return json.dumps({
                "error": f"Asset not found: {serial_number}"
            })
        
        return json.dumps({
            "serial_number": asset.serial_number,
            "data": asset.data,
            "source_file": asset.source_file,
            "source_sheet": asset.source_sheet,
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat()
        }, indent=2)


@mcp.tool()
async def get_stats(grouping: str = "customer") -> str:
    """
    Get aggregated statistics grouped by different dimensions.
    
    Args:
        grouping: How to group the data. Options:
            - "customer": Group by customer name
            - "error": Group by error type
            - "status": Group by status
            - "location": Group by location
            - "tier": Group by first failing tier (L1, L2, ATE, etc.)
            - "timeline": Group by date
    
    Returns:
        JSON object with counts and percentages
    
    Examples:
        get_stats(grouping="customer")
        get_stats(grouping="tier")
    """
    async with get_session() as session:
        stats = await get_statistics(session, grouping)
        return json.dumps(stats, indent=2)


@mcp.tool()
async def search_failures(query: str, limit: int = 50) -> str:
    """
    Search across all fields using natural language query.
    Searches serial numbers, customers, errors, locations, statuses, etc.
    
    Args:
        query: Search text (e.g., "cache error", "ALIBABA L1")
        limit: Maximum number of results (default 50)
    
    Returns:
        JSON array of matching assets
    
    Examples:
        search_failures("cache error L1")
        search_failures("ALIBABA")
    """
    async with get_session() as session:
        assets = await search_assets(session, query, limit)
        
        result = []
        for asset in assets:
            result.append({
                "serial_number": asset.serial_number,
                "customer": asset.data.get("Customer"),
                "error_type": asset.data.get("error_type"),
                "status": asset.data.get("status"),
                "location": asset.data.get("Location")
            })
        
        return json.dumps({
            "query": query,
            "count": len(result),
            "results": result
        }, indent=2)


@mcp.tool()
async def analyze_customer(customer: str) -> str:
    """
    Get comprehensive insights for a specific customer.
    Includes failure counts, error types, tier analysis, etc.
    
    Args:
        customer: Customer name (e.g., "ALIBABA", "TENCENT")
    
    Returns:
        JSON with customer analysis including:
        - Total assets
        - Serial numbers
        - Error type breakdown
        - Status breakdown
        - Tier failure analysis
    
    Example:
        analyze_customer("ALIBABA")
    """
    async with get_session() as session:
        insights = await get_customer_insights(session, customer)
        return json.dumps(insights, indent=2)


@mcp.tool()
async def count_assets(
    customer: Optional[str] = None,
    status: Optional[str] = None,
    error_type: Optional[str] = None
) -> str:
    """
    Get count of assets matching filters without returning full data.
    Useful for quick counts when you don't need the actual records.
    
    Args:
        customer: Filter by customer
        status: Filter by status
        error_type: Filter by error type
    
    Returns:
        JSON with count
    
    Examples:
        count_assets(customer="ALIBABA")
        count_assets(error_type="L1")
    """
    async with get_session() as session:
        assets = await query_assets_from_db(
            session,
            customer=customer,
            status=status,
            error_type=error_type,
            limit=100000  # High limit to get all
        )
        
        return json.dumps({
            "filters": {
                "customer": customer,
                "status": status,
                "error_type": error_type
            },
            "count": len(assets)
        })


# Resources

@mcp.resource("silicon-trace://database/summary")
async def database_summary() -> str:
    """
    Get overview of current database state.
    Shows total assets, customers, error types, date ranges.
    """
    async with get_session() as session:
        summary = await get_database_summary(session)
        return json.dumps(summary, indent=2)


@mcp.resource("silicon-trace://database/customers")
async def customers_list() -> str:
    """
    List of all customers with failure counts.
    Updated in real-time from database.
    """
    async with get_session() as session:
        stats = await get_statistics(session, "customer")
        return json.dumps(stats, indent=2)


@mcp.resource("silicon-trace://database/error-types")
async def error_types() -> str:
    """
    All unique error types seen in the database.
    Includes frequency counts.
    """
    async with get_session() as session:
        stats = await get_statistics(session, "error")
        return json.dumps(stats, indent=2)


@mcp.resource("silicon-trace://database/tiers")
async def tier_analysis() -> str:
    """
    Tier failure analysis showing which test stages have failures.
    """
    async with get_session() as session:
        stats = await get_statistics(session, "tier")
        return json.dumps(stats, indent=2)


# Run server
if __name__ == "__main__":
    # Run as HTTP server
    mcp.run(transport="sse")
