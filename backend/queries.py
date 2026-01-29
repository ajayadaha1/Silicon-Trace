"""
Shared query logic for both FastAPI and MCP server.
This module provides reusable database query functions.
"""

from sqlmodel import select, func
from models import Asset
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime


async def query_assets_from_db(
    session,
    customer: Optional[str] = None,
    status: Optional[str] = None,
    error_type: Optional[str] = None,
    location: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100
) -> List[Asset]:
    """
    Query assets with multiple filter options.
    
    Args:
        session: Database session
        customer: Filter by customer name
        status: Filter by status
        error_type: Filter by error type
        location: Filter by location
        date_from: Filter by date (ISO format)
        date_to: Filter by date (ISO format)
        limit: Maximum number of results
    
    Returns:
        List of Asset objects
    """
    query = select(Asset)
    
    if customer:
        query = query.where(Asset.data['Customer'].astext.ilike(f"%{customer}%"))
    
    if status:
        query = query.where(Asset.data['status'].astext.ilike(f"%{status}%"))
    
    if error_type:
        query = query.where(Asset.data['error_type'].astext.ilike(f"%{error_type}%"))
    
    if location:
        query = query.where(Asset.data['Location'].astext.ilike(f"%{location}%"))
    
    if date_from:
        query = query.where(Asset.data['Mfg Date Code'].astext >= date_from)
    
    if date_to:
        query = query.where(Asset.data['Mfg Date Code'].astext <= date_to)
    
    query = query.limit(limit)
    result = await session.exec(query)
    return result.all()


async def get_asset_by_serial(session, serial_number: str) -> Optional[Asset]:
    """Get a specific asset by serial number."""
    query = select(Asset).where(Asset.serial_number == serial_number)
    result = await session.exec(query)
    return result.first()


async def get_database_summary(session) -> Dict[str, Any]:
    """Get high-level database summary."""
    result = await session.exec(select(Asset))
    all_assets = result.all()
    
    if not all_assets:
        return {
            "total_assets": 0,
            "customers": [],
            "error_types": [],
            "date_range": None
        }
    
    # Extract data
    df = pd.DataFrame([asset.data for asset in all_assets])
    
    customers = df['Customer'].dropna().unique().tolist() if 'Customer' in df else []
    error_types = df['error_type'].dropna().unique().tolist() if 'error_type' in df else []
    
    dates = []
    if 'Mfg Date Code' in df:
        dates = df['Mfg Date Code'].dropna().tolist()
    
    date_range = None
    if dates:
        try:
            date_range = f"{min(dates)} to {max(dates)}"
        except:
            date_range = "Various dates"
    
    return {
        "total_assets": len(all_assets),
        "customers": sorted(customers),
        "error_types": sorted(error_types)[:20],  # Top 20
        "date_range": date_range,
        "last_updated": max(a.updated_at for a in all_assets).isoformat() if all_assets else None
    }


async def get_statistics(session, grouping: str = "customer") -> Dict[str, Any]:
    """
    Get aggregated statistics grouped by different dimensions.
    
    Args:
        grouping: One of 'customer', 'error', 'status', 'location', 'tier', 'timeline'
    """
    result = await session.exec(select(Asset))
    all_assets = result.all()
    
    if not all_assets:
        return {"error": "No assets found"}
    
    df = pd.DataFrame([asset.data for asset in all_assets])
    
    if grouping == "customer":
        if 'Customer' in df:
            counts = df['Customer'].value_counts().to_dict()
            total = sum(counts.values())
            return {
                "grouping": "customer",
                "counts": counts,
                "percentages": {k: round(v/total*100, 2) for k, v in counts.items()}
            }
    
    elif grouping == "error":
        if 'error_type' in df:
            counts = df['error_type'].value_counts().to_dict()
            return {"grouping": "error_type", "counts": counts}
    
    elif grouping == "status":
        if 'status' in df:
            counts = df['status'].value_counts().to_dict()
            return {"grouping": "status", "counts": counts}
    
    elif grouping == "location":
        if 'Location' in df:
            counts = df['Location'].value_counts().to_dict()
            return {"grouping": "location", "counts": counts}
    
    elif grouping == "tier":
        # Find first failing tier
        tier_cols = ['L1', 'L2', 'ATE', 'SLT', 'CESLT', 'OSV']
        available_tiers = [col for col in tier_cols if col in df]
        
        if available_tiers:
            first_fails = []
            for _, row in df.iterrows():
                for tier in available_tiers:
                    if pd.notna(row.get(tier)) and str(row.get(tier)).lower() in ['fail', 'failed', 'f']:
                        first_fails.append(tier)
                        break
            
            if first_fails:
                counts = pd.Series(first_fails).value_counts().to_dict()
                return {"grouping": "tier", "counts": counts}
    
    elif grouping == "timeline":
        if 'Mfg Date Code' in df:
            # Group by date
            counts = df['Mfg Date Code'].value_counts().sort_index().to_dict()
            return {"grouping": "timeline", "counts": counts}
    
    return {"error": f"Grouping '{grouping}' not supported or no data available"}


async def search_assets(session, query: str, limit: int = 50) -> List[Asset]:
    """
    Search assets across multiple fields.
    """
    # Search in multiple fields using OR logic
    search_query = select(Asset).where(
        (Asset.serial_number.ilike(f"%{query}%")) |
        (Asset.data['Customer'].astext.ilike(f"%{query}%")) |
        (Asset.data['error_type'].astext.ilike(f"%{query}%")) |
        (Asset.data['Location'].astext.ilike(f"%{query}%")) |
        (Asset.data['status'].astext.ilike(f"%{query}%"))
    ).limit(limit)
    
    result = await session.exec(search_query)
    return result.all()


async def get_customer_insights(session, customer: str) -> Dict[str, Any]:
    """Get comprehensive insights for a specific customer."""
    # Get all assets for this customer
    query = select(Asset).where(Asset.data['Customer'].astext.ilike(f"%{customer}%"))
    result = await session.exec(query)
    assets = result.all()
    
    if not assets:
        return {"error": f"No assets found for customer '{customer}'"}
    
    df = pd.DataFrame([asset.data for asset in assets])
    
    insights = {
        "customer": customer,
        "total_assets": len(assets),
        "serial_numbers": [a.serial_number for a in assets]
    }
    
    # Error type breakdown
    if 'error_type' in df:
        insights["error_types"] = df['error_type'].value_counts().to_dict()
    
    # Status breakdown
    if 'status' in df:
        insights["statuses"] = df['status'].value_counts().to_dict()
    
    # Location breakdown
    if 'Location' in df:
        insights["locations"] = df['Location'].value_counts().to_dict()
    
    # Tier analysis
    tier_cols = ['L1', 'L2', 'ATE', 'SLT', 'CESLT', 'OSV']
    available_tiers = [col for col in tier_cols if col in df]
    
    if available_tiers:
        tier_failures = {}
        for tier in available_tiers:
            fail_count = df[tier].apply(
                lambda x: str(x).lower() in ['fail', 'failed', 'f'] if pd.notna(x) else False
            ).sum()
            if fail_count > 0:
                tier_failures[tier] = int(fail_count)
        
        if tier_failures:
            insights["tier_failures"] = tier_failures
    
    return insights
