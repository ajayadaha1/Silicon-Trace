"""
Intelligent Excel parser for Silicon Trace.

This module implements heuristic-based column detection to identify serial numbers
in Excel files with inconsistent or varying column headers.

Now includes Nabu AI-powered column classification and data normalization.
"""

import re
import os
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
from column_classifier import ColumnClassifier, clean_error_type_with_nabu


# AMD CPU Serial Number Pattern Validator
# Pattern with anchors for exact validation - strict format
AMD_CPU_SERIAL_PATTERN = re.compile(r'^[0-9][A-Z0-9]{11}_\d{3}-\d{12}$')
# Pattern without anchors for searching within text - flexible to match variations
# Matches: [0-9]XXX... patterns (at least 9 alphanumeric chars after the first digit)
# Examples: 9MT8017P50008_100-000001463, 2ABS784R50042_100-000001359, 9AH0242W50010_100-000001
AMD_CPU_SERIAL_SEARCH_PATTERN = re.compile(r'[0-9][A-Z0-9]{9,}(?:_\d{3}(?:-\d{1,12})?)?')

def is_valid_amd_cpu_serial(serial: str) -> bool:
    """Validate if a string matches AMD CPU serial number format.
    
    Flexible format to handle variations:
    - Full: [0-9][A-Z0-9]{11}_[0-9]{3}-[0-9]{12}
    - Partial: [0-9][A-Z0-9]{9+} (at least 9 alphanumeric chars after the first digit)
    Examples: 9MT8017P50008_100-000001463, 2ABS784R50042_100-000001359, 9AH0242W50010_100-000001
    
    Returns:
        True if valid AMD CPU serial, False otherwise
    """
    if not serial or not isinstance(serial, str):
        return False
    serial = serial.strip()
    # Accept flexible AMD serial format: starts with digit, at least 9 more alphanumeric chars
    flexible_pattern = re.compile(r'^[0-9][A-Z0-9]{9,}')
    return flexible_pattern.match(serial) is not None

def is_legend_or_reference_row(serial: str) -> bool:
    """Check if a value looks like a legend/reference row rather than actual data.
    
    Legend rows contain: 'KEY', 'Label', 'Lo PROM', 'Hi PROM', 'Degradation', 'COV_', 'NFF', etc.
    These are Excel reference information for users, not actual failure data.
    """
    if not serial or not isinstance(serial, str):
        return False
    
    serial_lower = serial.lower().strip()
    legend_patterns = [
        'key', 'label', 'legend', 'reference', 'note', 'color',
        'prom', 'degradation', 'cov_', 'nff', 'esc',
        'description', 'definition', 'explanation'
    ]
    
    return any(pattern in serial_lower for pattern in legend_patterns)

