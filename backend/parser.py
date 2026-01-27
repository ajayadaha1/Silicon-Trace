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
        Higher priority keywords (earlier in list) get higher scores.
        
        Args:
            column_name: The column header to score
            
        Returns:
            Float score (0.0 to 1.0+), higher is better
        """
        if not isinstance(column_name, str):
            return 0.0
            
        col_lower = column_name.lower().strip()
        
        # Check for exact matches - prioritize by position in list
        # CPU_SN gets highest score (1.5), others decrease gradually
        for idx, keyword in enumerate(cls.HEADER_KEYWORDS):
            if col_lower == keyword:
                # First 3 keywords (cpu_sn variants) get bonus score > 1.0
                if idx < 3:
                    return 1.5
                # Next 3 keywords (2d_barcode) get 1.3
                elif idx < 6:
                    return 1.3
                # Everything else gets 1.0
                else:
                    return 1.0
        
        # Partial match - check if any keyword is contained in the column name
        max_score = 0.0
        for idx, keyword in enumerate(cls.HEADER_KEYWORDS):
            if keyword in col_lower:
                # Score based on how much of the column name is the keyword
                # Longer matches relative to column name get higher scores
                score = len(keyword) / len(col_lower)
                # Apply priority bonus for top keywords
                if idx < 3:
                    score *= 1.2
                elif idx < 6:
                    score *= 1.1
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
            
            # Handle multi-line values by taking only the first line
            # This handles cases like "9AMH711Q50057_100-000001359\nDue 9/18"
            if '\n' in str_value:
                str_value = str_value.split('\n')[0].strip()
            
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
        1. Check for high-priority columns (CPU_SN, 2d_barcode_sn) first
        2. If found with good data patterns, use them immediately
        3. Otherwise, score all columns and pick the best
        
        Args:
            df: Pandas DataFrame to analyze
            
        Returns:
            Column name containing serial numbers, or None if no good candidate found
        """
        if df.empty:
            return None
        
        # Priority keywords that should be preferred (case-insensitive)
        priority_keywords = ['cpu_sn', 'cpu sn', 'cpusn', '2d_barcode_sn', '2d_barcode', '2d barcode']
        
        # First pass: Check for priority columns
        for column in df.columns:
            col_lower = column.lower().strip()
            if col_lower in priority_keywords:
                # Check if this column has reasonable data patterns
                data_score = cls.score_column_data(df[column])
                if data_score >= 0.3:  # Reasonable threshold
                    return column
        
        # Second pass: Score all columns if no priority match found
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


def normalize_column_name(column_name: str) -> str:
    """
    Normalize column names to handle case sensitivity and extra spaces.
    This ensures columns like ' FA status ', 'FA status', 'fa status' 
    are all treated as the same column.
    
    Args:
        column_name: Original column name from Excel
        
    Returns:
        Normalized column name (lowercase, trimmed, single spaces)
    """
    if not isinstance(column_name, str):
        return str(column_name)
    
    # Convert to lowercase, strip leading/trailing spaces
    normalized = column_name.strip().lower()
    
    # Replace multiple spaces with single space
    normalized = ' '.join(normalized.split())
    
    return normalized


