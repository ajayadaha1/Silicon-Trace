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
from parser import parse_excel


# Initialize FastAPI app
app = FastAPI(
    title="Silicon Trace API",
    description="Hardware Failure Analysis Tool - Backend API",
    version="1.0.0"
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
        "version": "1.0.0"
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_excel(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Upload and parse an Excel file containing asset data.
    
    The endpoint:
    1. Accepts .xlsx files
    2. Intelligently detects serial number column
    3. Parses and normalizes data
    4. Performs upsert based on serial number (updates if exists, creates if new)
    
    Args:
        file: Excel file upload
        session: Database session
        
    Returns:
        UploadResponse with processing statistics
    """
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls) are supported"
        )
    
    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        # Parse the Excel file
        try:
            parsed_records = parse_excel(tmp_file_path, original_filename=file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error parsing Excel file: {str(e)}"
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
        
        # Process records - upsert based on serial number
        rows_created = 0
        rows_updated = 0
        
        for record in parsed_records:
            # Check if asset already exists
            stmt = select(Asset).where(Asset.serial_number == record['serial_number'])
            result = await session.execute(stmt)
            existing_asset = result.scalar_one_or_none()
            
            if existing_asset:
                # Update existing record (keep original ingest_timestamp)
                existing_asset.error_type = record['error_type']
                existing_asset.status = record['status']
                existing_asset.source_filename = record['source_filename']
                existing_asset.raw_data = record['raw_data']
                # Don't update ingest_timestamp - preserve original creation time
                rows_updated += 1
            else:
                # Create new record
                new_asset = Asset(**record)
                session.add(new_asset)
                rows_created += 1
        
        # Commit transaction
        await session.commit()
        
        return UploadResponse(
            success=True,
            message=f"Successfully processed {len(parsed_records)} records",
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
    
    Args:
        q: Search query string
        limit: Maximum number of results to return
        session: Database session
        
    Returns:
        SearchResponse with matching assets
    """
    # Build search query - case-insensitive partial matching
    search_pattern = f"%{q}%"
    
    stmt = select(Asset).where(
        or_(
            Asset.serial_number.ilike(search_pattern),
            Asset.error_type.ilike(search_pattern),
            Asset.status.ilike(search_pattern)
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
    limit: int = Query(50, ge=1, le=1000, description="Maximum results to return"),
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