def is_valid_customer_value(customer: str) -> bool:
    """Validate that a customer value is actually a customer name, not an error type or status.
    
    Filters out common non-customer values that appear in messy Customer columns.
    Returns True only for values that look like actual customer names.
    """
    if not customer or not isinstance(customer, str):
        return False
    
    customer = customer.strip()
    if not customer or len(customer) < 2:
        return False
    
    customer_upper = customer.upper()
    
    # Filter out common non-customer patterns
    non_customer_patterns = [
        # Status/tracking values
        'RMA', 'FA', 'NFF', 'TBD', 'TBC', 'N/A', 'NA', 'NONE', 'NULL', 'UNKNOWN',
        # Error types
        'ERR', 'ERROR', 'FAIL', 'PARITY', 'HANG', 'CRASH', 'WDT', 'TIMEOUT',
        'STRESS', 'ACF', 'CORR', 'UNCORR', 'ECC', 'MCE', 'WHEA',
        # Test stages
        'ATE', 'SLT', 'OSV', 'CESLT', 'L1', 'L2', 'FT1', 'FT2',
        # Common placeholder text
        'TEST', 'DEBUG', 'SAMPLE', 'INTERNAL', 'DEMO',
        # ODM/OEM names (these are manufacturers, not end customers)
        'HUAQIN', 'WISTRON', 'FOXCONN', 'QUANTA', 'COMPAL', 'INVENTEC', 
        'PEGATRON', 'FLEX', 'JABIL', 'CELESTICA', 'SUPER MICRO', 'SUPERMICRO',
        # AMD Platform/CPU names (these are product names, not customers)
        'TURIN', 'GENOA', 'BERGAMO', 'SIENA', 'MILAN', 'ROME', 'NAPLES',
        'EPYC', 'RYZEN', 'THREADRIPPER', 'ZEN',
    ]
    
    # Check if customer value contains any non-customer patterns
    for pattern in non_customer_patterns:
        if pattern in customer_upper:
            return False
    
    # Filter out values that are obviously error codes (e.g., "L2 TAG", "EX PARITY ERR")
    # Error codes typically have spaces with short words
    words = customer.split()
    if len(words) >= 2:
        # Check if it looks like an error code pattern
        short_words = [w for w in words if len(w) <= 3]
        if len(short_words) >= len(words) / 2:  # More than half are short words
            return False
    
    # Accept known good customer names (case-insensitive)
    known_customers = [
        'TENCENT', 'ALIBABA', 'UNIT', 'HUAWEI', 'BAIDU', 'BYTEDANCE',
        'MICROSOFT', 'GOOGLE', 'AMAZON', 'META', 'ORACLE', 'IBM',
        'DELL', 'HP', 'HPE', 'LENOVO', 'SUPERMICRO', 'CISCO'
    ]
    
    if any(known in customer_upper for known in known_customers):
        return True
    
    # For unknown values, accept if they look like reasonable company names
    # (alphanumeric, reasonable length, not all caps abbreviations)
    if 3 <= len(customer) <= 50:  # Reasonable company name length
        # Accept if it has some lowercase letters or is properly capitalized
        if customer != customer_upper or len(customer) > 6:
            return True
    
    return False

def _guess_value_type(value: str) -> str:
    """Guess what type of value this is for logging purposes."""
    if not value:
        return "empty"
    value_upper = str(value).upper()
    
    if any(pattern in value_upper for pattern in ['ERR', 'FAIL', 'PARITY', 'CRASH', 'HANG']):
        return "error type"
    if any(pattern in value_upper for pattern in ['RMA', 'FA', 'NFF']):
        return "status value"
    if any(pattern in value_upper for pattern in ['ATE', 'SLT', 'OSV', 'FT1', 'FT2']):
        return "test stage"
    return "unknown"

