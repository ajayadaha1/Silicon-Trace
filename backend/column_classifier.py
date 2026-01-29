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
    
    async def classify_columns(self, columns: List[str]) -> Dict[str, str]:
        """
        Classify a list of column headers using Nabu AI.
        
        Args:
            columns: List of column header names from Excel
            
        Returns:
            Dictionary mapping column names to categories
            Example: {"CPU_SN": "SERIAL_NUMBER", "错误类型": "ERROR_TYPE", ...}
        """
        if not columns:
            return {}
        
        # If Nabu not available, use fallback
        if not self.nabu_client:
            return self._fallback_classification(columns)
        
        # Prepare prompt for Nabu
        prompt = self._build_classification_prompt(columns)
        
        try:
            # Call Nabu AI for classification
            response_dict = await self.nabu_client.chat(
                user_prompt=prompt,
                history=[]
            )
            
            # Extract text response from dict
            response_text = response_dict.get('response', '') if isinstance(response_dict, dict) else str(response_dict)
            
            # Parse Nabu's response to extract classifications
            classification = self._parse_nabu_response(response_text, columns)
            
            print(f"✓ Nabu classified {len(classification)} columns")
            return classification
            
        except Exception as e:
            print(f"Warning: Nabu classification failed: {str(e)}. Using fallback.")
            return self._fallback_classification(columns)
    
    def _build_classification_prompt(self, columns: List[str]) -> str:
        """Build the prompt for Nabu AI column classification."""
        
        column_list = "\n".join([f"{i+1}. {col}" for i, col in enumerate(columns)])
        
        prompt = f"""You are an expert data analyst classifying hardware failure tracking columns.

Classify each of these Excel column headers into ONE category:

Categories:
- SERIAL_NUMBER: Serial numbers, barcodes, asset IDs, PPID, CPU_SN, 2D_barcode, System SN
- ERROR_TYPE: Error types, failures, symptoms, issues, fault codes (错误类型, Failtype, Error, Symptom)
- STATUS: Status, state, resolution progress, FA status, RMA status (状态, FA状态)
- TEST_TIER: Test stage names (L1, L2, ATE, SLT, CESLT, OSV, AFHC, FT1, FT2, Tier0-5)
- DATE: Dates, timestamps, date codes (日期, Fail Date, Deploy Date)
- CUSTOMER: Customer names, client info (客户, Customer, Client)
- PLATFORM: Platform, BIOS, firmware versions, hardware config
- DIAGNOSTIC: Log files, dump files, diagnostic paths, URLs, AFHC logs
- DESCRIPTION: Comments, notes, observations, debug notes, summaries
- IGNORE: Irrelevant, empty, or redundant columns

Column headers to classify:
{column_list}

Respond with ONLY a JSON object mapping each column to its category:
{{
  "column_name": "CATEGORY",
  ...
}}

Be intelligent about:
- Bilingual support (Chinese: 错误类型=ERROR_TYPE, 客户=CUSTOMER, 状态=STATUS, 日期=DATE)
- File references (dump_file, log_path, *.tar.gz) = DIAGNOSTIC
- URLs (SharePoint, http://) = DIAGNOSTIC
- Test tiers (L1, L2, ATE case-insensitive) = TEST_TIER
- Synonyms (Error/Failure/Issue/Symptom all = ERROR_TYPE)
"""
        
        return prompt
    
    def _parse_nabu_response(self, response: str, columns: List[str]) -> Dict[str, str]:
        """Parse Nabu's response to extract column classifications."""
        import json
        import re
        
        # Try to extract JSON from response
        try:
            # Look for JSON object in response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                classification = json.loads(json_str)
                
                # Validate categories
                validated = {}
                for col, category in classification.items():
                    if category.upper() in self.CATEGORIES:
                        validated[col] = category.upper()
                    else:
                        # Invalid category, use fallback for this column
                        validated[col] = self._classify_single_column(col)
                
                return validated
        except Exception as e:
            print(f"Warning: Failed to parse Nabu response: {str(e)}")
        
        # If parsing failed, use fallback
        return self._fallback_classification(columns)
    
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
        
        # Error type indicators
        if any(kw in col_lower for kw in ['error', 'fail', 'symptom', 'issue', 'problem', 
                                           '错误', '故障', 'fault']):
            # Check if it's a diagnostic file
            if any(kw in col_lower for kw in ['dump', 'log', 'file', 'path', '.tar', '.gz', 'afhc']):
                return "DIAGNOSTIC"
            return "ERROR_TYPE"
        
        # Status indicators
        if any(kw in col_lower for kw in ['status', 'state', '状态', 'fa_status', 'fa status', 
                                           'rma status', 'resolution']):
            return "STATUS"
        
        # Test tier indicators
        if any(kw in col_lower for kw in ['l1', 'l2', 'l3', 'ate', 'slt', 'ceslt', 'osv', 
                                           'afhc', 'ft1', 'ft2', 'fs1', 'fs2', 'tier']):
            return "TEST_TIER"
        
        # Date indicators
        if any(kw in col_lower for kw in ['date', 'time', '日期', 'deploy', 'fail_date', 
                                           'datecode', 'timestamp']):
            return "DATE"
        
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
