"""
FastAPI backend for Silicon Trace - Hardware Failure Analysis Tool.

Provides REST API endpoints for:
- Uploading and parsing Excel files
- Retrieving asset information by serial number
- Searching assets
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import tempfile
import os

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete, func
from pydantic import BaseModel

from models import Asset
from database import get_session, init_db
from parser import parse_excel, normalize_column_name
from pptx_parser import parse_pptx
from nabu_client import get_nabu_client
from code_sandbox import get_sandbox
import pandas as pd
import json


# Initialize FastAPI app
app = FastAPI(
    title="Silicon Trace API",
    description="Hardware Failure Analysis Tool - Backend API",
    version="3.0.0",
    root_path="/api"
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response Models
class UploadResponse(BaseModel):
    """Response model for file upload endpoint"""
    success: bool
    message: str
    rows_processed: int
    rows_created: int
    rows_updated: int


class AssetResponse(BaseModel):
    """Response model for asset data"""
    id: str
    serial_number: str
    error_type: Optional[str]
    error_category: Optional[str]  # High-level categorization of error_type
    status: Optional[str]
    customer: Optional[str]  # Extracted from raw_data for easier access
    tier: Optional[str]  # Test tier (ATE, SLT, FT1, FT2, etc.) extracted from TEST_TIER columns
    ingest_timestamp: str
    source_filename: str
    raw_data: dict
    
    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Response model for search results"""
    total: int
    assets: List[AssetResponse]