def extract_best_serial_from_text(text: str) -> Optional[str]:
    """Extract the best AMD CPU serial number from text that may contain multiple words.
    
    Uses a scoring system to find the word that best matches AMD serial pattern.
    Example: "9MP2379P50008_100-000001463 SLT coverage patch" -> "9MP2379P50008_100-000001463"
    
    Args:
        text: Text that may contain a serial number mixed with other words
        
    Returns:
        The best matching serial number, or None if no good match found
    """
    if not text or not isinstance(text, str):
        return None
    
    # Split by common delimiters (space, comma, semicolon, newline, tab)
    words = re.split(r'[\s,;\n\t]+', text.strip())
    
    best_word = None
    best_score = 0
    
    for word in words:
        if not word or len(word) < 10:  # Too short to be a serial
            continue
        
        score = 0
        
        # Scoring system:
        # 1. Starts with "9" (+30 points)
        if word.startswith('9'):
            score += 30
        
        # 2. Has underscore (+20 points)
        if '_' in word:
            score += 20
        
        # 3. Has dash (+10 points)
        if '-' in word:
            score += 10
        
        # 4. Length is reasonable (13-35 chars) (+10 points)
        if 13 <= len(word) <= 35:
            score += 10
        
        # 5. Mostly alphanumeric (+10 points)
        alnum_ratio = sum(c.isalnum() for c in word) / len(word)
        if alnum_ratio > 0.8:
            score += 10
        
        # 6. Matches flexible AMD pattern (+30 points)
        if AMD_CPU_SERIAL_SEARCH_PATTERN.search(word):
            score += 30
        
        if score > best_score:
            best_score = score
            best_word = word
    
    # Require minimum score of 40 to accept as serial
    if best_score >= 40:
        return best_word
    
    return None


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
    
    # Initialize column classifier for Nabu AI-powered classification
    classifier = ColumnClassifier()
    all_columns_across_sheets = set()
    sample_data = {}  # Store sample values for AI classification
    sheet_dataframes = {}  # Store DataFrames for second pass
    
    # First pass: Collect all columns from all sheets with sample data
    print("📊 First pass: Collecting columns from all sheets...")
    sample_rows = []  # Store complete rows that contain AMD CPU serials
    
    for sheet_name in sheet_names:
        try:
            # Quick skip check
            sheet_lower = sheet_name.lower().strip()
            if len(sheet_names) > 1 and any(pattern in sheet_lower for pattern in SKIP_SHEET_PATTERNS):
                continue
            
            # Read more rows to find rows with AMD CPU pattern
            df_peek = pd.read_excel(file_path, sheet_name=sheet_name, nrows=50)
            all_columns_across_sheets.update(df_peek.columns)
            
            print(f"  Reading sheet '{sheet_name}': {len(df_peek)} rows, {len(df_peek.columns)} columns")
            
            # Debug: Show first few values from Summary column to see what we're working with
            if 'Summary' in df_peek.columns:
                summary_samples = df_peek['Summary'].dropna().head(10).tolist()
                print(f"  📝 First 10 Summary values:")
                for i, val in enumerate(summary_samples[:5], 1):
                    val_str = str(val)[:150]
                    print(f"    {i}. '{val_str}'")
                    # Test pattern match
                    if AMD_CPU_SERIAL_SEARCH_PATTERN.search(str(val)):
                        print(f"       ✓ MATCHES AMD pattern!")
                    else:
                        print(f"       ✗ No match")
            
            # Collect complete rows that contain AMD CPU serial pattern
            # This gives AI full context to compare columns side-by-side
            for idx, row in df_peek.iterrows():
                # Check if ANY column in this row contains AMD CPU pattern
                row_dict = {}
                has_amd_pattern = False
                
                for col in df_peek.columns:
                    val = row[col]
                    if pd.notna(val):
                        val_str = str(val).strip()
                        row_dict[col] = val_str[:200]  # Limit length
                        
                        # Check if this value contains AMD CPU pattern (search anywhere in string)
                        if AMD_CPU_SERIAL_SEARCH_PATTERN.search(val_str):
                            has_amd_pattern = True
                            print(f"    ✓ Found AMD pattern in column '{col}': {val_str[:80]}...")
                
                # If this row contains AMD CPU pattern, add it as a sample
                if has_amd_pattern and len(sample_rows) < 5:
                    sample_rows.append(row_dict)
                    print(f"  ✓ Found sample row {len(sample_rows)} with AMD CPU pattern")
                
                # Stop once we have enough samples
                if len(sample_rows) >= 5:
                    break
            
            if len(sample_rows) >= 5:
                break
            
        except Exception as e:
            print(f"⚠ Warning: Could not peek at sheet '{sheet_name}': {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n📋 Sample row collection complete: Found {len(sample_rows)} rows with AMD CPU patterns")
    
    # Classify all columns using Nabu AI with complete sample rows
    print(f"🤖 Classifying {len(all_columns_across_sheets)} unique columns with Nabu AI...")
    print(f"   Sending {len(sample_rows)} complete sample rows containing AMD CPU serials")
    
    # Run async classification in a new thread to avoid event loop conflicts
    def run_async_classification():
        return asyncio.run(classifier.classify_columns(list(all_columns_across_sheets), sample_rows))
    
    with ThreadPoolExecutor() as executor:
        future = executor.submit(run_async_classification)
        classification_result = future.result()
    
    # Extract classifications and serial column from result
    column_classification = classification_result.get('classifications', {})
    ai_serial_column = classification_result.get('serial_number_column')
    ai_error_extraction_column = classification_result.get('error_extraction_column')
    
    print(f"\n✓ Column classification complete: {len(column_classification)} columns classified")
    print(f"\n🔍 DEBUG: AI Classification Results:")
    print(f"  - Total columns analyzed: {len(all_columns_across_sheets)}")
    print(f"  - Columns: {list(all_columns_across_sheets)}")
    print(f"  - Sent {len(sample_rows)} complete sample rows to AI")
    
    # Show first sample row (critical for debugging)
    if sample_rows:
        print(f"\n📋 Sample Row 1 Sent to AI:")
        for col, val in list(sample_rows[0].items()):
            display_val = val[:100] + '...' if len(val) > 100 else val
            print(f"  '{col}': '{display_val}'")
    
    if ai_serial_column:
        print(f"\n✓ AI identified serial number column: '{ai_serial_column}'")
    else:
        print(f"\n⚠ WARNING: AI did NOT identify a serial number column - will use fallback heuristic")
    
    if ai_error_extraction_column:
        print(f"✓ AI identified error extraction column: '{ai_error_extraction_column}'")
    
    # Show classification summary
    category_counts = {}
    for cat in column_classification.values():
        category_counts[cat] = category_counts.get(cat, 0) + 1
    print(f"\n📊 Category Distribution: {category_counts}")
    
    print(f"✓ Column classification complete: {len(column_classification)} columns classified")
    if ai_serial_column:
        print(f"✓ AI identified serial number column: '{ai_serial_column}'")
    if ai_error_extraction_column:
        print(f"✓ AI identified error extraction column: '{ai_error_extraction_column}'")
    
    # Dictionary to store combined data by serial number
    combined_data: Dict[str, Dict[str, Any]] = {}
    
    # Second pass: Process each sheet with classification
    print("📋 Second pass: Processing sheets with classification...")
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
            df_test = pd.read_excel(file_path, sheet_name=sheet_name, nrows=5, header=None)
            
            # Check if first few rows contain header-like data
            # Multi-row headers often have merged cells or repeated patterns
            header_rows = []
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
                                                         'tier', 'platform', 'mfg', 'afhc', 'ceslt', 'osv',
                                                         'diag', 'charz', 'repro', 'kvm']):
                            header_like_count += 1
                
                # If more than 30% of cells look like headers, this is a header row
                if header_like_count >= len(df_test.columns) * 0.3:
                    header_rows.append(row_idx)
            
            # Handle multi-row headers
            if len(header_rows) > 1:
                # Multi-row header detected - read ALL header rows and merge them
                # This handles cases where some columns (Customer, Serial) are in row 0
                # and tier columns (L1, L2, ATE) are in row 1
                print(f"Sheet '{sheet_name}': Detected multi-row header (rows {header_rows}), merging headers")
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_rows)
                
                # Flatten multi-index columns by combining ALL parts intelligently
                if isinstance(df.columns, pd.MultiIndex):
                    new_columns = []
                    for col_tuple in df.columns:
                        # Combine all non-null, non-"Unnamed" parts of the header
                        parts = []
                        for part in col_tuple:
                            part_str = str(part).strip()
                            if part_str and part_str.lower() != 'nan' and not part_str.startswith('Unnamed'):
                                parts.append(part_str)
                        
                        # Combine ALL meaningful parts with " - " separator to preserve tier hierarchy
                        # Example: ("Tier1 - ATE", "FT1") → "Tier1 - ATE - FT1"
                        # Example: ("Tier0 - Suzhou", "L1") → "Tier0 - Suzhou - L1"
                        if len(parts) >= 2:
                            # Multiple header levels - combine them all
                            combined = ' - '.join(parts)
                            new_columns.append(combined)
                        elif len(parts) == 1:
                            # Single meaningful part
                            new_columns.append(parts[0])
                        else:
                            # All parts were Unnamed or NaN - use original
                            new_columns.append('_'.join(str(p) for p in col_tuple))
                    
                    df.columns = new_columns
                    print(f"Sheet '{sheet_name}': Merged multi-row headers into {len(new_columns)} columns")
                    print(f"Sheet '{sheet_name}': Sample merged columns: {new_columns[:10]}")
            elif len(header_rows) == 1:
                print(f"Sheet '{sheet_name}': Detected single header at row {header_rows[0]}")
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_rows[0])
            else:
                # No header rows detected, assume row 0
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Log columns for debugging duplicate detection
            print(f"Sheet '{sheet_name}' columns: {list(df.columns)}")
            
            # Collect all unique columns across sheets for classification
            all_columns_across_sheets.update(df.columns)
            
            if df.empty:
                continue
            
            # Skip sheets with excessive rows (likely reference/lookup data)
            if len(df) > MAX_SHEET_ROWS:
                print(f"Skipping sheet '{sheet_name}': too many rows ({len(df)} > {MAX_SHEET_ROWS})")
                continue
            
            # Handle merged cells by forward-filling customer columns
            # Merged cells in Excel appear as NaN in all but the first row
            customer_keywords = ['customer', 'client', 'end_customer', 'end customer', 
                               'customer_name', 'customer name', '客户', 'cust']
            for col in df.columns:
                col_lower = col.lower().strip()
                if any(kw in col_lower for kw in customer_keywords):
                    # Forward fill the customer column to handle merged cells
                    df[col] = df[col].ffill()  # Use ffill() instead of deprecated fillna(method='ffill')
                    print(f"Forward-filled merged cells in customer column: '{col}'")
            
            # Detect or use AI-identified serial number column
            if ai_serial_column and ai_serial_column in df.columns:
                serial_column = ai_serial_column
                print(f"✓ Using AI-identified serial column: '{serial_column}'")
            else:
                # Fallback to heuristic detection if AI didn't identify one
                serial_column = SerialNumberDetector.detect_serial_column(df)
                if serial_column:
                    print(f"✓ Fallback heuristic detected serial column: '{serial_column}'")
            
            if not serial_column:
                # Skip sheets without detectable serial numbers
                continue
            
            # Log detected column for debugging
            print(f"Sheet '{sheet_name}': Detected serial column = '{serial_column}', Rows = {len(df)}")
            
            # Use classification to identify columns intelligently
            error_columns = []  # Can have multiple error-related columns
            status_column = None
            component_column = None
            tier_columns = []
            diagnostic_columns = []  # Separate diagnostic files from errors
            description_columns = []
            
            for col in df.columns:
                col_category = column_classification.get(col, "IGNORE")
                
                if col_category == "ERROR_TYPE":
                    error_columns.append(col)
                elif col_category == "STATUS":
                    if not status_column:  # Use first status column
                        status_column = col
                elif col_category == "TEST_TIER":
                    tier_columns.append(col)
                elif col_category == "DIAGNOSTIC":
                    diagnostic_columns.append(col)
                elif col_category == "DESCRIPTION":
                    description_columns.append(col)
                elif 'component' in col.lower() or 'part' in col.lower() or 'child' in col.lower():
                    component_column = col
            
            # Fallback if no error columns classified (backward compatibility)
            if not error_columns:
                for col in df.columns:
                    col_lower = col.lower().strip()
                    if 'error' in col_lower or 'failure' in col_lower or 'issue' in col_lower or 'symptom' in col_lower:
                        # But exclude diagnostic files
                        if not any(ext in col_lower for ext in ['dump', 'log', 'file', '.tar', '.gz']):
                            error_columns.append(col)
                            break
            
            # Process each row in this sheet
            for idx, row in df.iterrows():
                # Get serial number (required)
                raw_serial = str(row[serial_column]).strip()
                
                # Handle multi-line serial numbers (take only the first line)
                # Some Excel files have multiple serial numbers in one cell separated by newlines
                if '\n' in raw_serial:
                    raw_serial = raw_serial.split('\n')[0].strip()
                
                # Extract best serial from text using word-based scoring
                # This handles cases like "9MP2379P50008_100-000001463 SLT coverage patch"
                serial_number = extract_best_serial_from_text(raw_serial)
                
                if not serial_number:
                    # Fallback: try using the raw value if it looks like a serial
                    if raw_serial and is_valid_amd_cpu_serial(raw_serial):
                        serial_number = raw_serial
                
                # Extract error information from serial column if AI identified it for error extraction
                extracted_error = None
                if ai_error_extraction_column and serial_column == ai_error_extraction_column and serial_number:
                    # This column contains both serial numbers and error descriptions
                    # Remove the serial from the original text to get the error description
                    error_text = raw_serial.replace(serial_number, '').strip()
                    # Clean up error text
                    error_text = re.sub(r'^[,\s\-_:;]+', '', error_text)  # Remove leading punctuation
                    error_text = re.sub(r'[,\s\-_:;]+$', '', error_text)  # Remove trailing punctuation
                    if error_text and len(error_text) > 3:  # Meaningful error text
                        extracted_error = error_text
                        print(f"  Extracted error from serial column: '{error_text[:50]}...'")
                
                # Skip rows with invalid serial numbers
                if not serial_number or serial_number.lower() in ['nan', 'none', '', 'null', 'nat', 'n/a', 'na', 'tbd', 'tbc']:
                    continue
                
                # CRITICAL: Filter out legend/reference rows (Label KEY, Color KEY, etc.)
                if is_legend_or_reference_row(serial_number):
                    print(f"  Skipping legend/reference row: '{serial_number}'")
                    continue
                
                # CRITICAL: Validate AMD CPU serial number format
                # Only accept serials matching 9[A-Z0-9]{11}_[0-9]{3}-[0-9]{12}
                # This prevents FARM-3602, GOLD, etc. from being treated as serial numbers
                if not is_valid_amd_cpu_serial(serial_number):
                    print(f"  Skipping invalid serial format: '{serial_number}' (expected AMD CPU format: 9XXX...XXX_###-############)")
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
                        '_source_filename': source_filename,
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
                        'sheets_found': [f"{sheet_name} (row {int(idx) + 2})"],
                        '_error_sources': [],  # Track which columns contributed to error_type
                        '_diagnostic_info': {}  # Separate storage for diagnostic files
                    }
                else:
                    # If serial number already exists from another sheet, track it
                    combined_data[serial_number]['sheets_found'].append(f"{sheet_name} (row {int(idx) + 2})")
                    
                    # Update raw_data to reflect multiple source locations
                    # Keep first source as primary, but track all in _sheets_combined
                    if '_source_sheets_all' not in combined_data[serial_number]['raw_data']:
                        # First time seeing duplicate - preserve original source info
                        original_sheet = combined_data[serial_number]['raw_data']['_source_sheet']
                        original_row = combined_data[serial_number]['raw_data']['_source_row']
                        combined_data[serial_number]['raw_data']['_source_sheets_all'] = [
                            {"sheet": original_sheet, "row": original_row}
                        ]
                    # Add current location
                    combined_data[serial_number]['raw_data']['_source_sheets_all'].append({
                        "sheet": sheet_name,
                        "row": int(idx) + 2
                    })
                
                # Collect error_type from error columns (may have multiple)
                error_values = []
                
                # First, add extracted error from serial column if available
                if extracted_error:
                    error_values.append(extracted_error)
                    combined_data[serial_number]['_error_sources'].append(f"{serial_column} (extracted)")
                
                # Then collect from dedicated error columns
                for error_col in error_columns:
                    if error_col in row:
                        error_value = clean_value(row[error_col])
                        if error_value and str(error_value).lower() not in ['n/a', 'na', 'none', '']:
                            # Validate it's not a file path or URL
                            error_str = str(error_value)
                            if not any(ext in error_str.lower() for ext in ['.tar', '.gz', '.log', 'http://', 'https://']):
                                if len(error_str) < 100:  # Reasonable error description length
                                    error_values.append(error_str)
                                    combined_data[serial_number]['_error_sources'].append(error_col)
                
                # Set error_type (prefer first valid error, will clean with Nabu later)
                if error_values and not combined_data[serial_number]['error_type']:
                    combined_data[serial_number]['error_type'] = error_values[0]
                
                # Collect diagnostic info separately
                for diag_col in diagnostic_columns:
                    if diag_col in row:
                        diag_value = clean_value(row[diag_col])
                        if diag_value:
                            combined_data[serial_number]['_diagnostic_info'][diag_col] = str(diag_value)
                
                # If no error columns found, try tier test results as fallback
                if not error_values and tier_columns and not combined_data[serial_number]['error_type']:
                    # Check tier columns for failures
                    failed_tiers = []
                    for tier_col in tier_columns:
                        if tier_col in row:
                            value = clean_value(row[tier_col])
                            if value:
                                value_upper = str(value).upper().strip()
                                # Check if it's a failure (not PASS/NFF/NFT/NOT RUN/N/A)
                                if value_upper not in ['PASS', 'PASSED', 'NFF', 'NFT', 'NOT RUN', 'N/A', 'NA', '']:
                                    # It's a failure or uncertain result
                                    if not value_upper.startswith('NFF') and not value_upper.startswith('NFT'):
                                        failed_tiers.append(tier_col)
                    
                    if failed_tiers:
                        # Use the first failed tier as the error type
                        combined_data[serial_number]['error_type'] = f"Failed at: {failed_tiers[0]}"
                        combined_data[serial_number]['_error_sources'].append(f"tier:{failed_tiers[0]}")
                
                # Update status if found
                if status_column and status_column in row:
                    status_value = clean_value(row[status_column])
                    if status_value and not combined_data[serial_number]['status']:
                        combined_data[serial_number]['status'] = str(status_value)
                
                # If no traditional status column, infer status from tier results
                if not status_column and tier_columns and not combined_data[serial_number]['status']:
                    has_any_tier = False
                    has_failure = False
                    has_pass = False
                    
                    for tier_col in tier_columns:
                        if tier_col in row:
                            value = clean_value(row[tier_col])
                            if value:
                                has_any_tier = True
                                value_upper = str(value).upper().strip()
                                if value_upper in ['PASS', 'PASSED', 'NFF', 'NFT']:
                                    has_pass = True
                                elif value_upper not in ['NOT RUN', 'N/A', 'NA', '']:
                                    has_failure = True
                    
                    if has_any_tier:
                        if has_failure:
                            combined_data[serial_number]['status'] = 'Failed'
                        elif has_pass:
                            combined_data[serial_number]['status'] = 'Passed'
                        else:
                            combined_data[serial_number]['status'] = 'Not Run'
                
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
                        # Special validation for Customer columns
                        col_category = column_classification.get(col, "IGNORE")
                        if col_category == "CUSTOMER" and not is_valid_customer_value(value):
                            # Invalid customer value - skip it
                            print(f"  Skipping invalid customer value: '{value}' (looks like {_guess_value_type(value)})")
                            continue
                        
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
    
    # Post-process: Add metadata summary fields
    for serial_number, record in combined_data.items():
        raw_data = record['raw_data']
        
        # Add friendly summary of where this data came from
        raw_data['_sheets_combined'] = ', '.join(record['sheets_found'])
        raw_data['_total_sheets'] = len(record['sheets_found'])
    
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
    
    # Phase 3: Clean error_type values using Nabu AI
    print("🧹 Phase 3: Cleaning error_type values with Nabu AI...")
    nabu_client = None
    try:
        api_token = os.getenv('NABU_API_TOKEN')
        if api_token:
            from nabu_client import NabuClient
            nabu_client = NabuClient(api_token=api_token)
    except:
        pass
    
    cleaned_count = 0
    for serial_number, record in combined_data.items():
        if record['error_type']:
            original_error = record['error_type']
            
            # Clean the error type in a separate thread
            def run_async_cleaning():
                return asyncio.run(clean_error_type_with_nabu(original_error, nabu_client))
            
            with ThreadPoolExecutor() as executor:
                future = executor.submit(run_async_cleaning)
                cleaned_error = future.result()
            
            if cleaned_error != original_error:
                record['error_type'] = cleaned_error
                # Store original for reference
                record['raw_data']['_original_error_type'] = original_error
                cleaned_count += 1
    
    if cleaned_count > 0:
        print(f"✓ Cleaned {cleaned_count} error_type values")
    
    # Convert to list format and add metadata to raw_data
    results = []
    for serial_number, record in combined_data.items():
        # Add metadata about sheets
        record['raw_data']['_sheets_combined'] = ', '.join(record['sheets_found'])
        record['raw_data']['_total_sheets'] = len(record['sheets_found'])
        
        # Add column classification metadata
        record['raw_data']['_column_classification'] = column_classification
        
        # Store which columns were normalized
        if record.get('_error_sources'):
            record['raw_data']['_error_sources'] = record['_error_sources']
            del record['_error_sources']
        
        # Move diagnostic info to raw_data
        if record.get('_diagnostic_info'):
            record['raw_data']['_diagnostic_info'] = record['_diagnostic_info']
            del record['_diagnostic_info']
        
        # Remove the temporary sheets_found key
        del record['sheets_found']
        
        results.append(record)
    
    return results
