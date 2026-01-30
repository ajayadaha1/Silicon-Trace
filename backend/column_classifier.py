"""
Column Classifier using Nabu AI

This module uses AMD Nabu AI to intelligently classify Excel columns into categories,
enabling better data organization and normalization.
"""

import asyncio
from typing import Dict, List, Any, Optional
from nabu_client import NabuClient
import os


class ColumnClassifier:
    """
    Classifies Excel column headers into semantic categories using Nabu AI.
    
    Categories:
    - SERIAL_NUMBER: Serial number identifiers
    - ERROR_TYPE: Error, failure, symptom descriptions
    - STATUS: Status, state, resolution progress
    - TEST_TIER: Test stage columns (L1, L2, ATE, SLT, etc.)
    - DATE: Dates and timestamps
    - CUSTOMER: Customer information
    - PLATFORM: Platform, BIOS, hardware info
    - DIAGNOSTIC: Log files, dumps, debug info
    - DESCRIPTION: Comments, notes, observations
    - IGNORE: Irrelevant or duplicate columns
    """
    
    CATEGORIES = [
        "SERIAL_NUMBER",
        "ERROR_TYPE",
        "STATUS",
        "TEST_TIER",
        "DATE",
        "CUSTOMER",
        "PLATFORM",
        "DIAGNOSTIC",
        "DESCRIPTION",
        "IGNORE"
    ]
    
    def __init__(self):
        """Initialize the classifier with Nabu client."""
        api_token = os.getenv('NABU_API_TOKEN')
        if not api_token:
            print("Warning: NABU_API_TOKEN not set. Column classification will use fallback logic.")
            self.nabu_client = None
        else:
            self.nabu_client = NabuClient(api_token=api_token)
    
    async def classify_columns(self, columns: List[str], sample_data: Optional[Dict[str, List[Any]]] = None) -> Dict[str, Any]:
        """
        Classify a list of column headers using Nabu AI and detect serial number column.
        
        Args:
            columns: List of column header names from Excel
            sample_data: Optional dict mapping column names to first 3-5 sample values
            
        Returns:
            Dictionary with:
            - 'classifications': Dict mapping column names to categories
            - 'serial_number_column': Name of the column containing serial numbers
            - 'error_extraction_column': Column to extract error info from (if different from main error column)
            Example: {
                "classifications": {"CPU_SN": "SERIAL_NUMBER", "错误类型": "ERROR_TYPE"},
                "serial_number_column": "Summary",
                "error_extraction_column": "Summary"
            }
        """
        if not columns:
            return {"classifications": {}, "serial_number_column": None, "error_extraction_column": None}
        
        # If Nabu not available, use fallback
        if not self.nabu_client:
            fallback = self._fallback_classification(columns)
            return {
                "classifications": fallback,
                "serial_number_column": None,
                "error_extraction_column": None
            }
        
        # Prepare prompt for Nabu
        prompt = self._build_classification_prompt(columns, sample_data)
        
        try:
            # Call Nabu AI for classification
            print(f"\n🤖 Sending to Nabu AI:")
            print(f"  - Columns to classify: {len(columns)}")
            # Handle both old dict format and new list format
            if isinstance(sample_data, list):
                print(f"  - Sample data provided: {len(sample_data)} complete rows")
            elif isinstance(sample_data, dict):
                print(f"  - Sample data provided: {len(sample_data)} columns")
            else:
                print(f"  - Sample data provided: 0")
            
            if sample_data and isinstance(sample_data, list) and len(sample_data) > 0:
                # Show first sample row
                first_row = sample_data[0]
                print(f"  - First sample row has {len(first_row)} columns")
            
            response_dict = await self.nabu_client.chat(
                user_prompt=prompt,
                history=[]
            )
            
            # Extract text response from dict
            # Nabu returns response in 'responseText' field
            response_text = response_dict.get('responseText', '') if isinstance(response_dict, dict) else str(response_dict)
            
            print(f"\n📥 Nabu AI Response (first 500 chars):")
            print(f"{response_text[:500]}...")
            
            # Parse Nabu's response to extract classifications and serial column
            result = self._parse_nabu_response(response_text, columns)
            
            print(f"\n✅ Nabu Classification Results:")
            print(f"  ✓ Classified {len(result['classifications'])} columns")
            if result['serial_number_column']:
                print(f"  ✓ Serial column identified: '{result['serial_number_column']}'")
            else:
                print(f"  ⚠ No serial column identified by AI")
            if result['error_extraction_column']:
                print(f"  ✓ Error extraction column: '{result['error_extraction_column']}'")
            
            return result
            
        except Exception as e:
            print(f"Warning: Nabu classification failed: {str(e)}. Using fallback.")
            fallback = self._fallback_classification(columns)
            return {
                "classifications": fallback,
                "serial_number_column": None,
                "error_extraction_column": None
            }
    
    def _build_classification_prompt(self, columns: List[str], sample_data: Optional[Any] = None) -> str:
        """Build the prompt for Nabu AI column classification and serial number detection.
        
        Args:
            columns: List of column names
            sample_data: Either Dict[str, List] (old format) or List[Dict] (new format of complete rows)
        """
        
        column_list = "\n".join([f"{i+1}. {col}" for i, col in enumerate(columns)])
        
        # Add sample data - handle both old format (per-column) and new format (complete rows)
        sample_section = ""
        if sample_data:
            if isinstance(sample_data, list) and len(sample_data) > 0 and isinstance(sample_data[0], dict):
                # New format: List of complete row dictionaries
                sample_section = "\n\n**COMPLETE SAMPLE ROWS** (showing all columns side-by-side):\n"
                sample_section += "This is REAL data from the file. Compare columns to find AMD CPU serials.\n\n"
                
                for idx, row_dict in enumerate(sample_data[:3], 1):  # Show up to 3 complete rows
                    sample_section += f"Row {idx}:\n"
                    for col, val in row_dict.items():
                        display_val = str(val)[:150]
                        sample_section += f"  {col}: {display_val}\n"
                    sample_section += "\n"
            else:
                # Old format: Dict mapping column names to sample values
                sample_section = "\n\nSample data from columns:\n"
                sample_items = list(sample_data.items())[:10] if isinstance(sample_data, dict) else []
                for col, values in sample_items:
                    sample_values = [str(v)[:100] for v in (values[:3] if isinstance(values, list) else [values]) if v]
                    if sample_values:
                        sample_section += f"  {col}: {', '.join(sample_values)}\n"
        
        prompt = f"""You are an expert data analyst classifying hardware failure tracking columns.

Classify each of these Excel column headers into ONE category:

Categories:
- SERIAL_NUMBER: Serial numbers, barcodes, asset IDs, PPID, CPU_SN, 2D_barcode, System SN
- ERROR_TYPE: Error types, failures, symptoms, issues, fault codes (错误类型, Failtype, Error, Symptom)
  ⚠️ IMPORTANT: If column contains "date" or "time", classify as DATE, NOT ERROR_TYPE (e.g., "Fail Date" → DATE)
  ⚠️ IMPORTANT: Columns about failure location (failed core, failed CCD, failed die, failed DIMM) → DESCRIPTION, NOT ERROR_TYPE
- STATUS: Status, state, resolution progress, FA status, RMA status (状态, FA状态)
- TEST_TIER: Test stage names (L1, L2, ATE, SLT, CESLT, OSV, AFHC, FT1, FT2, Tier0-5, Stage, Phase)
  ⚠️ IMPORTANT: "Stage" columns (e.g., "Online Fail", "IDC Acceptance") are TEST_TIER, NOT CUSTOMER
- DATE: Dates, timestamps, date codes (日期, Fail Date, Deploy Date, Test Date)
  ⚠️ PRIORITY: Any column with "date" or "time" in name should be classified as DATE
- CUSTOMER: Customer names, client info (客户, Customer, Client, end_customer, ODM - but NOT stage/phase values)
  ⚠️ IMPORTANT: Column name must indicate customer identity, not test stage or location
- PLATFORM: Platform, BIOS, firmware versions, hardware config
- DIAGNOSTIC: Log files, dump files, diagnostic paths, URLs, AFHC logs
- DESCRIPTION: Comments, notes, observations, debug notes, summaries, failure location details (failed core/CCD/die)
- IGNORE: Irrelevant, empty, or redundant columns (Location, Site, numeric IDs, etc.)

Column headers to classify:
{column_list}{sample_section}

**CRITICAL TASK: Identify the Serial Number Column**

**A good AMD CPU serial number looks like this:**
`9MP2379P50008_100-000001463`

Pattern characteristics:
- Starts with "9"
- Followed by 11+ alphanumeric characters
- May have underscore and numbers (e.g., _100-000001463)
- Examples: 9MT8017P50008_100-000001463, 9AH0242W50010_100-000001, 9AR0841T50008

IMPORTANT: Look at the sample rows above. The serial number might be:
- In a dedicated column (like "PPID" or "CPU_SN")
- Mixed with other text in a column like "Summary" (e.g., "9MP2379P50008_100-000001463 SLT coverage patch")

**Compare ALL columns in the sample rows:**
- Which column has values that START with "9" followed by many alphanumeric characters?
- Which column has values like "FARM-####" or "GOLD" (NOT serials - these are tracking IDs)?
- The serial column might contain multiple words - look for the word that matches the pattern above

**The column with AMD CPU serials is the SERIAL_NUMBER column, not FARM/tracking IDs!**

**SECONDARY TASK: Error Extraction**
If the serial number column ALSO contains error descriptions (e.g., "9AMP...463 Bios x225 then fail"), identify this column for error extraction.

Respond with a JSON object containing:
1. "classifications": mapping each column to its category
2. "serial_number_column": the EXACT column name that contains AMD CPU serial numbers (null if none found)
3. "error_extraction_column": the column name to extract error descriptions from (null if none, can be same as serial_number_column)

{{
  "classifications": {{
    "column_name": "CATEGORY",
    ...
  }},
  "serial_number_column": "Summary",
  "error_extraction_column": "Summary"
}}

Be intelligent about:
- **FAILURE LOCATION vs ERROR TYPE**: Columns about WHERE the failure occurred (failed core, failed CCD, failed die, failed DIMM, core#, socket#) → DESCRIPTION, not ERROR_TYPE
- **STAGE/PHASE PRIORITY**: Columns named "Stage", "Phase", or containing test stage values (e.g., "Online Fail", "IDC Acceptance") are TEST_TIER, NEVER CUSTOMER
- **DATE PRIORITY**: Columns with "date", "time", or "timestamp" are ALWAYS DATE category, even if they also contain "fail", "error", etc.
  - "Fail Date" → DATE (not ERROR_TYPE)
  - "Deploy Date" → DATE (not STATUS)
  - "Test Time" → DATE (not TEST_TIER)
- **ODM vs CUSTOMER**: "odm" column (Original Design Manufacturer) → CUSTOMER only if it contains company names, not stage/tier values
- Bilingual support (Chinese: 错误类型=ERROR_TYPE, 客户=CUSTOMER, 状态=STATUS, 日期=DATE)
- File references (dump_file, log_path, *.tar.gz) = DIAGNOSTIC
- URLs (SharePoint, http://) = DIAGNOSTIC
- Test tiers (L1, L2, ATE case-insensitive) = TEST_TIER
- Synonyms (Error/Failure/Issue/Symptom all = ERROR_TYPE, but NOT if combined with location words like "core", "CCD", "die")
- **Serial numbers can be in ANY column, not just ones named "Serial" or "SN"**
- **Look at the ACTUAL DATA in sample rows, not just column names!**
"""
        
        return prompt
    
    def _parse_nabu_response(self, response: str, columns: List[str]) -> Dict[str, Any]:
        """Parse Nabu's response to extract column classifications and serial number column."""
        import json
        import re
        
        result = {
            "classifications": {},
            "serial_number_column": None,
            "error_extraction_column": None
        }
        
        # Try to extract JSON from response
        try:
            # Look for JSON object in response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                nabu_result = json.loads(json_str)
                
                # Extract classifications
                classifications = nabu_result.get('classifications', nabu_result)
                
                # Validate categories
                validated = {}
                for col, category in classifications.items():
                    if col in ['serial_number_column', 'error_extraction_column']:
                        continue  # Skip metadata fields
                    if category.upper() in self.CATEGORIES:
                        validated[col] = category.upper()
                    else:
                        # Invalid category, use fallback for this column
                        validated[col] = self._classify_single_column(col)
                
                result["classifications"] = validated
                result["serial_number_column"] = nabu_result.get('serial_number_column')
                result["error_extraction_column"] = nabu_result.get('error_extraction_column')
                
                return result
        except Exception as e:
            print(f"Warning: Failed to parse Nabu response: {str(e)}")
        
        # If parsing failed, use fallback
        result["classifications"] = self._fallback_classification(columns)
        return result
    
    def _fallback_classification(self, columns: List[str]) -> Dict[str, str]:
        """Fallback classification using keyword matching."""
        classification = {}
        
        for col in columns:
            classification[col] = self._classify_single_column(col)
        
        return classification
    
    def _classify_single_column(self, column: str) -> str:
        """Classify a single column using keyword matching (fallback logic)."""
        col_lower = column.lower().strip()
        
        # Serial number indicators
        if any(kw in col_lower for kw in ['cpu_sn', 'cpu sn', 'cpusn', '2d_barcode', 'serial', 
                                           'sn', 'barcode', 'ppid', 'system_sn', 'rma#', 'asset']):
            return "SERIAL_NUMBER"
        
        # Date indicators (CHECK FIRST to avoid "Fail Date" being classified as ERROR_TYPE)
        if any(kw in col_lower for kw in ['date', 'time', '日期', 'timestamp', 'datecode']):
            return "DATE"
        
        # Test tier indicators (CHECK EARLY to prevent "Stage" from being classified as CUSTOMER)
        if any(kw in col_lower for kw in ['stage', 'l1', 'l2', 'l3', 'ate', 'slt', 'ceslt', 'osv', 
                                           'afhc', 'ft1', 'ft2', 'fs1', 'fs2', 'tier', 'phase']):
            return "TEST_TIER"
        
        # Error type indicators (now won't match "Fail Date" since dates are already handled)
        if any(kw in col_lower for kw in ['error', 'fail', 'symptom', 'issue', 'problem', 
                                           '错误', '故障', 'fault', 'failtype', 'failure']):
            # Exclude columns that are about failure location/context, not error types
            if any(kw in col_lower for kw in ['core', 'ccd', 'socket', 'die', 'dimm', 'channel', 'rank']):
                return "DESCRIPTION"  # Failed core/CCD location, not error type
            # Check if it's a diagnostic file
            if any(kw in col_lower for kw in ['dump', 'log', 'file', 'path', '.tar', '.gz', 'afhc']):
                return "DIAGNOSTIC"
            return "ERROR_TYPE"
        
        # Status indicators
        if any(kw in col_lower for kw in ['status', 'state', '状态', 'fa_status', 'fa status', 
                                           'rma status', 'resolution']):
            return "STATUS"
        
        # Customer indicators
        if any(kw in col_lower for kw in ['customer', 'client', '客户', 'cust', 'end_customer']):
            return "CUSTOMER"
        
        # Platform indicators
        if any(kw in col_lower for kw in ['platform', 'bios', 'firmware', 'version', 'hardware', 
                                           'config', 'cpu', 'dimm']):
            return "PLATFORM"
        
        # Diagnostic indicators (files, logs, URLs)
        if any(kw in col_lower for kw in ['dump', 'log', 'file', 'path', 'url', 'link', 
                                           'sharepoint', 'http', '.tar', '.gz', 'afhc', 
                                           'diagnostic']):
            return "DIAGNOSTIC"
        
        # Description indicators
        if any(kw in col_lower for kw in ['comment', 'note', 'description', 'summary', 
                                           'observation', 'debug', 'remark']):
            return "DESCRIPTION"
        
        # Default to IGNORE if no clear category
        return "IGNORE"