# Startup event
@app.on_event("startup")
async def on_startup():
    """Initialize database on application startup"""
    await init_db()
    print("✓ Database initialized successfully")


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "service": "Silicon Trace API",
        "status": "operational",
        "version": "3.0.0"
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Upload and parse an Excel or PowerPoint file containing asset data.
    
    The endpoint:
    1. Accepts .xlsx, .xls, .xlsb, .pptx files
    2. Intelligently detects serial number column/data
    3. Parses and normalizes data
    4. Performs upsert based on serial number (updates if exists, creates if new)
    
    Supported formats:
    - Excel (.xlsx, .xls, .xlsb): Tables with serial numbers
    - PowerPoint (.pptx): Native tables, text content, or image-based tables (OCR)
    
    Args:
        file: Excel or PowerPoint file upload
        session: Database session
        
    Returns:
        UploadResponse with processing statistics
    """
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls', '.xlsb', '.pptx')):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls, .xlsb) and PowerPoint files (.pptx) are supported"
        )
    
    # Save uploaded file temporarily
    try:
        # Check if this exact filename was already uploaded
        # Check both source_filename field and _files_combined in raw_data
        stmt = select(Asset).where(Asset.source_filename == file.filename).limit(1)
        result = await session.execute(stmt)
        existing_by_source = result.scalar_one_or_none()
        
        if existing_by_source:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has already been uploaded. Please delete existing data first if you want to re-upload."
            )
        
        # Also check if filename appears in any _files_combined field using JSONB query
        # Use PostgreSQL's JSONB text search operator
        from sqlalchemy import text as sql_text
        stmt = sql_text(
            "SELECT COUNT(*) FROM assets WHERE raw_data->>'_files_combined' LIKE :filename"
        )
        result = await session.execute(stmt, {"filename": f"%{file.filename}%"})
        count = result.scalar()
        
        if count and count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has already been uploaded as part of merged data. Please delete existing data first if you want to re-upload."
            )
        
        # Determine file extension and create appropriate temp file
        file_ext = Path(file.filename).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        # Parse the file based on type
        try:
            if file_ext in ['.xlsx', '.xls', '.xlsb']:
                parsed_records = parse_excel(tmp_file_path, original_filename=file.filename)
            elif file_ext == '.pptx':
                parsed_records = parse_pptx(tmp_file_path, original_filename=file.filename)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error parsing file: {str(e)}"
            )
        finally:
            # Clean up temp file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
        
        if not parsed_records:
            return UploadResponse(
                success=True,
                message="No valid records found in the file",
                rows_processed=0,
                rows_created=0,
                rows_updated=0
            )
        
        # Deduplicate records by serial number (keep first occurrence)
        # This handles cases where PPTX has same serial number on multiple slides
        seen_serials = {}
        deduped_records = []
        duplicates_removed = 0
        
        for record in parsed_records:
            serial = record['serial_number']
            if serial not in seen_serials:
                seen_serials[serial] = True
                deduped_records.append(record)
            else:
                duplicates_removed += 1
        
        if duplicates_removed > 0:
            print(f"ℹ Removed {duplicates_removed} duplicate serial numbers within the file")
        
        # Process records - upsert based on serial number
        rows_created = 0
        rows_updated = 0
        rows_merged_from_multiple_files = 0
        
        for record in deduped_records:
            # Check if asset already exists
            stmt = select(Asset).where(Asset.serial_number == record['serial_number'])
            result = await session.execute(stmt)
            existing_asset = result.scalar_one_or_none()
            
            if existing_asset:
                # Track if this is a merge from a different file
                is_different_file = existing_asset.source_filename != record['source_filename']
                if is_different_file:
                    rows_merged_from_multiple_files += 1
                    print(f"Merging data for serial {record['serial_number']}: {existing_asset.source_filename} + {record['source_filename']}")
                
                # Merge data from multiple files instead of replacing
                # Track which files contributed data
                existing_files = existing_asset.raw_data.get('_files_combined', existing_asset.source_filename)
                new_file = record['source_filename']
                
                # Add new file to the list if not already there
                if new_file not in existing_files:
                    existing_asset.raw_data['_files_combined'] = f"{existing_files} | {new_file}"
                else:
                    existing_asset.raw_data['_files_combined'] = existing_files
                
                # Merge raw_data columns intelligently
                for key, new_value in record['raw_data'].items():
                    if key.startswith('_'):
                        # Handle metadata fields specially
                        if key == '_sheets_combined':
                            # Append new sheets info
                            old_sheets = existing_asset.raw_data.get('_sheets_combined', '')
                            existing_asset.raw_data['_sheets_combined'] = f"{old_sheets} | {new_value}" if old_sheets else new_value
                        elif key == '_total_sheets':
                            # Sum total sheets
                            existing_asset.raw_data['_total_sheets'] = existing_asset.raw_data.get('_total_sheets', 0) + new_value
                        elif key not in ['_source_sheet', '_source_row', '_serial_column']:
                            # Preserve other metadata
                            existing_asset.raw_data[key] = new_value
                        continue
                    
                    # Check if column already exists (with normalization)
                    normalized_key = normalize_column_name(key)
                    existing_key = None
                    
                    for existing_col in existing_asset.raw_data.keys():
                        if not existing_col.startswith('_'):
                            if normalize_column_name(existing_col) == normalized_key:
                                existing_key = existing_col
                                break
                    
                    if existing_key:
                        # Column exists - check if values differ
                        existing_value = existing_asset.raw_data[existing_key]
                        if existing_value != new_value:
                            # Concatenate different values
                            existing_asset.raw_data[existing_key] = f"{existing_value} | {new_value}"
                        # else: same value, skip
                    else:
                        # New column - add it
                        existing_asset.raw_data[key] = new_value
                
                # Update error_type and status if new ones are available
                if record['error_type']:
                    existing_asset.error_type = record['error_type']
                if record['status']:
                    existing_asset.status = record['status']
                
                # Update source_filename to show latest file
                existing_asset.source_filename = record['source_filename']
                
                # Don't update ingest_timestamp - preserve original creation time
                rows_updated += 1
            else:
                # Create new record
                new_asset = Asset(**record)
                session.add(new_asset)
                rows_created += 1
        
        # Commit transaction
        await session.commit()
        
        # Log summary
        if rows_merged_from_multiple_files > 0:
            print(f"✓ Multi-file merge summary: {rows_merged_from_multiple_files} serial numbers found in multiple files")
        
        return UploadResponse(
            success=True,
            message=f"Successfully processed {len(parsed_records)} records ({rows_merged_from_multiple_files} merged from multiple files)",
            rows_processed=len(parsed_records),
            rows_created=rows_created,
            rows_updated=rows_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/assets/{serial_number}", response_model=AssetResponse)
async def get_asset(
    serial_number: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Retrieve asset details by serial number.
    
    Returns the normalized asset data along with the complete raw JSON
    from the original Excel row for verification.
    
    Args:
        serial_number: The serial number to search for
        session: Database session
        
    Returns:
        AssetResponse with complete asset details including raw_data
    """
    stmt = select(Asset).where(Asset.serial_number == serial_number)
    result = await session.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=404,
            detail=f"Asset with serial number '{serial_number}' not found"
        )
    
    # Extract customer and tier
    customer = None
    tier = None
    if asset.raw_data:
        customer = asset.raw_data.get('Customer')
        if not customer:
            column_classification = asset.raw_data.get('_column_classification', {})
            for col, category in column_classification.items():
                if category == 'CUSTOMER' and col in asset.raw_data:
                    customer = asset.raw_data.get(col)
                    if customer:
                        break
        
        column_classification = asset.raw_data.get('_column_classification', {})
        tier_values = []
        for col, category in column_classification.items():
            if category == 'TEST_TIER' and col in asset.raw_data:
                value = asset.raw_data.get(col)
                if value and str(value).strip() not in ['', 'N/A', 'NA', 'None']:
                    tier_values.append(str(value).strip())
        if tier_values:
            tier = ', '.join(tier_values)
    
    if not tier:
        tier = "Not Specified"
    
    return AssetResponse(
        id=str(asset.id),
        serial_number=asset.serial_number,
        error_type=asset.error_type,
        error_category=_categorize_error(asset.error_type),
        status=asset.status,
        customer=customer,
        tier=tier,
        ingest_timestamp=asset.ingest_timestamp.isoformat(),
        source_filename=asset.source_filename,
        raw_data=asset.raw_data
    )


