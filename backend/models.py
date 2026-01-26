"""
SQLModel definitions for Silicon Trace application.
Defines the Asset table structure for storing hardware failure data.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column, JSON
from sqlalchemy import Index


class Asset(SQLModel, table=True):
    """
    Asset table for storing hardware failure analysis data.
    
    The raw_data column stores the entire original Excel row as JSON,
    enabling verification of data transformations and debugging.
    """
    __tablename__ = "assets"
    
    # Primary key - UUID for distributed systems compatibility
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    
    # Serial number - the main identifier for hardware assets
    # Indexed for fast lookups
    serial_number: str = Field(
        index=True,
        nullable=False,
        unique=True,
        max_length=255
    )
    
    # Optional classification fields
    error_type: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True
    )
    
    status: Optional[str] = Field(
        default=None,
        max_length=100,
        nullable=True
    )
    
    # Metadata about the ingestion
    ingest_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False
    )
    
    source_filename: str = Field(
        nullable=False,
        max_length=500
    )
    
    # Critical: Store the entire original Excel row as JSON
    # This enables verification and debugging of the normalization process
    raw_data: dict = Field(
        default={},
        sa_column=Column(JSON, nullable=False)
    )
    
    class Config:
        """SQLModel configuration"""
        schema_extra = {
            "example": {
                "serial_number": "ABC12345XYZ",
                "error_type": "Memory Failure",
                "status": "Failed",
                "source_filename": "hardware_log_2024.xlsx",
                "raw_data": {
                    "SN": "ABC12345XYZ",
                    "Error": "Memory Failure",
                    "Status": "Failed",
                    "Date": "2024-01-15"
                }
            }
        }


# Create additional indexes for performance
Index('idx_serial_number', Asset.serial_number)
Index('idx_ingest_timestamp', Asset.ingest_timestamp)
