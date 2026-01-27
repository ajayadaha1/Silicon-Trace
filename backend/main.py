"""
FastAPI backend for Silicon Trace - Hardware Failure Analysis Tool.

Provides REST API endpoints for:
- Uploading and parsing Excel files
- Retrieving asset information by serial number
- Searching assets
"""

from typing import List, Optional
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


# Initialize FastAPI app
app = FastAPI(
    title="Silicon Trace API",
    description="Hardware Failure Analysis Tool - Backend API",
    version="3.0.0"
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
    status: Optional[str]
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
    1. Accepts .xlsx, .xls, .pptx files
    2. Intelligently detects serial number column/data
    3. Parses and normalizes data
    4. Performs upsert based on serial number (updates if exists, creates if new)
    
    Supported formats:
    - Excel (.xlsx, .xls): Tables with serial numbers
    - PowerPoint (.pptx): Native tables, text content, or image-based tables (OCR)
    
    Args:
        file: Excel or PowerPoint file upload
        session: Database session
        
    Returns:
        UploadResponse with processing statistics
    """
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls', '.pptx')):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls) and PowerPoint files (.pptx) are supported"
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
            if file_ext in ['.xlsx', '.xls']:
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
    
    return AssetResponse(
        id=str(asset.id),
        serial_number=asset.serial_number,
        error_type=asset.error_type,
        status=asset.status,
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
    asset_responses = [
        AssetResponse(
            id=str(asset.id),
            serial_number=asset.serial_number,
            error_type=asset.error_type,
            status=asset.status,
            ingest_timestamp=asset.ingest_timestamp.isoformat(),
            source_filename=asset.source_filename,
            raw_data=asset.raw_data
        )
        for asset in assets
    ]
    
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
    asset_responses = [
        AssetResponse(
            id=str(asset.id),
            serial_number=asset.serial_number,
            error_type=asset.error_type,
            status=asset.status,
            ingest_timestamp=asset.ingest_timestamp.isoformat(),
            source_filename=asset.source_filename,
            raw_data=asset.raw_data
        )
        for asset in assets
    ]
    
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