@app.get("/search", response_model=SearchResponse)
async def search_assets(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    session: AsyncSession = Depends(get_session)
):
    """
    Search for assets matching a query string.
    
    Searches across:
    - Serial numbers (partial match)
    - Error types (partial match)
    - Status (partial match)
    - All raw_data fields (JSONB search)
    
    Args:
        q: Search query string
        limit: Maximum number of results to return
        session: Database session
        
    Returns:
        SearchResponse with matching assets
    """
    # Build search query - case-insensitive partial matching
    search_pattern = f"%{q}%"
    
    # For JSONB search, we need to convert to text and search
    # Use raw SQL for JSONB text search
    from sqlalchemy import text, cast, String
    
    stmt = select(Asset).where(
        or_(
            Asset.serial_number.ilike(search_pattern),
            Asset.error_type.ilike(search_pattern),
            Asset.status.ilike(search_pattern),
            # Search in raw_data JSONB by casting to text
            cast(Asset.raw_data, String).ilike(search_pattern)
        )
    ).limit(limit)
    
    result = await session.execute(stmt)
    assets = result.scalars().all()
    
    # Convert to response models
    asset_responses = []
    for asset in assets:
        # Extract customer from raw_data
        customer = None
        if asset.raw_data:
            customer = asset.raw_data.get('Customer')
            if not customer:
                column_classification = asset.raw_data.get('_column_classification', {})
                for col, category in column_classification.items():
                    if category == 'CUSTOMER' and col in asset.raw_data:
                        customer = asset.raw_data.get(col)
                        if customer:
                            break
        
        # Extract tier from TEST_TIER columns
        tier = None
        if asset.raw_data:
            column_classification = asset.raw_data.get('_column_classification', {})
            # Collect all TEST_TIER column values
            tier_values = []
            for col, category in column_classification.items():
                if category == 'TEST_TIER' and col in asset.raw_data:
                    value = asset.raw_data.get(col)
                    if value and str(value).strip() not in ['', 'N/A', 'NA', 'None']:
                        tier_values.append(str(value).strip())
            
            # Join multiple tiers with comma
            if tier_values:
                tier = ', '.join(tier_values)
        
        # Default to "Not Specified" if no tier found
        if not tier:
            tier = "Not Specified"
        
        asset_responses.append(
            AssetResponse(
                id=str(asset.id),
                serial_number=asset.serial_number,
                error_type=asset.error_type,
                error_category=_categorize_error(asset.error_type),
                status=asset.status,
                customer=customer,
                tier=tier,
                ingest_timestamp=asset.ingest_timestamp.isoformat(),
                source_filename=asset.source_filename,
                raw_data=asset.raw_data
            )
        )
    
    return SearchResponse(
        total=len(asset_responses),
        assets=asset_responses
    )


