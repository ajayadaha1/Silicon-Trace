"""
Normalize existing error_type values in the database.
This script applies the validation and cleaning logic to all existing assets.
"""

import asyncio
import os
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from database import get_session, engine
from column_classifier import clean_error_type_with_nabu
from nabu_client import NabuClient


async def normalize_all_assets():
    """Apply normalization to all existing assets in the database."""
    
    # Initialize Nabu client
    api_token = os.getenv('NABU_API_TOKEN')
    if not api_token:
        print("Warning: NABU_API_TOKEN not set. Will use fallback cleaning only.")
        nabu_client = None
    else:
        nabu_client = NabuClient(api_token=api_token)
    
    # Import Asset model
    from models import Asset
    
    async with AsyncSession(engine) as session:
        # Get all assets
        stmt = select(Asset)
        result = await session.execute(stmt)
        assets = result.scalars().all()
        
        print(f"Found {len(assets)} assets to check")
        
        cleaned_count = 0
        ignored_count = 0
        checked = 0
        date_fixed_count = 0
        long_desc_count = 0
        tracking_extracted = 0
        
        for asset in assets:
            checked += 1
            
            # Extract tracking numbers from raw_data (re-extract to get newly matched ones)
            tracking_number = extract_tracking_number(asset.raw_data)
            if tracking_number:
                # Always update if we found a tracking number
                if '_tracking_number' not in asset.raw_data or asset.raw_data['_tracking_number'] != tracking_number:
                    print(f"  Extracting tracking for {asset.serial_number}: {tracking_number}")
                    asset.raw_data['_tracking_number'] = tracking_number
                    flag_modified(asset, "raw_data")  # Mark as modified for SQLAlchemy
                    tracking_extracted += 1
            
            if not asset.error_type:
                continue
            
            original_error = asset.error_type
            should_clean = False
            
            # Check if error_type is actually a date (common issue with old data)
            is_date = False
            if any(char.isdigit() for char in original_error):
                # Try to parse as date
                import re
                from datetime import datetime
                date_patterns = [
                    r'\d{4}-\d{2}-\d{2}',  # 2025-12-24
                    r'\d{2}/\d{2}/\d{4}',  # 12/24/2025
                    r'\d{4}/\d{2}/\d{2}',  # 2025/12/24
                ]
                for pattern in date_patterns:
                    if re.match(pattern, original_error.strip()):
                        is_date = True
                        break
            
            # If error_type is a date, look for the real error in raw_data
            if is_date:
                print(f"  Fixing date in error_type for {asset.serial_number}: {original_error}")
                
                # Search raw_data for actual error columns
                error_keywords = ['error', 'error_type', 'symptom', 'fail test', 'fail test case', 
                                '错误', '故障类型', 'issue', 'failure', 'problem', 'failtype']
                
                found_error = None
                for key, value in asset.raw_data.items():
                    if key.startswith('_'):
                        continue
                    key_lower = key.lower().strip()
                    
                    # Skip date columns
                    if 'date' in key_lower:
                        continue
                    
                    # Check if this is an error column
                    if any(kw in key_lower for kw in error_keywords):
                        if value and str(value).strip() not in ['', 'N/A', 'n/a', 'NA']:
                            # Validate it's not a file path or too long
                            value_str = str(value).strip()
                            if len(value_str) < 100 and not any(ext in value_str.lower() for ext in ['.tar', '.gz', '.log', 'http://', 'https://']):
                                found_error = value_str
                                print(f"    Found error in '{key}': {found_error}")
                                break
                
                if found_error:
                    asset.raw_data['_original_date_error'] = original_error
                    asset.error_type = found_error
                    date_fixed_count += 1
                else:
                    # No error found, set to Unknown
                    asset.raw_data['_original_date_error'] = original_error
                    asset.error_type = "Unknown"
                    date_fixed_count += 1
                continue
            
            # Check if error_type needs cleaning
            # 1. Very long descriptions (> 60 chars) - extract key error
            if len(original_error) > 60:
                print(f"  Cleaning long error for {asset.serial_number}: {original_error[:80]}...")
                cleaned_error = extract_key_error_from_description(original_error)
                if cleaned_error != original_error:
                    asset.raw_data['_original_long_error'] = original_error
                    asset.error_type = cleaned_error
                    long_desc_count += 1
                continue
            
            # 2. Contains file extensions
            if any(ext in original_error.lower() for ext in ['.tar.gz', '.tar', '.gz', '.log', '.txt', '.dump']):
                should_clean = True
            
            # 3. Contains URLs
            if 'http://' in original_error or 'https://' in original_error or '://' in original_error:
                should_clean = True
            
            # 4. Very descriptive (contains multiple sentences)
            if original_error.count('。') > 2 or original_error.count('.') > 3:
                should_clean = True
            
            if should_clean:
                print(f"  Cleaning error for {asset.serial_number}: {original_error[:80]}...")
                
                if nabu_client:
                    cleaned_error = await clean_error_type_with_nabu(original_error, nabu_client)
                else:
                    # Fallback cleaning
                    cleaned_error = _fallback_clean(original_error)
                
                if cleaned_error != original_error:
                    asset.raw_data['_original_error_type'] = original_error
                    asset.error_type = cleaned_error
                    cleaned_count += 1
        
        # Commit changes
        await session.commit()
        print(f"\n✓ Normalization complete:")
        print(f"  - {tracking_extracted} tracking numbers extracted")
        print(f"  - {date_fixed_count} error_type values fixed (were dates)")
        print(f"  - {long_desc_count} long descriptions shortened")
        print(f"  - {cleaned_count} error_type values cleaned")