def extract_customer_from_filename(filename: str) -> Optional[str]:
    """
    Extract customer name from filename.
    Examples:
    - "Tencent DPPM Summary Tracker_CQE update_ww52.xlsx" -> "Tencent"
    - "Alibaba_FA_Status.xlsx" -> "Alibaba"
    - "Turin-Dense_AlibabaTencent_FA_Status0123.pptx" -> "Alibaba Tencent"
    
    Args:
        filename: Original filename
        
    Returns:
        Customer name or None if not found
    """
    if not filename:
        return None
    
    # Common customer names (add more as needed)
    known_customers = ['Tencent', 'Alibaba', 'Meta', 'Google', 'Microsoft', 'Amazon', 
                      'Facebook', 'ByteDance', 'Baidu', 'Huawei', 'Intel', 'AMD']
    
    # Check for known customer names in filename
    filename_upper = filename.upper()
    found_customers = []
    
    for customer in known_customers:
        if customer.upper() in filename_upper:
            found_customers.append(customer)
    
    if found_customers:
        return ' '.join(found_customers)
    
    # Fallback: Extract first word before common separators
    # e.g., "CustomerName_Report.xlsx" -> "CustomerName"
    import re
    match = re.match(r'^([A-Za-z]+)[\s_\-]', filename)
    if match:
        first_word = match.group(1)
        # Avoid common generic words
        if first_word.lower() not in ['summary', 'tracker', 'report', 'status', 'data', 'fa', 'dppm']:
            return first_word
    
    return None


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
    
    # Extract customer name from filename
    customer_from_filename = extract_customer_from_filename(source_filename)
    if customer_from_filename:
        print(f"Extracted customer from filename: '{customer_from_filename}' from '{source_filename}'")
    
    # Read ALL sheets from the Excel file
    try:
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
    except Exception as e:
        raise ValueError(f"Error reading Excel file: {str(e)}")
    
    if not sheet_names:
        return []
    
    # Skip sheets that are likely lookup/reference data
    # Only skip if there's more than one sheet and this sheet has a generic name
    # Don't skip if it's the only sheet (likely contains the actual data)
    SKIP_SHEET_PATTERNS = ['datecode', 'lookup', 'reference', 'master', 'database', 'template']
    MAX_SHEET_ROWS = 2000  # Skip sheets with more than this many rows (likely reference data)
    
    # Dictionary to store combined data by serial number
    combined_data: Dict[str, Dict[str, Any]] = {}
    
    # Process each sheet
    for sheet_name in sheet_names:
        try:
            # Check if sheet should be skipped based on name
            # Only skip generic names if there are multiple sheets
            sheet_lower = sheet_name.lower().strip()
            should_skip = False
            
            if len(sheet_names) > 1:
                # If multiple sheets, skip generic names
                if any(pattern in sheet_lower for pattern in SKIP_SHEET_PATTERNS):
                    print(f"Skipping sheet '{sheet_name}': matches skip pattern (multiple sheets present)")
                    should_skip = True
            
            if should_skip:
                continue
            
            # Read with no duplicate column handling - we'll merge them ourselves
            # First, try to detect multi-row headers
            df_test = pd.read_excel(file_path, sheet_name=sheet_name, nrows=5)
            
            # Check if first few rows contain header-like data
            # Multi-row headers often have merged cells or repeated patterns
            header_row = 0
            for row_idx in range(min(4, len(df_test))):
                row_data = df_test.iloc[row_idx]
                # Count how many values look like headers (contain common keywords)
                header_like_count = 0
                for val in row_data:
                    if pd.notna(val):
                        val_str = str(val).lower()
                        # Check for header keywords
                        if any(kw in val_str for kw in ['serial', 'sn', 'number', 'customer', 'date', 
                                                         'status', 'error', 'failure', 'ticket', 'priority',
                                                         'bios', 'wafer', 'faili', 'ccd', 'ttf', 'ate', 'slt',
                                                         'platform', 'mfg']):
                            header_like_count += 1
                
                # If more than 30% of cells look like headers, this might be the real header row
                if header_like_count >= len(df_test.columns) * 0.3:
                    header_row = row_idx
                    break
            
            # Re-read with correct header row
            if header_row > 0:
                print(f"Sheet '{sheet_name}': Detected multi-row header at row {header_row}")
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Log columns for debugging duplicate detection
            print(f"Sheet '{sheet_name}' columns: {list(df.columns)}")
            
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
            
            # Try to detect error_type, status, and component columns (optional)
            error_column = None
            status_column = None
            component_column = None
            
            for col in df.columns:
                col_lower = col.lower().strip()
                if 'error' in col_lower or 'failure' in col_lower or 'issue' in col_lower or 'symptom' in col_lower:
                    error_column = col
                if 'status' in col_lower or 'state' in col_lower:
                    status_column = col
                if 'component' in col_lower or 'part' in col_lower or 'child' in col_lower:
                    component_column = col
            
            # Process each row in this sheet
            for idx, row in df.iterrows():
                # Get serial number (required)
                serial_number = str(row[serial_column]).strip()
                
                # Skip rows with invalid serial numbers
                if not serial_number or serial_number.lower() in ['nan', 'none', '', 'null', 'nat', 'n/a', 'na', 'tbd', 'tbc']:
                    continue
                
                # Skip header rows that appear as data (common in messy Excel files)
                # Check if the value looks like a column header
                sn_lower = serial_number.lower().replace(' ', '').replace('_', '')
                header_patterns = ['cpusn', 'cpu0sn', 'cpu1sn', 'serialnumber', 'serial', 
                                  'barcode', 'ppid', 'systemsn', 'rma', 'assetid']
                if any(pattern in sn_lower for pattern in header_patterns) and len(serial_number) < 20:
                    continue
                
                # Initialize record for this serial number if it doesn't exist
                if serial_number not in combined_data:
                    raw_data_init = {
                        '_source_sheet': sheet_name,
                        '_source_row': int(idx) + 2,  # +2 because Excel is 1-indexed and has header
                        '_serial_column': serial_column
                    }
                    
                    # Add customer from filename as fallback (only if no customer column exists)
                    # This will be used if the data doesn't have a customer column
                    # If a customer column exists, it will overwrite this in later processing
                    if customer_from_filename:
                        raw_data_init['_customer_from_filename'] = customer_from_filename
                    
                    combined_data[serial_number] = {
                        'serial_number': serial_number,
                        'error_type': None,
                        'status': None,
                        'source_filename': source_filename,
                        'raw_data': raw_data_init,
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
                # Smart column merging: normalize column names to handle case/space differences
                for col in df.columns:
                    value = clean_value(row[col])
                    # Skip None values
                    if value is None:
                        continue
                    
                    # Normalize column name (handles ' FA status ', 'FA status', etc.)
                    normalized_col = normalize_column_name(col)
                    
                    # Check if this normalized column already exists
                    existing_key = None
                    for existing_col in combined_data[serial_number]['raw_data'].keys():
                        if not existing_col.startswith('_'):  # Skip metadata fields
                            if normalize_column_name(existing_col) == normalized_col:
                                existing_key = existing_col
                                break
                    
                    if existing_key:
                        # Column already exists - check if values are different
                        existing_value = combined_data[serial_number]['raw_data'][existing_key]
                        if existing_value != value:
                            # Different value - concatenate with separator
                            # This preserves data from duplicate columns
                            combined_data[serial_number]['raw_data'][existing_key] = f"{existing_value} | {value}"
                        # else: Same value - skip (don't duplicate)
                    else:
                        # New column - use original column name (preserves original casing/spacing)
                        combined_data[serial_number]['raw_data'][col] = value
        
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
    
    # Post-process: Apply customer from filename if no Customer column found in data
    for serial_number, record in combined_data.items():
        raw_data = record['raw_data']
        
        # If we have a filename customer but no actual Customer column in the data, use it
        if '_customer_from_filename' in raw_data:
            # Check if any actual customer column exists
            has_customer_column = any(
                'customer' in normalize_column_name(k).lower() 
                for k in raw_data.keys() 
                if not k.startswith('_')
            )
            
            if not has_customer_column:
                # No customer column found, use filename customer
                raw_data['Customer'] = raw_data['_customer_from_filename']
            
            # Remove the temporary field
            del raw_data['_customer_from_filename']
    
    # Log summary
    print(f"Parser summary: Found {len(combined_data)} unique serial numbers from {len(sheet_names)} sheet(s)")
    
    # Post-process: Handle component-to-parent relationships
    # Identify which serial numbers are actually components of other systems
    component_serials = set()
    parent_map = {}  # Maps component SN to list of parent SNs
    
    for serial_number, record in combined_data.items():
        raw_data = record['raw_data']
        
        # Check if this record has a Component field with parent serial numbers
        component_field = None
        for key in raw_data.keys():
            if not key.startswith('_') and 'component' in key.lower():
                component_field = key
                break
        
        if component_field and raw_data[component_field]:
            component_value = str(raw_data[component_field])
            # Parse component field for serial numbers (split by /, comma, etc.)
            import re
            # Extract potential serial numbers (alphanumeric with underscores/dashes)
            potential_parents = re.findall(r'[A-Za-z0-9_\-]{8,}', component_value)
            
            # Check if any of these potential parents exist in our combined_data
            for potential_parent in potential_parents:
                if potential_parent in combined_data and potential_parent != serial_number:
                    # This serial_number is a component of potential_parent
                    if serial_number not in parent_map:
                        parent_map[serial_number] = []
                    parent_map[serial_number].append(potential_parent)
                    component_serials.add(serial_number)
    
    # Redistribute component data to parent systems
    components_redistributed = 0
    for component_sn, parent_sns in parent_map.items():
        if component_sn in combined_data:
            component_record = combined_data[component_sn]
            components_redistributed += 1
            
            print(f"Redistributing component {component_sn} to parents: {', '.join(parent_sns)}")
            
            # Add component data to each parent system
            for parent_sn in parent_sns:
                if parent_sn in combined_data:
                    parent_record = combined_data[parent_sn]
                    
                    # Add component info as a special field
                    if '_components' not in parent_record['raw_data']:
                        parent_record['raw_data']['_components'] = []
                    
                    parent_record['raw_data']['_components'].append({
                        'component_sn': component_sn,
                        'component_data': component_record['raw_data']
                    })
            
            # Remove the component from combined_data (it's not a standalone asset)
            del combined_data[component_sn]
    
    if components_redistributed > 0:
        print(f"✓ Component redistribution: {components_redistributed} component serial numbers moved to parent systems")
        print(f"Final asset count: {len(combined_data)} (after removing components)")
    
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
