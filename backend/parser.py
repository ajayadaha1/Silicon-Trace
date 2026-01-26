"""
Intelligent Excel parser for Silicon Trace.

This module implements heuristic-based column detection to identify serial numbers
in Excel files with inconsistent or varying column headers.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
from pathlib import Path


class SerialNumberDetector:
    """
    Detects the serial number column in a DataFrame using heuristic scoring.
    
    The detector scores each column based on:
    1. Header name similarity to common serial number terms
    2. Data pattern matching (alphanumeric codes of typical length)
    """
    
    # Common serial number header patterns (case-insensitive)
    # Priority given to CPU_SN and 2d_barcode_sn
    HEADER_KEYWORDS = [
        'cpu_sn', 'cpu sn', 'cpusn',              # Highest priority
        '2d_barcode_sn', '2d_barcode', '2d',      # High priority
        'sn', 'serial', 'barcode', 'ppid',
        'serial_number', 'serialnumber', 'serial number',
        'part_id', 'asset_id', 'device_id', 'rma',
        'system_sn', 'system sn',
        'rma#', 'rma #', 'rma_number',
        'unit_sn', 'unit sn', 'device_sn', 'device serial'
    ]
    
    # Regex patterns for serial number formats
    # Primary pattern: CPU SN format like "9AMA377P50091_100-000001359"
    # Format: [ALPHANUMERIC]_[NUMERIC]-[NUMERIC]
    CPU_SN_PATTERN = re.compile(r'^[A-Z0-9]+_\d+-\d+$', re.IGNORECASE)
    
    # Secondary pattern: Standard alphanumeric codes (8-25 characters)
    SERIAL_PATTERN = re.compile(r'^[A-Z0-9]{8,25}$', re.IGNORECASE)
    
    # Tertiary pattern: Alphanumeric with underscores/dashes
    EXTENDED_PATTERN = re.compile(r'^[A-Z0-9_\-]{8,30}$', re.IGNORECASE)
    
    @classmethod
    def score_column_header(cls, column_name: str) -> float:
        """
        Score a column header based on similarity to serial number keywords.
        
        Args:
            column_name: The column header to score
            
        Returns:
            Float score (0.0 to 1.0), higher is better
        """
        if not isinstance(column_name, str):
            return 0.0
            
        col_lower = column_name.lower().strip()
        
        # Exact match gets highest score
        if col_lower in cls.HEADER_KEYWORDS:
            return 1.0
        
        # Partial match - check if any keyword is contained in the column name
        max_score = 0.0
        for keyword in cls.HEADER_KEYWORDS:
            if keyword in col_lower:
                # Score based on how much of the column name is the keyword
                # Longer matches relative to column name get higher scores
                score = len(keyword) / len(col_lower)
                max_score = max(max_score, score * 0.8)  # Cap at 0.8 for partial matches
        
        return max_score
    
    @classmethod
    def score_column_data(cls, series: pd.Series, sample_size: int = 100) -> float:
        """
        Score column data based on how well it matches serial number patterns.
        Prioritizes CPU SN format (with underscores and dashes).
        
        Args:
            series: Pandas Series containing the column data
            sample_size: Number of rows to sample for pattern matching
            
        Returns:
            Float score (0.0 to 1.0+) representing match quality
            Scores can exceed 1.0 for high-priority patterns (CPU SN format)
        """
        # Sample data for performance (use all if fewer than sample_size)
        sample = series.dropna().head(sample_size)
        
        if len(sample) == 0:
            return 0.0
        
        # Count matches for each pattern type
        cpu_sn_matches = 0
        standard_matches = 0
        extended_matches = 0
        
        for value in sample:
            # Convert to string and strip whitespace
            str_value = str(value).strip()
            
            # Check for CPU SN format (highest priority)
            if cls.CPU_SN_PATTERN.match(str_value):
                cpu_sn_matches += 1
            # Check for standard alphanumeric format
            elif cls.SERIAL_PATTERN.match(str_value):
                standard_matches += 1
            # Check for extended format (with underscores/dashes)
            elif cls.EXTENDED_PATTERN.match(str_value):
                extended_matches += 1
        
        # Calculate weighted score
        # CPU SN format gets 1.5x multiplier (can exceed 1.0)
        # Standard format gets 1.0x multiplier
        # Extended format gets 0.8x multiplier
        total_samples = len(sample)
        score = (
            (cpu_sn_matches / total_samples) * 1.5 +
            (standard_matches / total_samples) * 1.0 +
            (extended_matches / total_samples) * 0.8
        )
        
        return score
    
    @classmethod
    def detect_serial_column(cls, df: pd.DataFrame) -> Optional[str]:
        """
        Detect the most likely serial number column in a DataFrame.
        
        Algorithm:
        1. Score each column based on header name (weight: 40%)
        2. Score each column based on data patterns (weight: 60%)
        3. Select the column with the highest combined score
        
        Args:
            df: Pandas DataFrame to analyze
            
        Returns:
            Column name containing serial numbers, or None if no good candidate found
        """
        if df.empty:
            return None
        
        scores: Dict[str, Dict[str, float]] = {}
        
        for column in df.columns:
            # Calculate header score (weight: 0.4)
            header_score = cls.score_column_header(column)
            
            # Calculate data pattern score (weight: 0.6)
            data_score = cls.score_column_data(df[column])
            
            # Combined weighted score
            combined_score = (header_score * 0.4) + (data_score * 0.6)
            
            scores[column] = {
                'header_score': header_score,
                'data_score': data_score,
                'combined_score': combined_score
            }
        
        # Find the column with the highest combined score
        if not scores:
            return None
        
        best_column = max(scores.items(), key=lambda x: x[1]['combined_score'])
        best_column_name = best_column[0]
        best_score = best_column[1]['combined_score']
        
        # Only return if the score is above a minimum threshold (0.3)
        # This prevents false positives on completely unrelated data
        if best_score >= 0.3:
            return best_column_name
        
        return None


def clean_value(value: Any) -> Any:
    """
    Clean a single value for JSON serialization.
    Handles NaN, None, and pandas-specific types.
    
    Args:
        value: Any value from a DataFrame
        
    Returns:
        JSON-serializable value or None
    """
    # Handle pandas NA types
    if pd.isna(value):
        return None
    
    # Handle numpy types
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    
    # Handle datetime
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(value)
    
    # Convert to string if it's not a basic type
    if not isinstance(value, (str, int, float, bool, type(None))):
        return str(value)
    
    return value


def parse_excel(file_path: str, original_filename: str = None) -> List[Dict[str, Any]]:
    """
    Parse an Excel file and extract asset data with intelligent serial number detection.
    Handles multiple sheets and combines data based on serial numbers.
    
    Process:
    1. Read ALL sheets from Excel file
    2. Detect which column contains serial numbers in each sheet
    3. Combine data from multiple sheets based on serial numbers
    4. Normalize data and preserve raw rows as JSON
    
    Args:
        file_path: Path to the Excel file
        original_filename: Original filename (if different from file_path)
        
    Returns:
        List of dictionaries, each containing:
        - serial_number: Detected serial number
        - error_type: Error classification (if available)
        - status: Status field (if available)
        - source_filename: Original filename
        - raw_data: Complete merged data from all sheets as dict
        
    Raises:
        ValueError: If no serial number column can be detected
        FileNotFoundError: If the file doesn't exist
    """
    # Read Excel file
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    
    # Use original filename if provided, otherwise use the file path name
    source_filename = original_filename if original_filename else file_path_obj.name
    
    # Read ALL sheets from the Excel file
    try:
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
    except Exception as e:
        raise ValueError(f"Error reading Excel file: {str(e)}")
    
    if not sheet_names:
        return []
    
    # Skip sheets that are likely lookup/reference data
    # These sheets typically have generic names and contain thousands of rows
    SKIP_SHEET_PATTERNS = ['datecode', 'sheet1', 'lookup', 'reference', 'master', 'database']
    MAX_SHEET_ROWS = 2000  # Skip sheets with more than this many rows (likely reference data)
    
    # Dictionary to store combined data by serial number
    combined_data: Dict[str, Dict[str, Any]] = {}
    
    # Process each sheet
    for sheet_name in sheet_names:
        try:
            # Check if sheet should be skipped based on name
            sheet_lower = sheet_name.lower().strip()
            if any(pattern in sheet_lower for pattern in SKIP_SHEET_PATTERNS):
                print(f"Skipping sheet '{sheet_name}': matches skip pattern")
                continue
            
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            if df.empty:
                continue
            
            # Skip sheets with excessive rows (likely reference/lookup data)
            if len(df) > MAX_SHEET_ROWS:
                print(f"Skipping sheet '{sheet_name}': too many rows ({len(df)} > {MAX_SHEET_ROWS})")
                continue
            
            # Detect serial number column for this sheet
            serial_column = SerialNumberDetector.detect_serial_column(df)
            
            if not serial_column:
                # Skip sheets without detectable serial numbers
                continue
            
            # Log detected column for debugging
            print(f"Sheet '{sheet_name}': Detected serial column = '{serial_column}', Rows = {len(df)}")
            
            # Try to detect error_type and status columns (optional)
            error_column = None
            status_column = None
            
            for col in df.columns:
                col_lower = col.lower().strip()
                if 'error' in col_lower or 'failure' in col_lower or 'issue' in col_lower or 'symptom' in col_lower:
                    error_column = col
                if 'status' in col_lower or 'state' in col_lower:
                    status_column = col
            
            # Process each row in this sheet
            for idx, row in df.iterrows():
                # Get serial number (required)
                serial_number = str(row[serial_column]).strip()
                
                # Skip rows with invalid serial numbers
                if not serial_number or serial_number.lower() in ['nan', 'none', '', 'null']:
                    continue
                
                # Initialize record for this serial number if it doesn't exist
                if serial_number not in combined_data:
                    combined_data[serial_number] = {
                        'serial_number': serial_number,
                        'error_type': None,
                        'status': None,
                        'source_filename': source_filename,
                        'raw_data': {
                            '_source_sheet': sheet_name,
                            '_source_row': int(idx) + 2,  # +2 because Excel is 1-indexed and has header
                            '_serial_column': serial_column
                        },
                        'sheets_found': [f"{sheet_name} (row {int(idx) + 2})"]
                    }
                else:
                    # If serial number already exists from another sheet, track it
                    combined_data[serial_number]['sheets_found'].append(f"{sheet_name} (row {int(idx) + 2})")
                
                # Update error_type and status if found and not already set
                if error_column and error_column in row:
                    error_value = clean_value(row[error_column])
                    if error_value and not combined_data[serial_number]['error_type']:
                        combined_data[serial_number]['error_type'] = str(error_value)
                
                if status_column and status_column in row:
                    status_value = clean_value(row[status_column])
                    if status_value and not combined_data[serial_number]['status']:
                        combined_data[serial_number]['status'] = str(status_value)
                
                # Merge raw_data from this sheet
                # Smart column merging: if column already exists, append sheet name suffix
                # Otherwise use original column name
                for col in df.columns:
                    value = clean_value(row[col])
                    # Skip None values
                    if value is None:
                        continue
                    
                    # Use original column name
                    col_name = col
                    
                    # If this column already exists with different value, add sheet suffix
                    if col_name in combined_data[serial_number]['raw_data']:
                        existing_value = combined_data[serial_number]['raw_data'][col_name]
                        # Only add suffix if values are different
                        if existing_value != value:
                            col_name = f"{col}_{sheet_name}"
                    
                    combined_data[serial_number]['raw_data'][col_name] = value
        
        except Exception as e:
            # Log warning but continue with other sheets
            print(f"Warning: Error processing sheet '{sheet_name}': {str(e)}")
            continue
    
    # Check if we found any data
    if not combined_data:
        raise ValueError(
            "Could not detect serial number columns in any sheet. "
            "Please ensure the file contains columns with serial numbers "
            "(headers like 'SN', 'Serial', 'PPID', '2d_barcode_sn', 'System SN', 'RMA#', etc.)"
        )
    
    # Log summary
    print(f"Parser summary: Found {len(combined_data)} unique serial numbers from {len(sheet_names)} sheet(s)")
    
    # Convert to list format and add sheet information to raw_data
    results = []
    for serial_number, record in combined_data.items():
        # Add metadata about sheets
        record['raw_data']['_sheets_combined'] = ', '.join(record['sheets_found'])
        record['raw_data']['_total_sheets'] = len(record['sheets_found'])
        
        # Remove the temporary sheets_found key
        del record['sheets_found']
        
        results.append(record)
    
    return results