def extract_tracking_number(raw_data: dict) -> str:
    """Extract tracking numbers from raw data columns."""
    import re
    
    tracking_patterns = {
        'fedex': r'(?:fedex|fed\s*ex)(?:\s*\(AWB)?[:\s]+([0-9]{12,})',
        'ups': r'(?:ups)(?:\s*\()?[:\s]+([0-9A-Z]{18})',
        'dhl': r'(?:dhl)(?:\s*\()?[:\s]+([0-9]{10,})',
        'usps': r'(?:usps)(?:\s*\()?[:\s]+([0-9]{20,})',
        'tracking': r'(?:tracking|track)(?:\s*\()?[:\s#]+([0-9A-Z]{10,})'
    }
    
    for key, value in raw_data.items():
        if key.startswith('_'):
            continue
        
        value_str = str(value).strip()
        if not value_str or len(value_str) > 2000:  # Increased to handle long RMA notes
            continue
        
        value_lower = value_str.lower()
        
        # Check for tracking number patterns
        for carrier, pattern in tracking_patterns.items():
            match = re.search(pattern, value_lower, re.IGNORECASE)
            if match:
                carrier_name = carrier.upper() if carrier != 'tracking' else ''
                number = match.group(1)
                return f"{carrier_name} {number}".strip() if carrier_name else number
    
    return None


def extract_key_error_from_description(description: str) -> str:
    """Extract the key error from a long description."""
    import re
    
    desc = description.strip()
    
    # Pattern 1: "Failed at: • something" -> extract "something"
    match = re.search(r'Failed at:\s*[•·]\s*(.+?)(?:\.|$)', desc, re.IGNORECASE)
    if match:
        error = match.group(1).strip()
        # Further clean: take first sentence or up to 50 chars
        if '.' in error:
            error = error.split('.')[0]
        return error[:50].strip() if len(error) > 50 else error
    
    # Pattern 2: Look for key error keywords
    error_keywords = ['stress test', 'margin search', 'reboot', 'crash', 'error', 'fail', 
                      'parity', 'ECC', 'WDT', 'ACF', 'PRF', 'training']
    
    for keyword in error_keywords:
        if keyword.lower() in desc.lower():
            # Extract phrase around keyword (max 50 chars)
            idx = desc.lower().find(keyword.lower())
            start = max(0, idx - 10)
            end = min(len(desc), idx + len(keyword) + 30)
            snippet = desc[start:end].strip()
            
            # Clean up
            if start > 0:
                # Find word boundary
                words = snippet.split()
                snippet = ' '.join(words[1:]) if len(words) > 1 else snippet
            
            return snippet[:50].strip()
    
    # Fallback: Take first 50 chars
    first_part = desc.split('.')[0] if '.' in desc else desc
    return first_part[:50].strip() + ('...' if len(first_part) > 50 else '')


def _fallback_clean(error_value: str) -> str:
    """Fallback error cleaning without Nabu."""
    import re
    
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
    
    # Extract error from parentheses
    paren_match = re.search(r'\(\s*([^)]+)\s*\)', cleaned)
    if paren_match:
        extracted = paren_match.group(1).strip()
        if len(extracted) < 30:
            return extracted
    
    # Remove extra whitespace
    cleaned = ' '.join(cleaned.split())
    
    # Truncate if too long
    if len(cleaned) > 50:
        cleaned = cleaned[:47] + "..."
    
    return cleaned if cleaned else "Unknown"


if __name__ == "__main__":
    print("🔄 Normalizing existing error_type values...")
    asyncio.run(normalize_all_assets())