@app.get("/assets", response_model=SearchResponse)
async def list_assets(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(1000, ge=1, le=50000, description="Maximum results to return"),
    source_files: Optional[str] = Query(None, description="Comma-separated list of source filenames to filter"),
    session: AsyncSession = Depends(get_session)
):
    """
    List all assets with pagination and optional filtering by source files.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of results to return
        source_files: Optional comma-separated list of source filenames to filter by
        session: Database session
        
    Returns:
        SearchResponse with assets
    """
    stmt = select(Asset)
    
    # Apply source file filter if provided
    if source_files:
        file_list = [f.strip() for f in source_files.split(',')]
        stmt = stmt.where(Asset.source_filename.in_(file_list))
    
    stmt = stmt.offset(skip).limit(limit)
    result = await session.execute(stmt)
    assets = result.scalars().all()
    
    # Convert to response models
    asset_responses = []
    for asset in assets:
        # Extract customer from raw_data
        customer = None
        if asset.raw_data:
            customer = asset.raw_data.get('Customer')
            if not customer:
                column_classification = asset.raw_data.get('_column_classification', {})
                for col, category in column_classification.items():
                    if category == 'CUSTOMER' and col in asset.raw_data:
                        customer = asset.raw_data.get(col)
                        if customer:
                            break
        
        # Extract tier from TEST_TIER columns
        tier = None
        if asset.raw_data:
            column_classification = asset.raw_data.get('_column_classification', {})
            # Collect all TEST_TIER column values
            tier_values = []
            for col, category in column_classification.items():
                if category == 'TEST_TIER' and col in asset.raw_data:
                    value = asset.raw_data.get(col)
                    if value and str(value).strip() not in ['', 'N/A', 'NA', 'None']:
                        tier_values.append(str(value).strip())
            
            # Join multiple tiers with comma
            if tier_values:
                tier = ', '.join(tier_values)
        
        # Default to "Not Specified" if no tier found
        if not tier:
            tier = "Not Specified"
        
        asset_responses.append(
            AssetResponse(
                id=str(asset.id),
                serial_number=asset.serial_number,
                error_type=asset.error_type,
                error_category=_categorize_error(asset.error_type),
                status=asset.status,
                customer=customer,
                tier=tier,
                ingest_timestamp=asset.ingest_timestamp.isoformat(),
                source_filename=asset.source_filename,
                raw_data=asset.raw_data
            )
        )
    
    return SearchResponse(
        total=len(asset_responses),
        assets=asset_responses
    )


@app.get("/source-files")
async def get_source_files(session: AsyncSession = Depends(get_session)):
    """
    Get list of all unique source filenames with asset counts.
    
    Returns:
        List of source filenames with metadata
    """
    # Get distinct source filenames with counts
    from sqlalchemy import func
    
    stmt = select(
        Asset.source_filename,
        func.count(Asset.id).label('asset_count'),
        func.max(Asset.ingest_timestamp).label('last_updated')
    ).group_by(Asset.source_filename).order_by(Asset.source_filename)
    
    result = await session.execute(stmt)
    files = result.all()
    
    return {
        "source_files": [
            {
                "filename": row[0],
                "asset_count": row[1],
                "last_updated": row[2].isoformat() if row[2] else None
            }
            for row in files
        ]
    }


@app.get("/files")
async def get_files(session: AsyncSession = Depends(get_session)):
    """
    Get list of all unique source filenames (alias for /source-files for compatibility).
    
    Returns:
        List of source filenames
    """
    # Get distinct source filenames with counts
    from sqlalchemy import func
    
    stmt = select(
        Asset.source_filename,
        func.count(Asset.id).label('asset_count'),
        func.max(Asset.ingest_timestamp).label('last_updated')
    ).group_by(Asset.source_filename).order_by(Asset.source_filename)
    
    result = await session.execute(stmt)
    files = result.all()
    
    return {
        "files": [row[0] for row in files]
    }