async def clean_error_type_with_nabu(error_value: str, nabu_client: Optional[NabuClient] = None) -> str:
    """
    Clean and normalize an error_type value using Nabu AI.
    
    Handles cases where error_type contains:
    - File names (dump_*.tar.gz)
    - URLs (SharePoint links)
    - Messy formats (OS crash ( ACF ))
    
    Args:
        error_value: Raw error value from Excel
        nabu_client: Optional NabuClient instance (creates new if None)
        
    Returns:
        Cleaned, normalized error type
    """
    if not error_value or error_value.lower() in ['n/a', 'na', 'none', 'unknown', '']:
        return "Unknown"
    
    # Quick check if it looks clean already
    if len(error_value) < 50 and not any(ext in error_value.lower() for ext in ['.tar', '.gz', '.log', 'http', '://']):
        # Already looks clean, just do basic cleanup
        cleaned = error_value.strip()
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        return cleaned
    
    # If no Nabu client provided, try to create one
    if not nabu_client:
        api_token = os.getenv('NABU_API_TOKEN')
        if not api_token:
            return _fallback_error_cleaning(error_value)
        nabu_client = NabuClient(api_token=api_token)
    
    # Use Nabu AI to clean the error
    prompt = f"""Clean this hardware error type value. It's supposed to describe a hardware failure, but got corrupted data.

Raw value: "{error_value}"

Rules:
- If it's a file name (*.tar.gz, *.log, dump_*) → extract the actual error type or use generic name
  - dump_*.tar.gz → "System Dump" or "OS Crash"
  - afhc_log*.tar → "AFHC Error"
  - *mce*.log → "Machine Check Exception"
- If it's a URL (SharePoint, http) → extract document type or use "Diagnostic Link"
- If it contains error code in parentheses like "OS crash ( ACF )" → keep the code: "ACF"
- Remove file extensions (.tar, .gz, .log, .txt)
- Standardize format: max 50 characters, capitalize properly
- If completely unclear → "Diagnostic Required"

Respond with ONLY the cleaned error type (no explanation):
"""
    
    try:
        response_dict = await nabu_client.chat(user_prompt=prompt, history=[])
        
        # Extract text response from dict
        response_text = response_dict.get('response', '') if isinstance(response_dict, dict) else str(response_dict)
        
        # Extract cleaned value from response
        cleaned = response_text.strip()
        
        # Remove quotes if Nabu added them
        cleaned = cleaned.strip('"\'')
        
        # Validate length
        if len(cleaned) > 100:
            cleaned = cleaned[:97] + "..."
        
        return cleaned if cleaned else "Unknown"
        
    except Exception as e:
        print(f"Warning: Nabu error cleaning failed: {str(e)}. Using fallback.")
        return _fallback_error_cleaning(error_value)


def _fallback_error_cleaning(error_value: str) -> str:
    """Fallback error cleaning without Nabu."""
    cleaned = str(error_value).strip()
    
    # Remove file extensions
    for ext in ['.tar.gz', '.tar', '.gz', '.log', '.txt', '.dump']:
        cleaned = cleaned.replace(ext, '')
    
    # Extract error from file names
    if 'dump_' in cleaned.lower():
        return "System Dump"
    if 'afhc' in cleaned.lower():
        return "AFHC Error"
    if 'mce' in cleaned.lower():
        return "Machine Check Exception"
    if 'http' in cleaned.lower() or '://' in cleaned:
        return "Diagnostic Link"
    
    # Extract error from parentheses: "OS crash ( ACF )" → "ACF"
    import re
    paren_match = re.search(r'\(\s*([^)]+)\s*\)', cleaned)
    if paren_match:
        extracted = paren_match.group(1).strip()
        if len(extracted) < 30:  # Reasonable error code length
            return extracted
    
    # Remove extra whitespace
    cleaned = ' '.join(cleaned.split())
    
    # Truncate if too long
    if len(cleaned) > 100:
        cleaned = cleaned[:97] + "..."
    
    return cleaned if cleaned else "Unknown"