@app.delete("/source-files/{filename}")
async def delete_source_file(
    filename: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Delete all assets from a specific source file.
    
    Args:
        filename: Source filename to delete
        session: Database session
        
    Returns:
        Deletion confirmation with count
    """
    # Count assets before deletion
    count_stmt = select(func.count(Asset.id)).where(Asset.source_filename == filename)
    result = await session.execute(count_stmt)
    count = result.scalar()
    
    if count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No assets found from source file: {filename}"
        )
    
    # Delete assets
    delete_stmt = delete(Asset).where(Asset.source_filename == filename)
    await session.execute(delete_stmt)
    await session.commit()
    
    return {
        "success": True,
        "message": f"Deleted {count} asset(s) from {filename}",
        "deleted_count": count,
        "filename": filename
    }


# AI Co-Analyst Endpoints
# Configuration for Nabu API
NABU_API_TOKEN = os.getenv("NABU_API_TOKEN", "11b3446d3714401a8bc89eba04c4e343")

# MCP Server Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8000/sse")
# MCP Tools available to Nabu AI for dynamic querying
MCP_SERVER_CONFIG = [
    {
        "name": "silicon-trace",
        "url": MCP_SERVER_URL,
        "description": "Silicon Trace hardware failure database with 6 query tools and 4 resources"
    }
]


class ChatRequest(BaseModel):
    """Request model for AI chat"""
    message: str
    file_ids: Optional[List[str]] = []
    chat_id: Optional[str] = None
    history: Optional[List[Dict]] = []


class AnalyzeRequest(BaseModel):
    """Request model for AI data analysis"""
    file_ids: Optional[List[str]] = []
    focus_areas: Optional[List[str]] = None


class VisualizeRequest(BaseModel):
    """Request model for AI visualization generation"""
    request: str
    file_ids: Optional[List[str]] = []


class InvestigateRequest(BaseModel):
    """Request model for AI root cause analysis"""
    topic: str
    file_ids: Optional[List[str]] = []
    max_steps: int = 5


@app.post("/ai/chat")
async def ai_chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Conversational AI interface for data exploration
    
    Allows users to ask questions about their failure data and get
    intelligent responses with optional visualizations.
    """
    try:
        # Get data context
        data_context = await _get_data_context(session, request.file_ids)
        
        # Enhance prompt with comprehensive data context
        enhanced_prompt = f"""You are analyzing hardware failure data for Silicon Trace.

COMPLETE DATA SUMMARY (ALL {data_context['total_assets']} RECORDS):

📊 FULL STATISTICS FOR EVERY COLUMN:
{json.dumps(data_context.get('complete_statistics', {}), indent=2)}

🔢 SERIAL NUMBER DIRECTORY (ALL {len(data_context.get('serial_lookup', {}))} assets with full details):
{json.dumps(data_context.get('serial_lookup', {}), indent=2)}

📈 CUSTOMER-ERROR MATRIX (ALL combinations):
{json.dumps(data_context.get('customer_error_matrix', {}), indent=2)}

📅 TIMELINE (ALL failures by date):
{json.dumps(data_context.get('timeline', {}), indent=2)}

📝 REPRESENTATIVE SAMPLES:
{json.dumps(data_context['sample'][:3], indent=2)}

Available columns: {', '.join(data_context['columns'])}

USER QUESTION: {request.message}

IMPORTANT: You have COMPLETE data access for all {data_context['total_assets']} records above. 
The serial_lookup dictionary contains EVERY serial number with status, error_type, customer, and source file.
To answer questions about specific serial numbers:
1. Look up the serial number in serial_lookup dictionary
2. Return the status, error_type, customer, and other details

Use the full data to provide accurate responses. 
Examples:
- "What's the status of serial number 9MK7529X40025_100-000001651?" → Look it up in serial_lookup
- "Which customer has most failures?" → Use complete_statistics['Customer']
- "What error types exist?" → Use complete_statistics['error_type']
- "How many failures per date?" → Use timeline

Provide accurate, data-driven responses using the complete dataset."""

        # Call Nabu AI
        nabu = get_nabu_client(NABU_API_TOKEN)
        response = await nabu.chat(
            user_prompt=enhanced_prompt,
            history=request.history,
            chat_id=request.chat_id
        )
        
        return {
            "success": True,
            "response": response.get('responseText', response.get('response', response.get('message', ''))),
            "chat_id": request.chat_id,
            "raw_response": response
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat error: {str(e)}")


@app.post("/ai/analyze")
async def ai_analyze(
    request: AnalyzeRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Automatically analyze dataset and extract insights
    
    Returns structured insights including:
    - Key metrics summary
    - Top insights and patterns
    - Anomalies detected
    - Actionable recommendations
    """
    try:
        # Get data as DataFrame
        df = await _get_dataframe(session, request.file_ids)
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No data available for analysis")
        
        # Call Nabu AI for analysis with statistical compression
        # Note: MCP integration requires user registration in Nabu portal
        # Using proven statistical compression approach for datasets <10K records
        nabu = get_nabu_client(NABU_API_TOKEN)
        result = await nabu.analyze_dataframe(df, request.focus_areas)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Analysis failed'))
        
        analysis = result['analysis']
        
        return {
            "success": True,
            "metrics": analysis.get('key_metrics', {}),
            "insights": analysis.get('insights', []),
            "anomalies": analysis.get('anomalies', []),
            "recommendations": analysis.get('recommendations', []),
            "trend_analysis": analysis.get('trend_analysis', {}),
            "raw_response": result.get('raw_response')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.post("/ai/visualize")
async def ai_visualize(
    request: VisualizeRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Generate custom visualization based on natural language request
    
    AI generates Plotly code, executes it safely, and returns the figure
    along with the generated code.
    """
    try:
        # Get data as DataFrame
        df = await _get_dataframe(session, request.file_ids)
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No data available for visualization")
        
        # Generate code with Nabu AI
        nabu = get_nabu_client(NABU_API_TOKEN)
        code_result = await nabu.generate_visualization_code(request.request, df)
        
        if not code_result['success']:
            raise HTTPException(status_code=500, detail="Failed to generate visualization code")
        
        code = code_result['code']
        
        # Execute code in sandbox
        sandbox = get_sandbox()
        exec_result = sandbox.execute(code, df)
        
        if not exec_result['success']:
            return {
                "success": False,
                "error": exec_result['error'],
                "code": code,
                "output": exec_result.get('output', '')
            }
        
        # Convert figure to JSON
        fig_json = exec_result['figure'].to_json()
        
        return {
            "success": True,
            "figure": json.loads(fig_json),
            "code": code,
            "output": exec_result.get('output', '')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visualization error: {str(e)}")


@app.post("/ai/investigate")
async def ai_investigate(
    request: InvestigateRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Perform multi-step root cause analysis investigation
    
    AI agent autonomously explores data, generates hypotheses,
    and provides structured findings with recommendations.
    """
    try:
        # Get data as DataFrame
        df = await _get_dataframe(session, request.file_ids)
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No data available for investigation")
        
        # Call Nabu AI for investigation
        # Note: MCP integration requires user registration in Nabu portal
        # Using statistical compression for datasets <10K records
        nabu = get_nabu_client(NABU_API_TOKEN)
        result = await nabu.investigate(request.topic, df, request.max_steps)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Investigation failed'))
        
        investigation = result['investigation']
        
        return {
            "success": True,
            "hypothesis": investigation.get('hypothesis', ''),
            "steps": investigation.get('steps', []),
            "conclusion": investigation.get('conclusion', ''),
            "root_causes": investigation.get('root_causes', []),
            "recommendations": investigation.get('recommendations', []),
            "confidence": investigation.get('confidence', 'medium'),
            "raw_response": result.get('raw_response')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Investigation error: {str(e)}")


# Helper functions for AI endpoints
async def _get_data_context(
    session: AsyncSession,
    file_ids: Optional[List[str]] = None
) -> Dict:
    """Get comprehensive statistical summary of ALL data (cost-effective alternative to raw records)"""
    query = select(Asset)
    if file_ids:
        query = query.where(Asset.source_filename.in_(file_ids))
    
    result = await session.execute(query.limit(1000))
    assets = result.scalars().all()
    
    if not assets:
        return {
            'total_assets': 0,
            'unique_customers': 0,
            'columns': [],
            'sample': []
        }
    
    # Get all unique columns from raw_data
    all_columns = set()
    for asset in assets:
        if asset.raw_data:
            all_columns.update(asset.raw_data.keys())
    
    # Build comprehensive statistics for ALL key columns
    # This gives AI complete information without sending raw records
    stats = {}
    
    # Collect all data for analysis
    for col in ['Customer', 'Failtype', 'status', 'error_type', 'Location', 'Mfg Date Code', 
                'Failing suite', 'L1', 'L2', 'ATE', 'SLT', 'CESLT', 'OSV']:
        values = {}
        for asset in assets:
            if col == 'status':
                val = asset.status
            elif col == 'error_type':
                val = asset.error_type
            elif asset.raw_data and col in asset.raw_data:
                val = asset.raw_data[col]
            else:
                continue
            
            if val and val != 'nan':
                values[val] = values.get(val, 0) + 1
        
        if values:
            stats[col] = dict(sorted(values.items(), key=lambda x: x[1], reverse=True))
    
    # Get ALL serial numbers with their key attributes (small dataset, affordable)
    all_serials = [asset.serial_number for asset in assets if asset.serial_number]
    
    # Create serial number to asset info mapping for direct lookup
    serial_lookup = {}
    for asset in assets:
        if asset.serial_number:
            # Extract customer
            customer = None
            if asset.raw_data:
                customer = asset.raw_data.get('Customer')
                if not customer:
                    column_classification = asset.raw_data.get('_column_classification', {})
                    for col, category in column_classification.items():
                        if category == 'CUSTOMER' and col in asset.raw_data:
                            customer = asset.raw_data.get(col)
                            if customer:
                                break
            
            serial_lookup[asset.serial_number] = {
                'status': asset.status,
                'error_type': asset.error_type,
                'customer': customer,
                'source_filename': asset.source_filename
            }
    
    # Cross-tabulation: Customer x Error Type
    customer_errors = {}
    for asset in assets:
        customer = asset.raw_data.get('Customer') if asset.raw_data else None
        error = asset.error_type
        if customer and error:
            key = f"{customer}|{error}"
            customer_errors[key] = customer_errors.get(key, 0) + 1
    
    # Time series: failures by date
    failures_by_date = {}
    for asset in assets:
        if asset.ingest_timestamp:
            date_key = asset.ingest_timestamp.strftime('%Y-%m-%d')
            failures_by_date[date_key] = failures_by_date.get(date_key, 0) + 1
    
    # Get representative samples from each major category
    sample = []
    sampled_customers = set()
    for asset in assets[:5]:  # First 5 as general samples
        sample.append({
            'serial_number': asset.serial_number,
            'error_type': asset.error_type,
            'status': asset.status,
            **asset.raw_data
        })
        if asset.raw_data and 'Customer' in asset.raw_data:
            sampled_customers.add(asset.raw_data['Customer'])
    
    # Add one sample from each remaining customer
    for asset in assets:
        if asset.raw_data and 'Customer' in asset.raw_data:
            customer = asset.raw_data['Customer']
            if customer not in sampled_customers and len(sample) < 10:
                sample.append({
                    'serial_number': asset.serial_number,
                    'error_type': asset.error_type,
                    'status': asset.status,
                    **asset.raw_data
                })
                sampled_customers.add(customer)
    
    return {
        'total_assets': len(assets),
        'unique_customers': len(stats.get('Customer', {})),
        'all_serial_numbers': all_serials,  # Complete list for small datasets
        'serial_lookup': serial_lookup,  # Map serial number to key attributes
        'complete_statistics': stats,  # Value counts for ALL records in each column
        'customer_error_matrix': customer_errors,  # Customer x Error cross-tab
        'timeline': dict(sorted(failures_by_date.items())),  # Failures over time
        'columns': sorted(list(all_columns)),
        'sample': sample  # Representative samples for context
    }


def _categorize_error(error_type: str) -> str:
    """Categorize granular error types into higher-level categories"""
    if not error_type or error_type.strip() == '':
        return 'Unknown'
    
    error_lower = str(error_type).lower().strip()
    
    # Parity Errors
    if 'parity' in error_lower or 'prt_err' in error_lower:
        return 'Parity Error'
    
    # ECC Errors
    if 'ecc' in error_lower:
        return 'ECC Error'
    
    # Cache Errors (L2, L3)
    if any(x in error_lower for x in ['l2', 'l3', 'cache']):
        return 'Cache Error'
    
    # Memory Errors
    if any(x in error_lower for x in ['memory', 'dimm', 'dram', 'mem']):
        return 'Memory Error'
    
    # Load-Store Unit Errors
    if error_lower.startswith('ls') or 'load-store' in error_lower:
        return 'Load-Store Error'
    
    # Floating Point Errors
    if error_lower.startswith('fp') or 'floating point' in error_lower or 'fp_' in error_lower:
        return 'Floating Point Error'
    
    # Integer Execution Errors
    if error_lower.startswith('ex') or error_lower == 'de' or 'execution' in error_lower:
        return 'Execution Unit Error'
    
    # Coherent Slave/Master Errors
    if error_lower.startswith('cs') or error_lower.startswith('if') or 'coherent' in error_lower:
        return 'Coherent Error'
    
    # GMI (Global Memory Interconnect) Errors
    if 'gmi' in error_lower or 'interconnect' in error_lower:
        return 'Interconnect Error'
    
    # Test Program Errors
    if any(x in error_lower for x in ['afhc', 'memtester', 'stressng', 'avt', 'bist', 'hdrt']):
        return 'Test Program'
    
    # System/Application Errors
    if any(x in error_lower for x in ['online', 'app', 'application', 'crash', 'hang', 'boot', 'reboot']):
        return 'System/Application Error'
    
    # Power/Thermal Errors
    if any(x in error_lower for x in ['power', 'thermal', 'temp', 'voltage', 'ac/dc', 'cycle']):
        return 'Power/Thermal Error'
    
    # PCIe Errors
    if 'pcie' in error_lower or 'pci' in error_lower:
        return 'PCIe Error'
    
    # BMC Errors
    if 'bmc' in error_lower:
        return 'BMC Error'
    
    # Watchdog Timer Errors
    if 'wdt' in error_lower or 'watchdog' in error_lower:
        return 'Watchdog Error'
    
    # Health Check / Diagnostic Errors
    if any(x in error_lower for x in ['health', 'diagnostic', 'check']):
        return 'Health Check'
    
    # Core/CPU Specific Errors
    if 'core' in error_lower or 'cpu' in error_lower:
        return 'Core/CPU Error'
    
    # Unknown/Other
    return 'Other'


async def _get_dataframe(
    session: AsyncSession,
    file_ids: Optional[List[str]] = None,
    limit: int = 50000
) -> pd.DataFrame:
    """Get data as pandas DataFrame for AI analysis"""
    query = select(Asset)
    if file_ids:
        query = query.where(Asset.source_filename.in_(file_ids))
    
    query = query.limit(limit)
    result = await session.execute(query)
    assets = result.scalars().all()
    
    if not assets:
        return pd.DataFrame()
    
    # Convert to list of dicts
    data = []
    for asset in assets:
        # Extract customer from raw_data
        customer = None
        if asset.raw_data:
            customer = asset.raw_data.get('Customer')
            if not customer:
                column_classification = asset.raw_data.get('_column_classification', {})
                for col, category in column_classification.items():
                    if category == 'CUSTOMER' and col in asset.raw_data:
                        customer = asset.raw_data.get(col)
                        if customer:
                            break
        
        # Extract tier from TEST_TIER columns
        tier = None
        if asset.raw_data:
            column_classification = asset.raw_data.get('_column_classification', {})
            tier_values = []
            for col, category in column_classification.items():
                if category == 'TEST_TIER' and col in asset.raw_data:
                    value = asset.raw_data.get(col)
                    if value and str(value).strip() not in ['', 'N/A', 'NA', 'None']:
                        tier_values.append(str(value).strip())
            if tier_values:
                tier = ', '.join(tier_values)
        
        # Default to "Not Specified" if no tier found
        if not tier:
            tier = "Not Specified"
        
        # Categorize error type
        error_category = _categorize_error(asset.error_type)
        
        row = {
            'id': str(asset.id),
            'serial_number': asset.serial_number,
            'error_type': asset.error_type,
            'error_category': error_category,
            'status': asset.status,
            'customer': customer,
            'tier': tier,
            'source_filename': asset.source_filename,
            'ingest_timestamp': asset.ingest_timestamp
        }
        if asset.raw_data:
            # Convert raw_data values to strings if they're lists/dicts
            # This prevents "unhashable type" errors in pandas operations
            for key, value in asset.raw_data.items():
                if isinstance(value, (list, dict)):
                    row[key] = str(value)
                else:
                    row[key] = value
        data.append(row)
    
    return pd.DataFrame(data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
