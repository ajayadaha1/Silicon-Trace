"""
Silicon Trace - Hardware Failure Analysis Dashboard

A Streamlit frontend for ingesting Excel files and tracing hardware assets.
"""

import streamlit as st
import requests
import pandas as pd
from typing import Optional, Dict, Any, List
import json
from langdetect import detect, LangDetectException
import matplotlib.pyplot as plt
from datetime import datetime
from collections import Counter

# Set Streamlit configuration for larger dataframe display
st.set_page_config(
    page_title="Silicon Trace",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Increase dataframe display limit from default 1000 to 10000 rows
pd.set_option('display.max_rows', 10000)


# Configuration
BACKEND_URL = "http://localhost:8000"

# Common Chinese to English translations for hardware terms
TRANSLATION_MAP = {
    # Status terms
    '已修复': 'Repaired',
    '待修复': 'Pending Repair',
    '已测试': 'Tested',
    '测试中': 'Testing',
    '已关闭': 'Closed',
    '打开': 'Open',
    '进行中': 'In Progress',
    '待处理': 'Pending',
    '已完成': 'Completed',
    '通过': 'Pass',
    '失败': 'Fail',
    
    # Location terms
    '南通': 'Nantong',
    '机房': 'Data Center',
    '是': 'Yes',
    '否': 'No',
    
    # Component terms
    '内存': 'Memory',
    '硬盘': 'Hard Drive',
    '主板': 'Motherboard',
    '电源': 'Power Supply',
    '风扇': 'Fan',
    'CPU': 'CPU',
    'GPU': 'GPU',
    
    # Error/Test terms
    '故障': 'Failure',
    '错误': 'Error',
    '异常': 'Abnormal',
    '损坏': 'Damaged',
    '无法启动': 'Cannot Start',
    '过热': 'Overheating',
    '老化': 'Aging/Burn-in',
    '测试': 'Test',
    '无效': 'Invalid',
    '缺失': 'Missing',
    '超时': 'Timeout',
    '崩溃': 'Crash',
    
    # Common phrases
    '无': 'None',
    '正常': 'Normal',
    '不正常': 'Abnormal',
    '未知': 'Unknown',
    '待定': 'Pending',
}


def has_chinese(text: str) -> bool:
    """Check if text contains Chinese characters"""
    if not text:
        return False
    for char in str(text):
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


def translate_text(text: str) -> str:
    """
    Translate Chinese text to English using dictionary lookup.
    Returns original text with translation in parentheses if Chinese detected.
    """
    if not text or not isinstance(text, str):
        return str(text) if text else 'N/A'
    
    text_str = str(text).strip()
    
    # Check if text contains Chinese characters
    if not has_chinese(text_str):
        return text_str
    
    # Check if we have a direct translation
    if text_str in TRANSLATION_MAP:
        return f"{text_str} ({TRANSLATION_MAP[text_str]})"
    
    # Check for partial matches and translate each part
    translated_parts = []
    found_translation = False
    
    for chinese, english in TRANSLATION_MAP.items():
        if chinese in text_str:
            text_str = text_str.replace(chinese, f"{chinese}[{english}]")
            found_translation = True
    
    if found_translation:
        return f"{text_str} (translated, may not be 100% accurate)"
    
    # If Chinese but no translation found
    return f"{text_str} (Chinese text - translation not in dictionary)"


# Page configuration
st.set_page_config(
    page_title="Silicon Trace",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="auto"
)

# Initialize session state for page navigation
if 'page' not in st.session_state:
    st.session_state.page = 'Dashboard'

# Custom CSS for better styling
st.markdown("""
    <style>
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #2d3748;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        background-color: #2d3748;
    }
    
    /* Show hamburger menu button */
    button[kind="header"] {
        color: #ff9a76 !important;
    }
    
    /* Collapsed sidebar - show icons only */
    section[data-testid="stSidebar"][aria-expanded="false"] {
        width: 80px !important;
        min-width: 80px !important;
    }
    
    section[data-testid="stSidebar"][aria-expanded="false"] .stButton button {
        font-size: 2rem;
        padding: 1rem 0;
        overflow: hidden;
        text-overflow: clip;
        white-space: nowrap;
        width: 60px;
        margin: 0 auto;
    }
    
    /* Expanded sidebar */
    section[data-testid="stSidebar"][aria-expanded="true"] {
        width: 280px !important;
    }
    
    section[data-testid="stSidebar"][aria-expanded="true"] .stButton button {
        text-align: left;
        padding-left: 1rem;
        font-size: 1.1rem;
    }
    
    /* Navigation button styling */
    .stButton button {
        background-color: transparent;
        color: #ff9a76;
        border: none;
        border-radius: 12px;
        padding: 0.75rem;
        margin: 0.25rem 0;
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton button:hover {
        background-color: #3d4a5c;
    }
    
    /* Active navigation button */
    .stButton button[kind="primary"] {
        background-color: #ff6b6b;
        color: white;
        box-shadow: 0 0 10px rgba(255, 107, 107, 0.5);
    }
    
    /* Main styling */
    .main-header {
        font-size: 2.5rem;
        color: #ff6b6b;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .metric-card-green {
        background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
    }
    
    .metric-card-blue {
        background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);
    }
    
    .metric-card-orange {
        background: linear-gradient(135deg, #f46b45 0%, #eea849 100%);
    }
    
    .metric-card-red {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
    }
    
    /* Sidebar styling */
    .sidebar-icon {
        font-size: 1.5rem;
        margin-right: 0.5rem;
    }
    
    /* Navigation buttons */
    .nav-button {
        width: 100%;
        text-align: left;
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        border-radius: 5px;
        border: none;
        background: #1e2130;
        color: white;
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .nav-button:hover {
        background: #ff6b6b;
        transform: translateX(5px);
    }
    
    .nav-button-active {
        background: #ff6b6b;
        border-left: 4px solid #fff;
    }
    
    /* Remove default streamlit padding */
    .block-container {
        padding-top: 2rem;
    }
    </style>
""", unsafe_allow_html=True)


def check_backend_health() -> bool:
    """Check if backend is accessible"""
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=5)
        return response.status_code == 200
    except:
        return False


def upload_file(file) -> Optional[Dict[str, Any]]:
    """Upload Excel file to backend"""
    try:
        files = {"file": (file.name, file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=180)
        
        if response.status_code == 200:
            return response.json()
        else:
            error_detail = response.json().get("detail", "Unknown error")
            st.error(f"Upload failed: {error_detail}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None


def search_asset(serial_number: str) -> Optional[Dict[str, Any]]:
    """Search for an asset by serial number"""
    try:
        response = requests.get(f"{BACKEND_URL}/assets/{serial_number}", timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            st.error(f"Search failed: {response.json().get('detail', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None


def search_assets(query: str) -> Optional[Dict[str, Any]]:
    """Search for assets matching a query"""
    try:
        response = requests.get(f"{BACKEND_URL}/search", params={"q": query}, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Search failed: {response.json().get('detail', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None


def get_source_files() -> Optional[List[Dict[str, Any]]]:
    """Get list of all source files"""
    try:
        response = requests.get(f"{BACKEND_URL}/source-files", timeout=10)
        
        if response.status_code == 200:
            return response.json().get("source_files", [])
        else:
            st.error(f"Failed to fetch source files")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None


def delete_source_file(filename: str) -> Optional[Dict[str, Any]]:
    """Delete all assets from a source file"""
    try:
        response = requests.delete(f"{BACKEND_URL}/source-files/{filename}", timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            error_detail = response.json().get("detail", "Unknown error")
            st.error(f"Delete failed: {error_detail}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None


def get_assets_filtered(source_files: List[str] = None, limit: int = 50000) -> Optional[Dict[str, Any]]:
    """Get assets with optional filtering by source files"""
    try:
        params = {"limit": limit}
        if source_files:
            params["source_files"] = ",".join(source_files)
        
        response = requests.get(f"{BACKEND_URL}/assets", params=params, timeout=60)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch assets: Status {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        st.error("Request timed out. Try reducing the data size or using filters.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None


def display_asset_card(asset: Dict[str, Any]):
    """Display asset information in a formatted card with ALL columns"""
    st.markdown('<div class="asset-card">', unsafe_allow_html=True)
    
    # Header with serial number
    st.markdown(f"<div class='metric-value'>{asset['serial_number']}</div>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Display all data from raw_data in a clean format
    if asset.get('raw_data'):
        # Create columns dynamically based on number of fields
        raw_data = asset['raw_data']
        # Filter out metadata fields
        display_data = {k: v for k, v in raw_data.items() if not k.startswith('_') and v is not None}
        
        if display_data:
            # Display in 2-column layout
            items = list(display_data.items())
            for i in range(0, len(items), 2):
                cols = st.columns(2)
                for j, (key, value) in enumerate(items[i:i+2]):
                    with cols[j]:
                        st.markdown(f"**{key}**")
                        st.write(str(value))
    
    st.markdown("---")
    
    # Metadata
    col1, col2 = st.columns(2)


def display_asset_details_modal(asset: Dict[str, Any]):
    """Display comprehensive asset details in organized tabs"""
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["🆔 Identity", "📅 Timeline", "🔧 Technical", "📄 Raw Data"])
    
    raw_data = asset.get('raw_data', {})
    
    # Tab 1: Identity
    with tab1:
        st.subheader("Asset Identity")
        
        # Key identifiers
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Serial Number", asset['serial_number'])
            st.metric("Source File", asset.get('source_filename', 'N/A'))
        with col2:
            st.metric("Source Sheet", raw_data.get('_source_sheet', 'N/A'))
            st.metric("Source Row", raw_data.get('_source_row', 'N/A'))
        
        st.markdown("---")
        
        # System info
        identity_fields = {}
        identity_keywords = ['system', 'cpu', 'sn', 'barcode', 'ppid', 'odm', 'location', '机房', 'vendor']
        
        for key, value in raw_data.items():
            if not key.startswith('_') and any(kw in key.lower() for kw in identity_keywords):
                identity_fields[key] = value
        
        if identity_fields:
            for key, value in identity_fields.items():
                st.text(f"{key}: {value}")
    
    # Tab 2: Timeline
    with tab2:
        st.subheader("Timeline & Lifecycle")
        
        # Extract date-related fields
        date_fields = {}
        date_keywords = ['date', 'time', 'day', '日期', 'deploy', 'fail', 'rma', 'ship']
        
        for key, value in raw_data.items():
            if not key.startswith('_') and any(kw in key.lower() for kw in date_keywords):
                date_fields[key] = value
        
        if date_fields:
            for key, value in date_fields.items():
                st.text(f"{key}: {value}")
        else:
            st.info("No timeline information available")
        
        # Show ingestion timestamp
        st.markdown("---")
        st.caption(f"Ingested: {asset.get('ingest_timestamp', 'N/A')}")
    
    # Tab 3: Technical
    with tab3:
        st.subheader("Technical Details")
        
        # Extract technical fields
        tech_fields = {}
        tech_keywords = ['error', 'fail', 'status', 'bios', 'firmware', 'log', 'symptom', 'issue', 
                        'test', 'code', 'version', '状态', '错误']
        
        for key, value in raw_data.items():
            if not key.startswith('_') and any(kw in key.lower() for kw in tech_keywords):
                tech_fields[key] = value
        
        if tech_fields:
            for key, value in tech_fields.items():
                st.markdown(f"**{key}**")
                st.text(str(value))
                st.markdown("")
        else:
            st.info("No technical details available")
    
    # Tab 4: Raw Data
    with tab4:
        st.subheader("Raw Excel Data")
        st.caption("Unmodified data from the source Excel file")
        st.json(raw_data)


def get_key_columns(asset: Dict[str, Any]) -> Dict[str, str]:
    """Extract the 'Golden 5' columns from an asset"""
    raw_data = asset.get('raw_data', {})
    
    # Schema mapping for bilingual support (Chinese/English)
    SCHEMA_MAP = {
        'sn': ['sn', 'serial', 'serial_number', 'serialnumber', 'cpu_sn', 'cpu sn', 
               '2d_barcode_sn', '2d barcode', 'system_sn', 'system sn'],
        'date': ['fail date', 'failed date', 'failure date', 'deploy date', 'deployment date',
                 'slt date', 'slt_date', 'fail_date', 'failed_date', 'failure_date', 'deploy_date',
                 'rma date', 'rma_date', 'date', 'date code', 'date_code', 'datecode', '日期', '故障日期'],
        'error': ['error', 'error_type', 'symptom', 'fail test', 'fail test case', 
                  '错误', '故障类型', 'issue', 'failure', 'problem'],
        'status': ['status', 'state', 'fa_status', 'fa status', '状态', 'fa状态', 
                   'fa 状态', 'rma status', 'rma_status'],
        'component': ['component', 'part', 'module', 'unit', '部件', 'cpu', 'gpu', 
                      'dimm', 'memory', 'disk', 'drive'],
        'location': ['location', 'site', 'lab', 'datacenter', 'data center', '机房', 
                     '南通机房', 'nantong', '是否南通机房', 'room']
    }
    
    result = {
        'Serial Number': asset['serial_number'],
        'Date': 'N/A',
        'Error': asset.get('error_type') or 'N/A',
        'Status': asset.get('status') or 'N/A',
        'Component': 'N/A'
    }
    
    # Try to match fields using schema map (no translation here for performance)
    for display_name, field_type in [('Date', 'date'), ('Error', 'error'), 
                                     ('Status', 'status'), ('Component', 'component')]:
        keywords = SCHEMA_MAP.get(field_type, [])
        
        if field_type == 'date':
            # Priority-based date field matching with fallback
            # 1. Try exact matches from high-priority date fields (full datetime preferred)
            priority_keywords = ['fail date', 'failed date', 'failure date', 'deploy date', 'deployment date', 'slt date']
            for key, value in raw_data.items():
                key_lower = key.lower().strip()
                if not key_lower.startswith('_') and value and any(kw in key_lower for kw in priority_keywords):
                    result[display_name] = str(value)
                    break
            
            # 2. If no priority match, try all date keywords
            if result[display_name] == 'N/A':
                for key, value in raw_data.items():
                    if not key.startswith('_') and any(kw == key.lower() for kw in keywords):
                        result[display_name] = str(value) if value else 'N/A'
                        break
            
            # 3. If still no match, try partial matches
            if result[display_name] == 'N/A':
                for key, value in raw_data.items():
                    if not key.startswith('_') and any(kw in key.lower() for kw in keywords):
                        result[display_name] = str(value) if value else 'N/A'
                        break
            
            # 4. Final fallback: any field containing "date" (but skip if it's just a number like datecode:2451)
            if result[display_name] == 'N/A':
                for key, value in raw_data.items():
                    if not key.startswith('_') and 'date' in key.lower() and value:
                        # Skip if value looks like just a year/number (e.g., 2451, 2025)
                        if not (str(value).isdigit() and len(str(value)) <= 4):
                            result[display_name] = str(value)
                            break
        else:
            # For non-date fields, use original logic
            for key, value in raw_data.items():
                if not key.startswith('_') and any(kw in key.lower() for kw in keywords):
                    if field_type == 'status' and value:
                        # Smart status extraction for messy status fields
                        result[display_name] = extract_status_from_text(str(value))
                    else:
                        result[display_name] = str(value) if value else 'N/A'
                    break
    
    return result


def extract_status_from_text(text: str) -> str:
    """
    Intelligently extract actual status from potentially messy status fields.
    Handles cases where status contains long technical logs.
    Converts Chinese to English for better graph rendering.
    """
    if not text or text == 'N/A':
        return 'N/A'
    
    text = str(text).strip()
    
    # Filter out serial numbers (typically all caps/numbers with specific patterns)
    if len(text) <= 20 and text.replace('-', '').replace('_', '').isalnum():
        # Check if it looks like a serial number pattern
        upper_count = sum(1 for c in text if c.isupper())
        digit_count = sum(1 for c in text if c.isdigit())
        if upper_count + digit_count > len(text) * 0.7:  # 70% uppercase or digits
            return 'Unknown'
    
    # Check for Chinese status terms FIRST and translate to English
    if any('\u4e00' <= char <= '\u9fff' for char in text):
        # Has Chinese characters - translate common status terms
        text_to_check = text.lower()
        
        if '已关闭' in text or '关闭' in text:
            return 'Closed'
        if '已打开' in text or '打开' in text or '开' in text:
            return 'Open'
        if '待处理' in text or '等待' in text:
            return 'Pending'
        if '进行中' in text or '处理中' in text:
            return 'In Progress'
        if '已完成' in text or '完成' in text:
            return 'Completed'
        if '已修复' in text or '修复' in text:
            return 'Repaired'
        if '待修复' in text:
            return 'Pending Repair'
        if '已测试' in text or '测试' in text:
            return 'Tested'
        if '测试中' in text:
            return 'Testing'
        if '失败' in text or '错误' in text:
            return 'Failed'
        if '通过' in text:
            return 'Passed'
        if '正常' in text:
            return 'Normal'
        
        # If we have Chinese but no known pattern, return as "Other (Chinese)"
        return 'Other'
    
    # Normalize and categorize common English status patterns
    text_lower = text.lower()
    
    # Map variations to standard categories
    if 'closed' in text_lower:
        if 'known' in text_lower or 'issue' in text_lower:
            return 'Closed - Known Issue'
        return 'Closed'
    
    if 'lab received' in text_lower or 'received' in text_lower:
        return 'Lab Received'
    
    if 'open' in text_lower:
        return 'Open'
    
    if 'pending' in text_lower or 'awaiting' in text_lower:
        return 'Pending'
    
    if 'in progress' in text_lower or 'investigating' in text_lower:
        return 'In Progress'
    
    if 'completed' in text_lower or 'resolved' in text_lower:
        return 'Completed'
    
    if 'failed' in text_lower or 'fail' in text_lower:
        return 'Failed'
    
    if 'passed' in text_lower or 'pass' in text_lower:
        return 'Passed'
    
    if 'testing' in text_lower or 'test' in text_lower:
        return 'Testing'
    
    if 'shipped' in text_lower or 'ship' in text_lower:
        return 'Shipped'
    
    if 'returned' in text_lower or 'rma' in text_lower:
        return 'Returned'
    
    # If text is short and clean, return first line
    first_line = text.split('\n')[0].strip()
    if len(first_line) <= 30:
        return first_line
    
    # For longer text, take first meaningful part
    first_sentence = first_line.split('.')[0].strip()
    if len(first_sentence) <= 30:
        return first_sentence
    
    # Last resort: truncate
    return first_line[:25].strip() + '...'


# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"

# Main App Header
st.markdown('<div class="main-header">🔍 Silicon Trace v3.0</div>', unsafe_allow_html=True)
st.markdown("**Hardware Failure Analysis Dashboard** - Real-time insights and analytics")

# Sidebar Navigation
with st.sidebar:
    # Add some spacing at top
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Navigation menu with icons
    pages = [
        {"icon": "🏠", "label": "Dashboard", "page": "Dashboard"},
        {"icon": "📤", "label": "File Manager", "page": "Ingest"},
        {"icon": "🔍", "label": "Trace Assets", "page": "Trace"},
        {"icon": "📊", "label": "Analytics", "page": "Analytics"},
    ]
    
    # Create navigation buttons
    for nav_item in pages:
        # Create button label with icon and text
        button_label = f"{nav_item['icon']}   {nav_item['label']}"
        
        if st.button(
            button_label,
            key=f"nav_{nav_item['page']}",
            use_container_width=True,
            type="primary" if st.session_state.page == nav_item["page"] else "secondary"
        ):
            # Clear analytics page init flag when leaving Analytics
            if st.session_state.page == "Analytics" and nav_item["page"] != "Analytics":
                if 'analytics_page_init' in st.session_state:
                    del st.session_state.analytics_page_init
            
            st.session_state.page = nav_item["page"]
            st.rerun()
    
    st.markdown("---")
    
    # System Status
    st.markdown("### System Status")
    backend_status = check_backend_health()
    
    if backend_status:
        st.success("✓ Backend Connected")
    else:
        st.error("✗ Backend Offline")
        st.info(f"Make sure the backend is running at {BACKEND_URL}")
    
    st.markdown("---")
    st.markdown("### About")
    st.info(
        "Silicon Trace v3.0 intelligently parses Excel files with inconsistent headers "
        "to extract hardware asset information. The system automatically detects "
        "serial number columns using heuristic scoring."
    )

# Main Content Area - Route based on selected page
if st.session_state.page == "Dashboard":
    # ==================== DASHBOARD PAGE ====================
    st.markdown("## 📊 Dashboard Overview")
    
    # Get all assets for dashboard metrics
    data = get_assets_filtered(source_files=None)
    
    if data and data.get('total', 0) > 0:
        assets = data['assets']
        
        # Extract metrics with customer segmentation
        error_counts = Counter()
        status_counts = Counter()
        customer_counts = Counter()
        date_months = []
        
        # New: Track customer breakdown for each metric
        error_by_customer = {}  # {error_type: {customer: count}}
        status_by_customer = {}  # {status: {customer: count}}
        month_by_customer = {}  # {month: {customer: count}}
        
        for asset in assets:
            key_cols = get_key_columns(asset)
            raw_data = asset.get('raw_data', {})
            
            # Extract customer first
            customer_keywords = ['customer', 'client', 'end_customer', 'end customer', 
                               'customer_name', 'customer name', '客户', 'cust']
            customer_found = False
            customer_name = 'Unknown'
            for key, value in raw_data.items():
                if not key.startswith('_') and value and any(kw in key.lower() for kw in customer_keywords):
                    customer_name = str(value).strip().upper()
                    if customer_name and customer_name not in ['N/A', 'NA', 'NONE', '']:
                        customer_counts[customer_name] += 1
                        customer_found = True
                        break
            
            if not customer_found:
                customer_counts['Unknown'] += 1
                customer_name = 'Unknown'
            
            # Count errors with customer breakdown
            error_type = key_cols.get('Error', 'Unknown')
            if error_type and error_type != 'N/A':
                error_counts[error_type] += 1
                if error_type not in error_by_customer:
                    error_by_customer[error_type] = Counter()
                error_by_customer[error_type][customer_name] += 1
            
            # Count status with customer breakdown
            status = key_cols.get('Status', 'Unknown')
            if status and status != 'N/A':
                status_counts[status] += 1
                if status not in status_by_customer:
                    status_by_customer[status] = Counter()
                status_by_customer[status][customer_name] += 1
            
            # Extract month with improved date parsing
            date_str = key_cols.get('Date', '')
            
            if date_str and date_str != 'N/A':
                try:
                    # Handle concatenated dates (take first one before " | ")
                    if ' | ' in str(date_str):
                        date_str = str(date_str).split(' | ')[0].strip()
                    
                    # Try various date formats
                    date_formats = [
                        '%Y-%m-%d',           # 2025-08-30
                        '%Y-%m-%d %H:%M:%S',  # 2025-08-30 02:54:00
                        '%m/%d/%Y',           # 08/30/2025
                        '%d/%m/%Y',           # 30/08/2025
                        '%Y/%m/%d',           # 2025/08/30
                        '%Y_%m',              # 2025_05
                        '%Y-%m',              # 2025-05
                    ]
                    
                    parsed = False
                    month_str = None
                    for fmt in date_formats:
                        try:
                            date_obj = datetime.strptime(str(date_str).strip(), fmt)
                            month_str = date_obj.strftime('%Y-%m')
                            date_months.append(month_str)
                            parsed = True
                            break
                        except:
                            continue
                    
                    # If still not parsed, try extracting YYYY-MM or YYYY_MM pattern
                    if not parsed:
                        import re
                        match = re.search(r'(\d{4})[-_](\d{2})', str(date_str))
                        if match:
                            month_str = f"{match.group(1)}-{match.group(2)}"
                            date_months.append(month_str)
                            parsed = True
                    
                    # Track customer for this month
                    if parsed and month_str:
                        if month_str not in month_by_customer:
                            month_by_customer[month_str] = Counter()
                        month_by_customer[month_str][customer_name] += 1
                except Exception as e:
                    pass
        
        month_counts = Counter(date_months)
        
        # Display Key Metrics
        st.markdown("### Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📦 Total Assets",
                value=f"{len(assets):,}",
                delta=f"+{len(assets) % 100}" if len(assets) > 0 else None
            )
        
        with col2:
            st.metric(
                label="⚠️ Unique Errors",
                value=len(error_counts),
                delta="-5%" if len(error_counts) > 0 else None,
                delta_color="inverse"
            )
        
        with col3:
            st.metric(
                label="📋 Status Types",
                value=len(status_counts)
            )
        
        with col4:
            st.metric(
                label="🏢 Customers",
                value=len([k for k in customer_counts.keys() if k != 'Unknown'])
            )
        
        st.markdown("---")
        
        # Display Graphs in 2x2 grid
        st.markdown("### Analytics Overview")
        
        col1, col2 = st.columns(2)
        
        # Graph 1: Failures by Failure Type (with customer segmentation)
        with col1:
            st.subheader("📊 Failures by Failure Type")
            if error_counts:
                top_errors = dict(error_counts.most_common(10))
                
                fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                ax.set_facecolor('#16213e')
                
                # Get all unique customers
                all_customers = set()
                for error in top_errors.keys():
                    if error in error_by_customer:
                        all_customers.update(error_by_customer[error].keys())
                all_customers = sorted(list(all_customers))
                
                # Define color palette for customers
                customer_colors = {
                    'ALIBABA': '#ff6b6b',
                    'TENCENT': '#51cf66',
                    'TURIN': '#339af0',
                    'META': '#cc5de8',
                    'GOOGLE': '#ffd43b',
                    'MICROSOFT': '#ff8787',
                    'AMAZON': '#ffa94d',
                    'FACEBOOK': '#74c0fc',
                    'BYTEDANCE': '#b197fc',
                    'BAIDU': '#ffc9c9',
                    'HUAWEI': '#a9e34b',
                    'INTEL': '#66d9e8',
                    'AMD': '#ff8787',
                    'Unknown': '#6c757d'
                }
                
                # Prepare data for stacked bars
                error_names = list(top_errors.keys())
                y_pos = range(len(error_names))
                
                # Create stacked bars
                left_offset = [0] * len(error_names)
                
                for customer in all_customers:
                    customer_values = []
                    for error in error_names:
                        count = error_by_customer.get(error, {}).get(customer, 0)
                        customer_values.append(count)
                    
                    color = customer_colors.get(customer, '#95a5a6')
                    ax.barh(y_pos, customer_values, left=left_offset, 
                           label=customer, color=color, edgecolor='white', linewidth=0.3)
                    
                    # Update left offset for next stack
                    left_offset = [left_offset[i] + customer_values[i] for i in range(len(error_names))]
                
                ax.set_yticks(y_pos)
                ax.set_yticklabels(error_names)
                ax.set_xlabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                ax.set_title('Top 10 Failure Types by Customer', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                ax.grid(axis='x', alpha=0.2, color='white', linestyle='--')
                ax.tick_params(colors='#ffffff', labelsize=10)
                
                for spine in ax.spines.values():
                    spine.set_color('#3a4a5c')
                
                # Add total count labels at end of bars
                for i, (error, total) in enumerate(top_errors.items()):
                    ax.text(total + 0.5, i, f'{int(total)}', 
                           ha='left', va='center', fontsize=11, 
                           color='#ffffff', fontweight='bold')
                
                # Add legend
                ax.legend(loc='lower right', facecolor='#16213e', edgecolor='#3a4a5c',
                         labelcolor='#ffffff', fontsize=9, ncol=2)
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            else:
                st.info("No error data available")
        
        # Graph 2: Assets by Month (with customer segmentation)
        with col2:
            st.subheader("📅 Assets by Month")
            if month_counts:
                sorted_months = dict(sorted(month_counts.items()))
                
                fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                ax.set_facecolor('#16213e')
                
                # Get all unique customers
                all_customers = set()
                for month in sorted_months.keys():
                    if month in month_by_customer:
                        all_customers.update(month_by_customer[month].keys())
                all_customers = sorted(list(all_customers))
                
                # Define color palette for customers (same as above)
                customer_colors = {
                    'ALIBABA': '#ff6b6b',
                    'TENCENT': '#51cf66',
                    'TURIN': '#339af0',
                    'META': '#cc5de8',
                    'GOOGLE': '#ffd43b',
                    'MICROSOFT': '#ff8787',
                    'AMAZON': '#ffa94d',
                    'FACEBOOK': '#74c0fc',
                    'BYTEDANCE': '#b197fc',
                    'BAIDU': '#ffc9c9',
                    'HUAWEI': '#a9e34b',
                    'INTEL': '#66d9e8',
                    'AMD': '#ff8787',
                    'Unknown': '#6c757d'
                }
                
                # Prepare data for stacked area chart
                months_list = list(sorted_months.keys())
                x_pos = range(len(months_list))
                
                # Create stacked area chart
                bottom = [0] * len(months_list)
                
                for customer in all_customers:
                    customer_values = []
                    for month in months_list:
                        count = month_by_customer.get(month, {}).get(customer, 0)
                        customer_values.append(count)
                    
                    color = customer_colors.get(customer, '#95a5a6')
                    ax.fill_between(x_pos, bottom, 
                                   [bottom[i] + customer_values[i] for i in range(len(months_list))],
                                   label=customer, color=color, alpha=0.8, edgecolor='white', linewidth=0.5)
                    
                    # Update bottom for next stack
                    bottom = [bottom[i] + customer_values[i] for i in range(len(months_list))]
                
                ax.set_xticks(x_pos)
                ax.set_xticklabels(months_list, rotation=45, ha='right', color='#ffffff', fontsize=10)
                ax.set_ylabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                ax.set_title('Asset Trend Over Time by Customer', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                ax.tick_params(colors='#ffffff', labelsize=10)
                
                for spine in ax.spines.values():
                    spine.set_color('#3a4a5c')
                
                # Add total value labels on top
                for i, total in enumerate(bottom):
                    ax.text(i, total + max(bottom)*0.02, f'{int(total)}', 
                           ha='center', va='bottom', fontsize=10, color='#ffffff', fontweight='bold')
                
                # Add legend
                ax.legend(loc='upper left', facecolor='#16213e', edgecolor='#3a4a5c',
                         labelcolor='#ffffff', fontsize=9, ncol=2)
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            else:
                st.info("No date data available")
        
        # Second row of graphs
        col3, col4 = st.columns(2)
        
        # Graph 3: Assets by Status (with customer segmentation)
        with col3:
            st.subheader("🔧 Assets by Status")
            if status_counts:
                top_status = dict(status_counts.most_common(10))
                
                fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                ax.set_facecolor('#16213e')
                
                # Get all unique customers
                all_customers = set()
                for status in top_status.keys():
                    if status in status_by_customer:
                        all_customers.update(status_by_customer[status].keys())
                all_customers = sorted(list(all_customers))
                
                # Define color palette for customers (same as above)
                customer_colors = {
                    'ALIBABA': '#ff6b6b',
                    'TENCENT': '#51cf66',
                    'TURIN': '#339af0',
                    'META': '#cc5de8',
                    'GOOGLE': '#ffd43b',
                    'MICROSOFT': '#ff8787',
                    'AMAZON': '#ffa94d',
                    'FACEBOOK': '#74c0fc',
                    'BYTEDANCE': '#b197fc',
                    'BAIDU': '#ffc9c9',
                    'HUAWEI': '#a9e34b',
                    'INTEL': '#66d9e8',
                    'AMD': '#ff8787',
                    'Unknown': '#6c757d'
                }
                
                # Prepare data for stacked bars
                status_names = list(top_status.keys())
                x_pos = range(len(status_names))
                
                # Create stacked bars
                bottom_offset = [0] * len(status_names)
                
                for customer in all_customers:
                    customer_values = []
                    for status in status_names:
                        count = status_by_customer.get(status, {}).get(customer, 0)
                        customer_values.append(count)
                    
                    color = customer_colors.get(customer, '#95a5a6')
                    ax.bar(x_pos, customer_values, bottom=bottom_offset,
                          label=customer, color=color, edgecolor='white', linewidth=0.3, width=0.7)
                    
                    # Update bottom offset for next stack
                    bottom_offset = [bottom_offset[i] + customer_values[i] for i in range(len(status_names))]
                
                ax.set_xticks(x_pos)
                ax.set_xticklabels(status_names, rotation=45, ha='right', 
                                  fontsize=10, fontweight='bold', color='#ffffff')
                ax.set_ylabel('Total Assets', color='#ffffff', fontsize=12, fontweight='bold')
                ax.set_title('Assets by Status by Customer', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                ax.tick_params(axis='x', colors='#ffffff', labelsize=10)
                ax.tick_params(axis='y', colors='#ffffff', labelsize=10)
                
                for spine in ax.spines.values():
                    spine.set_color('#3a4a5c')
                
                # Add total value labels on top of bars
                for i, total in enumerate(bottom_offset):
                    ax.text(i, total, f'{int(total)}', 
                           ha='center', va='bottom', fontsize=10, 
                           color='#ffffff', fontweight='bold')
                
                # Add legend
                ax.legend(loc='upper right', facecolor='#16213e', edgecolor='#3a4a5c',
                         labelcolor='#ffffff', fontsize=9, ncol=2)
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            else:
                st.info("No status data available")
        
        # Graph 4: Assets by Customer
        with col4:
            st.subheader("🏢 Assets by Customer")
            if customer_counts and len(customer_counts) > 1 or (len(customer_counts) == 1 and 'Unknown' not in customer_counts):
                filtered_customers = {k: v for k, v in customer_counts.items() if k != 'Unknown'} if len(customer_counts) > 1 else customer_counts
                
                if filtered_customers:
                    sorted_customers = sorted(filtered_customers.items(), key=lambda x: x[1], reverse=True)[:10]
                    customers = [x[0] for x in sorted_customers]
                    counts = [x[1] for x in sorted_customers]
                    
                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                    ax.set_facecolor('#16213e')
                    
                    # Create gradient colors from purple to pink
                    colors = ['#845ef7', '#9775fa', '#b197fc', '#cc99ff', '#d5a5ff',
                             '#deb3ff', '#e7c1ff', '#f0cfff', '#f9ddff', '#ffe0ff']
                    
                    bars = ax.barh(customers, counts, color=colors[:len(customers)], 
                                  edgecolor='white', linewidth=0.5)
                    ax.set_xlabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                    ax.set_title('Top 10 Customers', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                    ax.invert_yaxis()
                    ax.grid(axis='x', alpha=0.2, color='white', linestyle='--')
                    ax.tick_params(colors='#ffffff', labelsize=10)
                    
                    for spine in ax.spines.values():
                        spine.set_color('#3a4a5c')
                    
                    for i, bar in enumerate(bars):
                        width = bar.get_width()
                        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2., 
                               f'{int(width)}',
                               ha='left', va='center', fontsize=11, 
                               color='#ffffff', fontweight='bold')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
                else:
                    st.info("No customer data available")
            else:
                st.info("No customer data available")
    
    else:
        st.info("🎯 No assets in the database yet. Upload a file from the **Ingest Data** page to get started!")

elif st.session_state.page == "Ingest":
    # ==================== INGEST DATA PAGE ====================
    st.markdown("## 📤 Ingest Data")
    st.markdown("Upload Excel or PowerPoint files containing hardware asset data. The system will automatically detect serial numbers.")
    
    uploaded_files = st.file_uploader(
        "Choose file(s)",
        type=["xlsx", "xls", "pptx"],
        accept_multiple_files=True,
        help="Upload .xlsx, .xls, or .pptx files with asset data"
    )
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} file(s) selected")
        
        # Show file details
        for file in uploaded_files:
            st.text(f"  • {file.name} ({file.size:,} bytes)")
        
        if st.button("🚀 Process Files", type="primary", use_container_width=True):
            total_processed = 0
            total_created = 0
            total_updated = 0
            success_count = 0
            failed_files = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, file in enumerate(uploaded_files):
                status_text.text(f"Processing {file.name}...")
                
                with st.spinner(f"Processing {file.name}..."):
                    result = upload_file(file)
                    
                    if result and result.get("success"):
                        success_count += 1
                        total_processed += result['rows_processed']
                        total_created += result['rows_created']
                        total_updated += result['rows_updated']
                    else:
                        failed_files.append(file.name)
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.empty()
            progress_bar.empty()
            
            # Display results
            if success_count > 0:
                st.success(f"✓ Successfully processed {success_count}/{len(uploaded_files)} file(s)")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Rows Processed", total_processed)
                with col2:
                    st.metric("New Assets", total_created)
                with col3:
                    st.metric("Updated Assets", total_updated)
                
                if success_count == len(uploaded_files):
                    st.balloons()
            
            if failed_files:
                st.error(f"✗ Failed to process {len(failed_files)} file(s):")
                for fname in failed_files:
                    st.text(f"  • {fname}")
    
    st.markdown("---")
    st.markdown("### Expected File Format")
    st.markdown("""
    The Excel file should contain:
    - **Serial Number Column**: Headers like 'SN', 'Serial', 'Barcode', 'PPID', '2D', etc.
    - **Optional Columns**: Error Type, Status, or other asset information
    
    The system will automatically detect which column contains serial numbers.
    """)
    
    # File Management Section
    st.markdown("---")
    st.markdown("## 📂 File Management")
    
    source_files_data = get_source_files()
    
    if source_files_data and len(source_files_data) > 0:
        st.markdown("**Source Files**")
        
        # Create DataFrame for source files
        files_df = pd.DataFrame([
            {
                "Select": False,
                "Filename": sf['filename'],
                "Assets": sf['asset_count'],
                "Last Updated": sf.get('last_updated', 'N/A')[:19] if sf.get('last_updated') else 'N/A'
            }
            for sf in source_files_data
        ])
        
        # Display editable dataframe with checkboxes
        edited_df = st.data_editor(
            files_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select files to delete",
                    default=False,
                ),
                "Filename": st.column_config.TextColumn(
                    "Filename",
                    width="large",
                ),
                "Assets": st.column_config.NumberColumn(
                    "Assets",
                    help="Number of assets in this file",
                ),
                "Last Updated": st.column_config.TextColumn(
                    "Last Updated",
                    help="Last upload/update timestamp",
                )
            },
            disabled=["Filename", "Assets", "Last Updated"],
        )
        
        # Get selected files
        selected_to_delete = edited_df[edited_df["Select"] == True]["Filename"].tolist()
        
        if selected_to_delete:
            st.warning(f"⚠️ {len(selected_to_delete)} file(s) selected for deletion")
            col1, col2 = st.columns([3, 1])
            
            with col2:
                if st.button("🗑️ Delete Selected", type="secondary", use_container_width=True):
                    success_count = 0
                    failed_files = []
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, filename in enumerate(selected_to_delete):
                        status_text.text(f"Deleting {filename}...")
                        result = delete_source_file(filename)
                        
                        if result and result.get('success'):
                            success_count += 1
                        else:
                            failed_files.append(filename)
                        
                        progress_bar.progress((idx + 1) / len(selected_to_delete))
                    
                    status_text.empty()
                    progress_bar.empty()
                    
                    if success_count > 0:
                        st.success(f"✓ Deleted {success_count} file(s)")
                    
                    if failed_files:
                        st.error(f"✗ Failed to delete {len(failed_files)} file(s):")
                        for fname in failed_files:
                            st.text(f"  • {fname}")
                    
                    st.rerun()
    else:
        st.info("📁 No files uploaded yet")

elif st.session_state.page == "Trace":
    # ==================== TRACE ASSETS PAGE ====================
    # Initialize selected_files
    selected_files = None
    
    # Get list of source files
    source_files_data = get_source_files()
    
    if source_files_data and len(source_files_data) > 0:
        file_options = {
            f"{sf['filename']} ({sf['asset_count']} assets)": sf['filename'] 
            for sf in source_files_data
        }
        
        selected_display = st.multiselect(
            "Filter by Source Files",
            options=list(file_options.keys()),
            help="Filter assets by source file"
        )
        
        selected_files = [file_options[display] for display in selected_display] if selected_display else None
    
    st.markdown("---")
    
    # Section: Search Assets
    st.markdown("## 🔍 Search Assets")
    st.markdown("Search for assets by serial number or keyword. Build a logical chain with AND/OR operators.")

    # Initialize search criteria list (now with logic operators) and clear counter
    if 'search_criteria' not in st.session_state:
        st.session_state.search_criteria = []  # List of {"term": str, "logic": str}
    if 'form_clear_counter' not in st.session_state:
        st.session_state.form_clear_counter = 0
    
    # Use a form to support Enter key
    with st.form(key=f"search_form_{st.session_state.form_clear_counter}", clear_on_submit=False):
        # Logic selector (only show if there are existing criteria)
        logic_operator = None
        if st.session_state.search_criteria:
            st.markdown("""
                <div style="border: 2px solid #ff6b6b; padding: 10px; border-radius: 8px; 
                            background-color: rgba(255, 107, 107, 0.1); margin-bottom: 10px;">
                    <strong style="color: #ff6b6b;">⚠️ Required: Select Logical Operator</strong>
                </div>
            """, unsafe_allow_html=True)
            
            logic_operator = st.radio(
                "How should this filter relate to previous filters?",
                options=[None, "AND", "OR"],
                format_func=lambda x: "-- Select Logic --" if x is None else x,
                horizontal=True,
                help="AND = Must match all conditions | OR = Can match any condition",
                key=f"logic_radio_{st.session_state.form_clear_counter}"
            )
            
            if logic_operator:
                st.success(f"✓ {logic_operator} selected - Now click Add button below")
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            new_search_term = st.text_input(
                "Enter Search Term",
                value="",
                placeholder="e.g., ALIBABA, Cache L1, online app",
                help="Type your search term and press Enter (or click Add button). After selecting logic operator, click the Add button.",
                label_visibility="visible"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            add_button = st.form_submit_button("➕ Add", type="primary", use_container_width=True)
    
    # Handle add button (works for both Enter key and button click)
    if add_button:
        # Validate that logic operator is selected if there are existing criteria
        if st.session_state.search_criteria and logic_operator is None:
            st.error("⚠️ Please select a logical operator (AND or OR) before adding a new filter!")
            # Don't clear or rerun - keep the input
        elif new_search_term.strip():
            # Check if term already exists
            existing_terms = [c['term'] for c in st.session_state.search_criteria]
            if new_search_term.strip() not in existing_terms:
                # Add new criterion with logic operator
                st.session_state.search_criteria.append({
                    'term': new_search_term.strip(),
                    'logic': logic_operator  # None for first, "AND" or "OR" for others
                })
                st.session_state.show_analysis = False  # Reset analysis dialog
                st.session_state.form_clear_counter += 1  # Increment to clear the form
                st.rerun()
            else:
                st.warning(f"Filter '{new_search_term.strip()}' already exists!")
    
    # Display active search criteria as tags with logic operators
    if st.session_state.search_criteria:
        st.markdown("**Active Filters:**")
        
        # Display filters in a cleaner way using columns
        filter_cols = st.columns(len(st.session_state.search_criteria) * 2)  # Double for logic operators
        col_idx = 0
        
        for idx, criterion in enumerate(st.session_state.search_criteria):
            # Add logic operator before criterion (except first one)
            if idx > 0 and criterion['logic']:
                with filter_cols[col_idx]:
                    logic_color = "green" if criterion['logic'] == "AND" else "red"
                    st.markdown(f":{logic_color}[**{criterion['logic']}**]")
                col_idx += 1
            
            # Add the filter term
            with filter_cols[col_idx]:
                st.markdown(f":blue[🔍 **{criterion['term']}**]")
            col_idx += 1
        
        # Remove buttons row
        st.markdown("**Remove Filters:**")
        remove_cols = st.columns(min(len(st.session_state.search_criteria), 5))
        for idx, criterion in enumerate(st.session_state.search_criteria):
            col_idx = idx % 5
            with remove_cols[col_idx]:
                logic_label = f" ({criterion['logic']})" if criterion['logic'] else ""
                if st.button(f"❌ {criterion['term'][:15]}..{logic_label}" if len(criterion['term']) > 15 else f"❌ {criterion['term']}{logic_label}", 
                           key=f"remove_{idx}", use_container_width=True):
                    st.session_state.search_criteria.pop(idx)
                    st.session_state.show_analysis = False
                    st.rerun()

        
        # Clear all button and status message
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            # Build logic description
            logic_desc = []
            for idx, criterion in enumerate(st.session_state.search_criteria):
                if idx > 0 and criterion['logic']:
                    logic_desc.append(criterion['logic'])
            logic_summary = " and ".join(logic_desc) if logic_desc else "single filter"
            st.info(f"🔍 Showing assets with {logic_summary}")
        with col2:
            if st.button("🗑️ Clear All", type="secondary", use_container_width=True, key="clear_all_btn"):
                st.session_state.search_criteria = []
                st.session_state.form_clear_counter += 1  # Increment to force form re-creation and clear input
                st.session_state.show_analysis = False  # Reset analysis dialog
                st.rerun()
    
    # Section 3: All Assets Table/Aggregate View (BOTTOM)
    st.markdown("---")
    
    # View mode toggle
    view_mode = st.radio(
        "View Mode",
        options=["📋 List View", "📄 Complete View"],
        horizontal=True,
        help="Switch between simplified list and complete data view"
    )
    
    st.subheader("All Assets" if not selected_files else f"Assets from {len(selected_files)} file(s)")
    
    with st.spinner("Loading assets..."):
        # Get all assets or filtered by source files
        data = get_assets_filtered(source_files=selected_files)
        
        # Apply multiple search criteria filter with AND/OR logic
        if st.session_state.search_criteria and data and data.get('total', 0) > 0:
            all_assets = data['assets']
            
            # Build result set based on logic chain
            result_set = set()
            current_set = set()
            
            for idx, criterion in enumerate(st.session_state.search_criteria):
                criterion_term = criterion['term'].lower()
                criterion_logic = criterion['logic']
                
                # Find all assets matching this criterion
                matching_assets = []
                for asset_idx, asset in enumerate(all_assets):
                    match_found = False
                    
                    # Check serial number
                    if criterion_term in asset.get('serial_number', '').lower():
                        match_found = True
                    
                    # Check error_type
                    if not match_found and asset.get('error_type') and criterion_term in asset.get('error_type', '').lower():
                        match_found = True
                    
                    # Check status
                    if not match_found and asset.get('status') and criterion_term in asset.get('status', '').lower():
                        match_found = True
                    
                    # Check all raw_data fields
                    if not match_found:
                        raw_data = asset.get('raw_data', {})
                        for key, value in raw_data.items():
                            if value and criterion_term in str(value).lower():
                                match_found = True
                                break
                    
                    if match_found:
                        matching_assets.append(asset_idx)
                
                # Apply logic operation
                if idx == 0:
                    # First criterion - initialize result set
                    result_set = set(matching_assets)
                elif criterion_logic == "AND":
                    # AND: intersection - only keep assets in both sets
                    result_set = result_set.intersection(set(matching_assets))
                elif criterion_logic == "OR":
                    # OR: union - combine both sets
                    result_set = result_set.union(set(matching_assets))
            
            # Convert indices back to assets
            filtered_assets = [all_assets[idx] for idx in sorted(result_set)]
            
            # Update data with filtered results
            data = {
                'total': len(filtered_assets),
                'assets': filtered_assets
            }
            
            if len(filtered_assets) == 0:
                st.warning(f"❌ No assets found matching all {len(st.session_state.search_criteria)} criteria")
            else:
                # Show success message with Analyze button
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.success(f"✓ Found {len(filtered_assets)} asset(s) matching all {len(st.session_state.search_criteria)} criteria")
                with col2:
                    if st.button("📊 Analyze Results", type="primary", use_container_width=True):
                        st.session_state.show_analysis = True
                        st.rerun()
    
    # Show analysis dialog if triggered (only when search criteria exist and results found)
    if (st.session_state.get('show_analysis', False) and 
        st.session_state.search_criteria and 
        data and data.get('total', 0) > 0):
        @st.dialog("📊 Analysis of Filtered Results", width="large")
        def show_analysis_dialog():
            filtered_assets = data['assets']
            
            # Create tabs for different analyses
            tab1, tab2, tab3, tab4 = st.tabs(["👥 By Customer", "📅 Timeline", "🔧 By Status", "⚠️ Error Types"])
            
            # Tab 1: Customer Distribution
            with tab1:
                st.markdown("### Customer Distribution")
                customer_counts = Counter()
                
                for asset in filtered_assets:
                    raw_data = asset.get('raw_data', {})
                    customer_keywords = ['customer', 'client', 'end_customer', 'end customer', 
                                       'customer_name', 'customer name', '客户', 'cust']
                    customer_found = False
                    for key, value in raw_data.items():
                        if not key.startswith('_') and value and any(kw in key.lower() for kw in customer_keywords):
                            customer_name = str(value).strip().upper()
                            if customer_name and customer_name not in ['N/A', 'NA', 'NONE', '']:
                                customer_counts[customer_name] += 1
                                customer_found = True
                                break
                    if not customer_found:
                        customer_counts['Unknown'] += 1
                
                if customer_counts:
                    sorted_customers = sorted(customer_counts.items(), key=lambda x: x[1], reverse=True)
                    customers = [x[0] for x in sorted_customers]
                    counts = [x[1] for x in sorted_customers]
                    
                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                    ax.set_facecolor('#16213e')
                    
                    colors = ['#ff6b6b', '#51cf66', '#339af0', '#cc5de8', '#ffd43b', 
                             '#ff8787', '#ffa94d', '#74c0fc', '#b197fc', '#ffc9c9']
                    
                    bars = ax.barh(customers, counts, color=colors[:len(customers)], 
                                  edgecolor='white', linewidth=0.5)
                    ax.set_xlabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                    ax.set_title('Assets by Customer', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                    ax.invert_yaxis()
                    ax.grid(axis='x', alpha=0.2, color='white', linestyle='--')
                    ax.tick_params(colors='#ffffff', labelsize=10)
                    
                    for spine in ax.spines.values():
                        spine.set_color('#3a4a5c')
                    
                    for i, bar in enumerate(bars):
                        width = bar.get_width()
                        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2., 
                               f'{int(width)}', ha='left', va='center', 
                               fontsize=11, color='#ffffff', fontweight='bold')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
                else:
                    st.info("No customer data available")
            
            # Tab 2: Timeline Analysis
            with tab2:
                st.markdown("### Timeline Analysis")
                date_months = []
                
                for asset in filtered_assets:
                    key_cols = get_key_columns(asset)
                    date_str = key_cols.get('Date', '')
                    
                    if date_str and date_str != 'N/A':
                        try:
                            if ' | ' in str(date_str):
                                date_str = str(date_str).split(' | ')[0].strip()
                            
                            date_formats = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', 
                                          '%d/%m/%Y', '%Y/%m/%d', '%Y_%m', '%Y-%m']
                            
                            for fmt in date_formats:
                                try:
                                    date_obj = datetime.strptime(str(date_str).strip(), fmt)
                                    date_months.append(date_obj.strftime('%Y-%m'))
                                    break
                                except:
                                    continue
                        except:
                            pass
                
                if date_months:
                    month_counts = Counter(date_months)
                    sorted_months = dict(sorted(month_counts.items()))
                    
                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                    ax.set_facecolor('#16213e')
                    
                    months_list = list(sorted_months.keys())
                    values_list = list(sorted_months.values())
                    
                    ax.plot(range(len(months_list)), values_list, color='#51cf66', linewidth=3, 
                           marker='o', markersize=8, markerfacecolor='#51cf66', 
                           markeredgecolor='white', markeredgewidth=2)
                    ax.fill_between(range(len(months_list)), values_list, alpha=0.3, color='#51cf66')
                    
                    ax.set_xticks(range(len(months_list)))
                    ax.set_xticklabels(months_list, rotation=45, ha='right', color='#ffffff', fontsize=10)
                    ax.set_ylabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                    ax.set_title('Asset Trend Over Time', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                    ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                    ax.tick_params(colors='#ffffff', labelsize=10)
                    
                    for spine in ax.spines.values():
                        spine.set_color('#3a4a5c')
                    
                    for i, value in enumerate(values_list):
                        ax.text(i, value + max(values_list)*0.02, f'{int(value)}', 
                               ha='center', va='bottom', fontsize=10, color='#ffffff', fontweight='bold')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
                else:
                    st.info("No date data available")
            
            # Tab 3: Status Distribution
            with tab3:
                st.markdown("### Status Distribution")
                status_counts = Counter()
                
                for asset in filtered_assets:
                    key_cols = get_key_columns(asset)
                    status = key_cols.get('Status', 'Unknown')
                    if status and status != 'N/A':
                        status_counts[status] += 1
                
                if status_counts:
                    sorted_status = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
                    statuses = [x[0] for x in sorted_status]
                    counts = [x[1] for x in sorted_status]
                    
                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                    ax.set_facecolor('#16213e')
                    
                    colors = ['#ffd43b', '#ffc107', '#ffb300', '#ffa000', '#ff8f00',
                             '#ff6f00', '#fb8c00', '#f57c00', '#ef6c00', '#e65100']
                    
                    bars = ax.bar(range(len(statuses)), counts, color=colors[:len(statuses)], 
                                 edgecolor='white', linewidth=0.5, width=0.7)
                    
                    ax.set_xticks(range(len(statuses)))
                    ax.set_xticklabels(statuses, rotation=45, ha='right', 
                                      fontsize=10, fontweight='bold', color='#ffffff')
                    ax.set_ylabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                    ax.set_title('Assets by Status', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                    ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                    ax.tick_params(colors='#ffffff', labelsize=10)
                    
                    for spine in ax.spines.values():
                        spine.set_color('#3a4a5c')
                    
                    for i, bar in enumerate(bars):
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2, height,
                               f'{int(height)}', ha='center', va='bottom', 
                               fontsize=10, color='#ffffff', fontweight='bold')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
                else:
                    st.info("No status data available")
            
            # Tab 4: Error Type Breakdown
            with tab4:
                st.markdown("### Error Type Breakdown")
                error_counts = Counter()
                
                for asset in filtered_assets:
                    key_cols = get_key_columns(asset)
                    error_type = key_cols.get('Error', 'Unknown')
                    if error_type and error_type != 'N/A':
                        error_counts[error_type] += 1
                
                if error_counts:
                    top_errors = dict(error_counts.most_common(10))
                    
                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                    ax.set_facecolor('#16213e')
                    
                    colors = ['#ff6b6b', '#ee5a6f', '#f06595', '#cc5de8', '#845ef7', 
                             '#5c7cfa', '#339af0', '#22b8cf', '#20c997', '#51cf66']
                    
                    bars = ax.barh(list(top_errors.keys()), list(top_errors.values()), 
                                  color=colors[:len(top_errors)], edgecolor='white', linewidth=0.5)
                    ax.set_xlabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                    ax.set_title('Top 10 Error Types', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                    ax.grid(axis='x', alpha=0.2, color='white', linestyle='--')
                    ax.tick_params(colors='#ffffff', labelsize=10)
                    
                    for spine in ax.spines.values():
                        spine.set_color('#3a4a5c')
                    
                    for bar in bars:
                        width = bar.get_width()
                        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, 
                               f'{int(width)}', ha='left', va='center', 
                               fontsize=11, color='#ffffff', fontweight='bold')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
                else:
                    st.info("No error data available")
            
            # Close button
            if st.button("✖ Close", type="secondary", use_container_width=True):
                st.session_state.show_analysis = False
                st.rerun()
        
        show_analysis_dialog()
    
    if data and data.get('total', 0) > 0:
        assets = data['assets']
        
        if view_mode == "📋 List View":
            # List View: Show Golden 5 columns with row selection
            st.caption(f"Showing {len(assets)} assets - Click on any row to see full details")
            
            # Create table with only key columns
            table_data = []
            for idx, asset in enumerate(assets):
                key_cols = get_key_columns(asset)
                table_data.append(key_cols)
            
            df = pd.DataFrame(table_data)
            
            # Display table with row selection
            selected = st.dataframe(
                df,
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="asset_table",
                height=600  # Allow scrolling through all rows
            )
            
            # Show dialog when a row is selected
            if selected.selection.rows:
                selected_idx = selected.selection.rows[0]
                selected_asset = assets[selected_idx]
                
                @st.dialog(f"Asset Details: {selected_asset['serial_number']}", width="large")
                def show_asset_details():
                    raw_data = selected_asset.get('raw_data', {})
                    
                    st.info("ℹ️ Chinese text is automatically translated (may not be 100% accurate)")
                    
                    # Create tabs in dialog
                    tab1, tab2, tab3, tab4 = st.tabs(["🆔 Identity", "📅 Timeline", "🔧 Technical", "📄 Raw Data"])
                    
                    # Tab 1: Identity
                    with tab1:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Serial Number", selected_asset['serial_number'])
                            st.metric("Source File", selected_asset.get('source_filename', 'N/A'))
                        with col2:
                            st.metric("Source Sheet", raw_data.get('_source_sheet', 'N/A'))
                            st.metric("Source Row", raw_data.get('_source_row', 'N/A'))
                        
                        st.markdown("---")
                        st.markdown("**System Information**")
                        
                        identity_keywords = ['system', 'cpu', 'sn', 'barcode', 'ppid', 'odm', 'location', '机房', 'vendor']
                        for key, value in raw_data.items():
                            if not key.startswith('_') and any(kw in key.lower() for kw in identity_keywords):
                                translated_value = translate_text(value) if value else 'N/A'
                                st.text(f"{key}: {translated_value}")
                    
                    # Tab 2: Timeline
                    with tab2:
                        date_keywords = ['date', 'time', 'day', '日期', 'deploy', 'fail', 'rma', 'ship']
                        date_found = False
                        
                        for key, value in raw_data.items():
                            if not key.startswith('_') and any(kw in key.lower() for kw in date_keywords):
                                translated_value = translate_text(value) if value else 'N/A'
                                st.metric(key, translated_value)
                                date_found = True
                        
                        if not date_found:
                            st.info("No timeline information available")
                        
                        st.markdown("---")
                        st.caption(f"Ingested: {selected_asset.get('ingest_timestamp', 'N/A')}")
                    
                    # Tab 3: Technical
                    with tab3:
                        tech_keywords = ['error', 'fail', 'status', 'bios', 'firmware', 'log', 'symptom', 'issue', 
                                       'test', 'code', 'version', '状态', '错误']
                        tech_found = False
                        
                        for key, value in raw_data.items():
                            if not key.startswith('_') and any(kw in key.lower() for kw in tech_keywords):
                                st.markdown(f"**{key}**")
                                translated_value = translate_text(value) if value else 'N/A'
                                st.text(str(translated_value))
                                st.markdown("")
                                tech_found = True
                        
                        if not tech_found:
                            st.info("No technical details available")
                    
                    # Tab 4: Raw Data
                    with tab4:
                        st.json(raw_data)
                
                show_asset_details()
        
        elif view_mode == "📄 Complete View":
            # Complete View: Show all columns from raw_data
            st.caption(f"Showing {len(assets)} assets with all available columns - Click on any row to see full details")
            
            # Create a dynamic table with ALL columns from raw_data
            assets_list = []
            for a in assets:
                # Start with basic info
                asset_row = {
                    'Serial Number': str(a['serial_number']),
                    'Ingested': str(a['ingest_timestamp'][:10]) if a.get('ingest_timestamp') else 'N/A',
                    'Source File': str(a.get('source_filename', 'N/A'))
                }
                # Add all columns from raw_data
                if a.get('raw_data'):
                    for key, value in a['raw_data'].items():
                        # Skip metadata fields
                        if not key.startswith('_'):
                            # Convert all values to strings to avoid Arrow type errors
                            asset_row[key] = str(value) if value is not None else 'N/A'
                assets_list.append(asset_row)
            
            # Create DataFrame and explicitly convert all columns to string type
            assets_df = pd.DataFrame(assets_list)
            for col in assets_df.columns:
                assets_df[col] = assets_df[col].astype(str)
            
            # Display table with row selection
            selected = st.dataframe(
                assets_df,
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="complete_asset_table",
                height=600  # Allow scrolling through all rows
            )
            
            # Show dialog when a row is selected
            if selected.selection.rows:
                selected_idx = selected.selection.rows[0]
                selected_asset = assets[selected_idx]
                
                @st.dialog(f"Asset Details: {selected_asset['serial_number']}", width="large")
                def show_complete_asset_details():
                    raw_data = selected_asset.get('raw_data', {})
                    
                    st.info("ℹ️ Chinese text is automatically translated (may not be 100% accurate)")
                    
                    # Create tabs in dialog
                    tab1, tab2, tab3, tab4 = st.tabs(["🆔 Identity", "📅 Timeline", "🔧 Technical", "📄 Raw Data"])
                    
                    # Tab 1: Identity
                    with tab1:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Serial Number", selected_asset['serial_number'])
                            st.metric("Source File", selected_asset.get('source_filename', 'N/A'))
                        with col2:
                            st.metric("Source Sheet", raw_data.get('_source_sheet', 'N/A'))
                            st.metric("Source Row", raw_data.get('_source_row', 'N/A'))
                        
                        st.markdown("---")
                        st.markdown("**System Information**")
                        
                        identity_keywords = ['system', 'cpu', 'sn', 'barcode', 'ppid', 'odm', 'location', '机房', 'vendor']
                        for key, value in raw_data.items():
                            if not key.startswith('_') and any(kw in key.lower() for kw in identity_keywords):
                                translated_value = translate_text(value) if value else 'N/A'
                                st.text(f"{key}: {translated_value}")
                    
                    # Tab 2: Timeline
                    with tab2:
                        date_keywords = ['date', 'time', 'day', '日期', 'deploy', 'fail', 'rma', 'ship']
                        date_found = False
                        
                        for key, value in raw_data.items():
                            if not key.startswith('_') and any(kw in key.lower() for kw in date_keywords):
                                translated_value = translate_text(value) if value else 'N/A'
                                st.metric(key, translated_value)
                                date_found = True
                        
                        if not date_found:
                            st.info("No timeline information available")
                        
                        st.markdown("---")
                        st.caption(f"Ingested: {selected_asset.get('ingest_timestamp', 'N/A')}")
                    
                    # Tab 3: Technical
                    with tab3:
                        tech_keywords = ['error', 'fail', 'status', 'bios', 'firmware', 'log', 'symptom', 'issue', 
                                       'test', 'code', 'version', '状态', '错误']
                        tech_found = False
                        
                        for key, value in raw_data.items():
                            if not key.startswith('_') and any(kw in key.lower() for kw in tech_keywords):
                                st.markdown(f"**{key}**")
                                translated_value = translate_text(value) if value else 'N/A'
                                st.text(str(translated_value))
                                st.markdown("")
                                tech_found = True
                        
                        if not tech_found:
                            st.info("No technical details available")
                    
                    # Tab 4: Raw Data
                    with tab4:
                        st.json(raw_data)
                
                show_complete_asset_details()
    
    else:
        if selected_files:
            st.info(f"No assets found from selected file(s).")
        else:
            st.info("No assets in the database yet. Upload a file to get started!")

elif st.session_state.page == "Analytics":
    # ==================== ANALYTICS PAGE ====================
    st.markdown("## 📈 Analytics")
    st.markdown("Detailed breakdown and grouping of asset data")
    
    # Clear any analytics analysis dialogs when entering this page
    if 'analytics_page_init' not in st.session_state:
        # Clear all analytics analysis flags
        keys_to_remove = [key for key in st.session_state.keys() if key.startswith('show_analytics_analysis_')]
        for key in keys_to_remove:
            del st.session_state[key]
        st.session_state.analytics_page_init = True
    
    # Get all assets for analytics
    data = get_assets_filtered(source_files=None)
    
    if data and data.get('total', 0) > 0:
        assets = data['assets']
        
        # Reset init flag if group_by changes
        if 'last_group_by' not in st.session_state:
            st.session_state.last_group_by = None
        
        # Add grouping selector
        group_by = st.radio(
            "Group By",
            options=["Failure Type", "Month", "Status", "Customer", "Tier Analysis"],
            horizontal=True,
            help="Select field to group assets by. 'Tier Analysis' shows test tier progression."
        )
        
        # Clear analysis dialogs if grouping changed
        if st.session_state.last_group_by != group_by:
            keys_to_remove = [key for key in st.session_state.keys() if key.startswith('show_analytics_analysis_')]
            for key in keys_to_remove:
                del st.session_state[key]
            st.session_state.last_group_by = group_by
        
        st.markdown("---")
        st.caption(f"Assets grouped by {group_by.lower()}")
        
        # Tier Analysis validation and logging
        if group_by == "Tier Analysis":
            import logging
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger(__name__)
            
            # First, validate if tier columns exist in any asset
            tier_keywords = ['l1', 'l2', 'slt', 'ceslt', 'osv', 'afhc', 'tier0', 'tier1', 'tier2', 
                           'tier3', 'tier4', 'tier5', 'fs1', 'fs2', 'diag', 'aft', 'wl:', 'hdrt', 'difect']
            
            logger.info("=" * 80)
            logger.info("TIER ANALYSIS VALIDATION STARTING")
            logger.info(f"Total assets to analyze: {len(assets)}")
            
            # Check if any assets have tier columns and track which files have tier data
            assets_with_tiers = 0
            assets_without_tiers = 0
            all_detected_tier_cols = set()
            files_with_tiers = set()
            files_without_tiers = set()
            
            for asset in assets:
                raw_data = asset.get('raw_data', {})
                asset_tier_cols = []
                
                # Get filename from asset
                filename = asset.get('_filename', 'Unknown File')
                
                for key in raw_data.keys():
                    if not key.startswith('_'):
                        key_lower = key.lower().strip()
                        
                        # Skip date columns
                        if any(x in key_lower for x in ['date', 'timestamp', 'time', 'mfg', 'wafer', 'ship', 'receive']):
                            continue
                        
                        # Check for tier columns
                        is_tier = False
                        for kw in tier_keywords:
                            if kw in key_lower:
                                is_tier = True
                                break
                        
                        # Special handling for 'ate'
                        if not is_tier and ('ate' in key_lower or ' ate ' in key_lower):
                            if 'date' not in key_lower and 'update' not in key_lower and 'create' not in key_lower:
                                is_tier = True
                        
                        if is_tier:
                            asset_tier_cols.append(key)
                            all_detected_tier_cols.add(key)
                
                if asset_tier_cols:
                    assets_with_tiers += 1
                    files_with_tiers.add(filename)
                else:
                    assets_without_tiers += 1
                    files_without_tiers.add(filename)
            
            logger.info(f"Assets with tier columns: {assets_with_tiers}/{len(assets)}")
            logger.info(f"Assets without tier columns: {assets_without_tiers}/{len(assets)}")
            logger.info(f"Detected tier columns across all assets: {sorted(all_detected_tier_cols)}")
            logger.info(f"Files with tier data: {sorted(files_with_tiers)}")
            logger.info(f"Files without tier data: {sorted(files_without_tiers)}")
            
            # Show messages based on tier data availability
            # Check if we truly have multiple different files (not all "Unknown File")
            has_multiple_files = len(files_with_tiers | files_without_tiers) > 1 or (
                len(files_with_tiers) == 1 and len(files_without_tiers) == 1 and 
                files_with_tiers != files_without_tiers
            )
            
            if assets_with_tiers == 0:
                # No tier data at all
                st.error("⚠️ Tier Analysis Not Available")
                st.info(
                    "No tier-related columns detected in any of the uploaded files. "
                    "Tier Analysis requires columns with test tier information such as:\n"
                    "- L1, L2, ATE, SLT, CESLT, OSV\n"
                    "- Tier0, Tier1, Tier2, Tier3, Tier4, Tier5\n"
                    "- ATE FT1, ATE FT2, SLT1, SLT2, FS1, FS2\n"
                    "- AFHC, WL:, Diag\n\n"
                    "Please upload a file with tier test data to use this feature."
                )
                logger.warning("TIER ANALYSIS ABORTED: No tier columns found")
            elif assets_without_tiers > 0 and has_multiple_files:
                # Some files/sheets have tier data, some don't (only show if truly different files)
                st.warning(f"⚠️ Partial Tier Data Available")
                st.info(
                    f"📊 **{assets_with_tiers} assets** have tier data and will be analyzed.\n\n"
                    f"⚠️ **{assets_without_tiers} assets** do not have tier columns and will be grouped as '❓ No Tier Data'.\n\n"
                    f"**Sources WITH tier data:** {', '.join(sorted(files_with_tiers))}\n\n"
                    f"**Sources WITHOUT tier data:** {', '.join(sorted(files_without_tiers))}"
                )
                logger.info(f"TIER ANALYSIS PROCEEDING with partial data: {assets_with_tiers} assets with tiers, {assets_without_tiers} without")
            elif assets_without_tiers > 0:
                # Same file but some assets don't have tier data (likely different rows/sheets)
                st.info(
                    f"📊 Analyzing **{assets_with_tiers} assets** with tier data.\n\n"
                    f"ℹ️ {assets_without_tiers} asset(s) do not have tier columns and will be grouped as '❓ No Tier Data'."
                )
                logger.info(f"TIER ANALYSIS PROCEEDING: {assets_with_tiers} assets with tiers, {assets_without_tiers} without")
            else:
                # All assets have tier data
                st.success(f"✅ All {assets_with_tiers} assets have tier data ({len(all_detected_tier_cols)} tier columns detected)")
                logger.info(f"TIER ANALYSIS PROCEEDING with {assets_with_tiers} assets (all have tier data)")
        
        # Stop here if tier analysis with no data
        if group_by == "Tier Analysis" and assets_with_tiers == 0:
            st.stop()
        
        # Group assets by selected field
        from collections import defaultdict
        groups = defaultdict(list)
        
        for asset in assets:
            key_cols = get_key_columns(asset)
            raw_data = asset.get('raw_data', {})
            
            if group_by == "Failure Type":
                group_key = key_cols.get('Error', 'Unknown')
            elif group_by == "Month":
                date_str = key_cols.get('Date', '')
                if date_str and date_str != 'N/A':
                    try:
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                            try:
                                date_obj = datetime.strptime(str(date_str).split()[0], fmt)
                                group_key = date_obj.strftime('%Y-%m')
                                break
                            except:
                                continue
                        else:
                            group_key = 'Unknown'
                    except:
                        group_key = 'Unknown'
                else:
                    group_key = 'Unknown'
            elif group_by == "Status":
                group_key = key_cols.get('Status', 'Unknown')
            
            elif group_by == "Month":
                # Extract month from date
                date_str = key_cols.get('Date', '')
                if date_str and date_str != 'N/A':
                    try:
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                            try:
                                date_obj = datetime.strptime(str(date_str).split()[0], fmt)
                                group_key = date_obj.strftime('%Y-%m')
                                break
                            except:
                                continue
                        else:
                            group_key = 'Unknown'
                    except:
                        group_key = 'Unknown'
                else:
                    group_key = 'Unknown'
            
            elif group_by == "Customer":
                # Intelligently extract customer from raw_data
                customer_keywords = ['customer', 'client', 'end_customer', 'end customer', 
                                   'customer_name', 'customer name', '客户', 'cust']
                customer_found = False
                for key, value in raw_data.items():
                    if not key.startswith('_') and value and any(kw in key.lower() for kw in customer_keywords):
                        customer_name = str(value).strip().upper()
                        if customer_name and customer_name not in ['N/A', 'NA', 'NONE', '']:
                            group_key = customer_name
                            customer_found = True
                            break
                
                if not customer_found:
                    group_key = 'Unknown'
            
            elif group_by == "Tier Analysis":
                # Detect tier columns and analyze test flow progression
                # Look for tier-related columns: L1, L2, ATE, SLT, Tier0-5, etc.
                tier_columns = []
                tier_keywords = ['l1', 'l2', 'slt', 'ceslt', 'osv', 'afhc', 'tier0', 'tier1', 'tier2',
                               'tier3', 'tier4', 'tier5', 'tier 0', 'tier 1', 'tier 2', 'tier 3', 'tier 4', 'tier 5',
                               'ft1', 'ft2', 'fs1', 'fs2', 'diag', 'aft', 'wl:', 'hdrt', 'difect', 
                               'per core', 'charz', 'shak', 'kvm']
                
                serial = key_cols.get('Serial Number', 'Unknown')
                logger.info(f"\n--- Processing Asset: {serial} ---")
                
                for key in raw_data.keys():
                    if not key.startswith('_'):
                        key_lower = key.lower().strip()
                        
                        # Explicitly exclude date/time/mfg columns
                        if any(x in key_lower for x in ['date', 'timestamp', 'time', 'mfg', 'wafer', 'ship', 'receive']):
                            logger.debug(f"  Skipping date column: {key}")
                            continue  # Skip all date/time/manufacturing date columns
                        
                        # Exclude status/result columns (not actual test tiers)
                        if any(x in key_lower for x in ['status', 'result', 'plan', 'comment', 'debug', 'repro status']):
                            logger.debug(f"  Skipping status column: {key}")
                            continue
                        
                        # Check if this is a tier column using flexible matching
                        is_tier = False
                        for kw in tier_keywords:
                            if kw in key_lower:
                                is_tier = True
                                logger.debug(f"  Tier column detected (keyword '{kw}'): {key}")
                                break
                        
                        # Special handling for 'ate' - must be word boundary to avoid matching 'date'
                        if not is_tier and ('ate' in key_lower or ' ate ' in key_lower or key_lower.startswith('ate ') or key_lower.endswith(' ate') or key_lower == 'ate'):
                            # Make sure it's not part of 'date', 'update', 'create', etc.
                            if 'date' not in key_lower and 'update' not in key_lower and 'create' not in key_lower:
                                is_tier = True
                                logger.debug(f"  Tier column detected (ATE match): {key}")
                        
                        if is_tier:
                            tier_value = raw_data.get(key)
                            tier_columns.append((key, tier_value))
                            logger.info(f"  {key}: '{tier_value}'")
                
                logger.info(f"  Total tier columns found: {len(tier_columns)}")
                
                # Define pass/not-run values with smarter matching
                def is_pass_value(val):
                    """Check if a value indicates a passing test - ONLY explicit PASS/NFF/NFT without '?'"""
                    if not val:
                        return False
                    val_str = str(val).strip().upper()
                    
                    # If value ends with "?", it's NOT a definitive pass (uncertain = failure)
                    if val_str.endswith('?'):
                        return False
                    
                    # Pass ONLY if it's exactly NFF/NFT (with optional hrs in parens) or PASS/PASSED
                    # Must start with these exact prefixes
                    if val_str.startswith('NFF') or val_str.startswith('NFT'):
                        # Additional check: shouldn't contain failure keywords
                        val_lower = val_str.lower()
                        if any(fail_word in val_lower for fail_word in ['fail', 'hang', 'error', 'crash']):
                            return False
                        return True
                    return val_str in ['PASS', 'PASSED']
                
                def is_not_run(val):
                    """Check if a value indicates test was not run - ONLY explicit NOT RUN/N/A"""
                    if not val or str(val).strip() == '':
                        return True
                    val_str = str(val).strip().upper()
                    
                    # Values with "?" are NOT "not run" - they are uncertain failures
                    # Only explicit NOT RUN, N/A, NA count as not run
                    return val_str in ['N/A', 'NA'] or 'NOT RUN' in val_str or 'NOTRUN' in val_str
                
                def is_failure(val):
                    """Check if a value indicates a test failure - anything except explicit PASS or NOT RUN"""
                    if is_not_run(val):
                        return False
                    if is_pass_value(val):
                        return False
                    # If it has content and it's not pass/not-run, it's a failure
                    # This includes "Fail?", "NFF?", and any other uncertain or error values
                    val_str = str(val).strip()
                    return len(val_str) > 0
                
                # Sort tier columns by their tier level for proper progression analysis
                # Tier order: tier0/l1/l2 -> tier1/ate ft -> tier2/slt -> tier3/fs1 -> tier4/diag -> tier5/fs2/wl
                def get_tier_order(col_name):
                    col_lower = col_name.lower()
                    # Assign order priority - check for exact matches and substrings
                    
                    # Tier 0: Basic tests (L1, L2, ATE, SLT, CESLT, OSV, AFHC at Suzhou)
                    # These are standalone simple names under Tier0-Suzhou header
                    if (col_lower in ['l1', 'l2', 'ate', 'slt', 'ceslt', 'osv'] or 
                        'afhc at suzhou' in col_lower or 'suzhou' in col_lower or
                        any(x in col_lower for x in ['tier0', 'tier 0'])):
                        return (0, col_name)
                    
                    # Tier 1: ATE detailed tests (ATE FT1, ATE FT2, Per Core Charz)
                    elif any(x in col_lower for x in ['tier1', 'tier 1', 'ate ft', 'ft1', 'ft2', 'per core', 'core char']):
                        return (1, col_name)
                    
                    # Tier 2: SLT tests (SLT1, SLT2, SLT perCCD)
                    elif any(x in col_lower for x in ['tier2', 'tier 2', 'slt1', 'slt2', 'slt per', 'perccd']):
                        return (2, col_name)
                    
                    # Tier 3: FS1 tests
                    elif any(x in col_lower for x in ['tier3', 'tier 3', 'fs1', 'l3 repro', 'afhc det', 'repro']):
                        return (3, col_name)
                    
                    # Tier 4: Diag tests
                    elif any(x in col_lower for x in ['tier4', 'tier 4', 'diag', 'extended diag', 'shak', 'kvm']):
                        return (4, col_name)
                    
                    # Tier 5: FS2 / WL tests
                    elif any(x in col_lower for x in ['tier5', 'tier 5', 'fs2', 'wl:', 'wl ', 'variable fan', 'freq exp', 'voltage exp', 'v + freq', 'nominal']):
                        return (5, col_name)
                    
                    else:
                        # Unknown tier
                        return (99, col_name)
                
                # Sort tier columns by logical progression
                tier_columns_sorted = sorted(tier_columns, key=lambda x: get_tier_order(x[0]))
                
                logger.info(f"  Analyzing tier results in progression order:")
                
                # Analyze test results across all tiers
                has_any_failure = False
                has_any_pass = False
                has_any_not_run = False
                all_not_run = True
                
                for tier_col, tier_value in tier_columns_sorted:
                    tier_order = get_tier_order(tier_col)[0]
                    
                    is_fail = is_failure(tier_value)
                    is_pass = is_pass_value(tier_value)
                    is_not = is_not_run(tier_value)
                    
                    logger.info(f"    [Tier{tier_order}] {tier_col}: '{tier_value}' → is_fail={is_fail}, is_pass={is_pass}, is_not_run={is_not}")
                    
                    if is_fail:
                        has_any_failure = True
                        all_not_run = False
                    elif is_pass:
                        has_any_pass = True
                        all_not_run = False
                    elif is_not:
                        has_any_not_run = True
                
                logger.info(f"  Summary: has_any_pass={has_any_pass}, has_any_failure={has_any_failure}, has_any_not_run={has_any_not_run}, all_not_run={all_not_run}")
                
                # Find the first failing tier in progression order
                first_fail_tier = None
                if has_any_failure:
                    for tier_col, tier_value in tier_columns_sorted:
                        if is_failure(tier_value):
                            first_fail_tier = tier_col
                            logger.info(f"  First failure detected at: {tier_col} (value: '{tier_value}')")
                            break
                
                # Determine grouping
                logger.info(f"  Determining group assignment:")
                if not tier_columns:
                    group_key = "❓ No Tier Data"
                    logger.info(f"  → Decision: No tier columns found")
                    logger.info(f"  → Group: {group_key}")
                elif all_not_run:
                    group_key = "⏸️ Not Run - No Test Results"
                    logger.info(f"  → Decision: All tests are 'Not run'")
                    logger.info(f"  → Group: {group_key}")
                elif first_fail_tier:
                    # Simplify tier name for grouping
                    tier_name = first_fail_tier.replace(':', '').replace('_', ' ').strip()
                    group_key = f"❌ Failed at: {tier_name}"
                    logger.info(f"  → Decision: Has failure at first failing tier")
                    logger.info(f"  → Group: {group_key}")
                elif has_any_pass and not has_any_failure and not has_any_not_run:
                    # All Tiers Passed: ALL tiers must be explicitly PASS (no failures, no not-run)
                    group_key = "✅ All Tiers Passed"
                    logger.info(f"  → Decision: All tiers have explicit PASS results")
                    logger.info(f"  → Group: {group_key}")
                elif has_any_pass and not has_any_failure and has_any_not_run:
                    # Has some passes and some not-run (no failures) - treat as Not Run
                    group_key = "⏸️ Not Run - No Test Results"
                    logger.info(f"  → Decision: Has passes but also has 'Not run' tiers")
                    logger.info(f"  → Group: {group_key}")
                else:
                    group_key = "❓ No Tier Data"
                    logger.info(f"  → Decision: Edge case - no clear pass/fail pattern")
                    logger.info(f"  → Group: {group_key} (has_pass={has_any_pass}, has_fail={has_any_failure}, has_not_run={has_any_not_run})")
            
            if group_key:
                groups[group_key].append(asset)
        
        # Final summary logging for tier analysis
        if group_by == "Tier Analysis":
            logger.info("=" * 80)
            logger.info(f"TIER ANALYSIS COMPLETE - {len(groups)} groups created")
            for group_name, group_assets in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
                logger.info(f"  {group_name}: {len(group_assets)} assets")
            logger.info("=" * 80)
        
        # Display grouped data
        for group_name, group_assets in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
            with st.expander(f"**{group_name}** ({len(group_assets)} assets)", expanded=False):
                # Add Analyze button at the top
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.caption(f"Showing {min(len(group_assets), 50)} of {len(group_assets)} assets - Click on any row to see full details")
                with col2:
                    analyze_key = f"analyze_{group_name}_{len(group_assets)}"
                    if st.button("📊 Analyze", type="primary", use_container_width=True, key=analyze_key):
                        st.session_state[f'show_analytics_analysis_{group_name}'] = True
                        st.rerun()
                
                table_data = []
                display_assets = group_assets[:50]  # Show first 50
                for idx, asset in enumerate(display_assets):
                    key_cols = get_key_columns(asset)
                    table_data.append(key_cols)
                
                df = pd.DataFrame(table_data)
                
                # Display table with row selection
                selected = st.dataframe(
                    df,
                    hide_index=True,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key=f"analytics_table_{group_name}",
                    height=400  # Allow scrolling through all rows
                )
                
                # Show dialog when a row is selected
                if selected.selection.rows:
                    selected_idx = selected.selection.rows[0]
                    selected_asset = display_assets[selected_idx]
                    
                    # Use session state to control dialog opening
                    dialog_key = f'show_asset_details_{selected_asset["serial_number"]}'
                    if dialog_key not in st.session_state:
                        st.session_state[dialog_key] = True
                    
                    if st.session_state.get(dialog_key, False):
                        @st.dialog(f"Asset Details: {selected_asset['serial_number']}", width="large")
                        def show_asset_details():
                            raw_data = selected_asset.get('raw_data', {})
                            
                            st.info("ℹ️ Chinese text is automatically translated (may not be 100% accurate)")
                            
                            # Create tabs in dialog
                            tab1, tab2, tab3, tab4 = st.tabs(["🆔 Identity", "📅 Timeline", "🔧 Technical", "📄 Raw Data"])
                            
                            # Tab 1: Identity
                            with tab1:
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("Serial Number", selected_asset['serial_number'])
                                    st.metric("Source File", selected_asset.get('source_filename', 'N/A'))
                                with col2:
                                    st.metric("Source Sheet", raw_data.get('_source_sheet', 'N/A'))
                                    st.metric("Source Row", raw_data.get('_source_row', 'N/A'))
                                
                                st.markdown("---")
                                st.markdown("**System Information**")
                                
                                identity_keywords = ['system', 'cpu', 'sn', 'barcode', 'ppid', 'odm', 'location', '机房', 'vendor']
                                for key, value in raw_data.items():
                                    if not key.startswith('_') and any(kw in key.lower() for kw in identity_keywords):
                                        translated_value = translate_text(value) if value else 'N/A'
                                        st.text(f"{key}: {translated_value}")
                            
                            # Tab 2: Timeline
                            with tab2:
                                date_keywords = ['date', 'time', 'day', '日期', 'deploy', 'fail', 'rma', 'ship']
                                date_found = False
                                
                                for key, value in raw_data.items():
                                    if not key.startswith('_') and any(kw in key.lower() for kw in date_keywords):
                                        translated_value = translate_text(value) if value else 'N/A'
                                        st.metric(key, translated_value)
                                        date_found = True
                                
                                if not date_found:
                                    st.info("No timeline information available")
                                
                                st.markdown("---")
                                st.caption(f"Ingested: {selected_asset.get('ingest_timestamp', 'N/A')}")
                            
                            # Tab 3: Technical
                            with tab3:
                                tech_keywords = ['error', 'fail', 'status', 'bios', 'firmware', 'log', 'symptom', 'issue', 
                                               'test', 'code', 'version', '状态', '错误']
                                tech_found = False
                                
                                for key, value in raw_data.items():
                                    if not key.startswith('_') and any(kw in key.lower() for kw in tech_keywords):
                                        st.markdown(f"**{key}**")
                                        translated_value = translate_text(value) if value else 'N/A'
                                        st.text(str(translated_value))
                                        st.markdown("")
                                        tech_found = True
                                
                                if not tech_found:
                                    st.info("No technical details available")
                            
                            # Tab 4: Raw Data
                            with tab4:
                                st.json(raw_data)
                        
                        show_asset_details()
                        # Clear the session state to prevent re-opening
                        st.session_state[dialog_key] = False
                
                # Show analysis dialog for this group (only if explicitly triggered)
                show_dialog_key = f'show_analytics_analysis_{group_name}'
                if st.session_state.get(show_dialog_key, False):
                    # Special handler for Tier Analysis
                    if group_by == "Tier Analysis":
                        @st.dialog(f"📊 Tier Analysis: {group_name}", width="large")
                        def show_tier_analysis():
                            tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🛤️ Test Journey", "🎯 Tier Waterfall", "🗺️ Customer Journey", "📊 Tier Heatmap", "👤 Owner Workload", "🖥️ Platform Analysis", "📈 Time Trends"])
                            
                            # Extract tier columns from all assets
                            tier_keywords = ['l1', 'l2', 'ate', 'slt', 'ceslt', 'osv', 'tier0', 'tier1', 'tier2', 
                                           'tier3', 'tier4', 'tier5', 'fs1', 'fs2', 'diag', 'aft', 'wl:']
                            all_tier_cols = set()
                            for asset in group_assets:
                                raw_data = asset.get('raw_data', {})
                                for key in raw_data.keys():
                                    if not key.startswith('_'):
                                        key_lower = key.lower().strip()
                                        # Skip date/time columns that might contain 'ate' (like 'Date', 'datecode', 'Mfg Date')
                                        # But include columns with tier indicators even if they have date-like substrings
                                        is_date_col = any(x in key_lower for x in ['date', 'timestamp', 'time'])
                                        has_tier_indicator = any(x in key_lower for x in ['tier', 'test', ' l1', ' l2', ' slt', ' ate ', 'ft1', 'ft2', 'wl:'])
                                        
                                        if is_date_col and not has_tier_indicator:
                                            continue  # Skip pure date/time columns
                                        
                                        # Check if this is a tier column using flexible matching
                                        if any(kw in key_lower for kw in tier_keywords):
                                            all_tier_cols.add(key)
                            
                            all_tier_cols = sorted(all_tier_cols)
                            
                            # Tab 0: Test Journey View
                            with tab0:
                                st.markdown("### Complete Test Journey")
                                st.caption("See how each asset progressed through all test tiers - Color: 🟢 Pass | 🔴 Fail | ⚪ Not Run")
                                
                                # Build journey table
                                journey_data = []
                                for asset in group_assets[:20]:  # Limit to 20 for readability
                                    row = {'Serial Number': asset.get('serial_number', 'N/A')}
                                    raw_data = asset.get('raw_data', {})
                                    
                                    # Add customer if available
                                    customer_keywords = ['customer', 'client']
                                    for key, value in raw_data.items():
                                        if not key.startswith('_') and value and any(kw in key.lower() for kw in customer_keywords):
                                            row['Customer'] = str(value).strip().upper()[:10]
                                            break
                                    
                                    # Add all tier columns
                                    for tier_col in all_tier_cols[:15]:  # Limit to 15 tier columns for width
                                        tier_short = tier_col.replace(':', '').replace('_', ' ')[:15]
                                        value = raw_data.get(tier_col, '')
                                        
                                        if value:
                                            val_upper = str(value).strip().upper()
                                            if val_upper in ['NFT', 'NFF', 'PASS', 'PASSED']:
                                                row[tier_short] = '✅ PASS'
                                            elif val_upper in ['NOT RUN', 'N/A', 'NA', '']:
                                                row[tier_short] = '⏸️ NOT RUN'
                                            else:
                                                # Show actual failure reason (truncated)
                                                fail_reason = str(value)[:20]
                                                row[tier_short] = f'❌ {fail_reason}'
                                        else:
                                            row[tier_short] = '⏸️ NOT RUN'
                                    
                                    journey_data.append(row)
                                
                                if journey_data:
                                    df_journey = pd.DataFrame(journey_data)
                                    
                                    # Display table
                                    st.dataframe(
                                        df_journey, 
                                        use_container_width=True, 
                                        height=500
                                    )
                                    
                                    if len(group_assets) > 20:
                                        st.caption(f"ℹ️ Showing first 20 of {len(group_assets)} assets for performance")
                                    
                                    # Add download button
                                    csv = df_journey.to_csv(index=False).encode('utf-8')
                                    st.download_button(
                                        label="📥 Download Journey Data (CSV)",
                                        data=csv,
                                        file_name=f"test_journey_{group_name}.csv",
                                        mime="text/csv",
                                    )
                                else:
                                    st.info("No journey data available")
                            
                            # Tab 1: Tier Waterfall
                            with tab1:
                                st.markdown("### Test Tier Progression")
                                st.caption("Shows how many units pass/fail at each test tier")
                                
                                tier_stats = {}
                                for tier_col in all_tier_cols:
                                    pass_count = 0
                                    fail_count = 0
                                    for asset in group_assets:
                                        value = asset.get('raw_data', {}).get(tier_col, '')
                                        if value:
                                            val_upper = str(value).strip().upper()
                                            if val_upper in ['NFT', 'NFF', 'PASS', 'PASSED']:
                                                pass_count += 1
                                            elif val_upper not in ['N/A', 'NA', '']:
                                                fail_count += 1
                                    
                                    if pass_count + fail_count > 0:
                                        tier_stats[tier_col] = {'pass': pass_count, 'fail': fail_count}
                                
                                if tier_stats:
                                    fig, ax = plt.subplots(figsize=(12, max(6, len(tier_stats) * 0.5)), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    tier_names = list(tier_stats.keys())
                                    pass_counts = [tier_stats[t]['pass'] for t in tier_names]
                                    fail_counts = [tier_stats[t]['fail'] for t in tier_names]
                                    
                                    y_pos = range(len(tier_names))
                                    
                                    # Stacked horizontal bars
                                    bars1 = ax.barh(y_pos, pass_counts, color='#51cf66', label='Pass')
                                    bars2 = ax.barh(y_pos, fail_counts, left=pass_counts, color='#ff6b6b', label='Fail')
                                    
                                    ax.set_yticks(y_pos)
                                    ax.set_yticklabels([t.replace(':', '').replace('_', ' ')[:30] for t in tier_names], 
                                                       color='#ffffff', fontsize=10)
                                    ax.set_xlabel('Asset Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Test Tier Pass/Fail Distribution', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.legend(loc='upper right', facecolor='#16213e', edgecolor='white', labelcolor='white')
                                    ax.grid(axis='x', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff')
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    # Add value labels
                                    for i, (bar1, bar2) in enumerate(zip(bars1, bars2)):
                                        if bar1.get_width() > 0:
                                            ax.text(bar1.get_width()/2, bar1.get_y() + bar1.get_height()/2, 
                                                   f'{int(bar1.get_width())}', ha='center', va='center', 
                                                   fontsize=9, color='white', fontweight='bold')
                                        if bar2.get_width() > 0:
                                            ax.text(bar1.get_width() + bar2.get_width()/2, bar2.get_y() + bar2.get_height()/2, 
                                                   f'{int(bar2.get_width())}', ha='center', va='center', 
                                                   fontsize=9, color='white', fontweight='bold')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No tier progression data available")
                            
                            # Tab 2: Customer Journey
                            with tab2:
                                st.markdown("### Customer-Tier Failure Analysis")
                                st.caption("Shows which customers fail at which test tiers")
                                
                                # Extract customer info
                                customer_tier_fails = {}
                                for asset in group_assets:
                                    raw_data = asset.get('raw_data', {})
                                    
                                    # Get customer
                                    customer = 'Unknown'
                                    customer_keywords = ['customer', 'client', 'end_customer', 'end customer', 'customer_name']
                                    for key, value in raw_data.items():
                                        if not key.startswith('_') and value and any(kw in key.lower() for kw in customer_keywords):
                                            customer = str(value).strip().upper()
                                            if customer in ['N/A', 'NA', 'NONE', '']:
                                                customer = 'Unknown'
                                            break
                                    
                                    if customer not in customer_tier_fails:
                                        customer_tier_fails[customer] = Counter()
                                    
                                    # Check which tiers failed
                                    for tier_col in all_tier_cols:
                                        value = raw_data.get(tier_col, '')
                                        if value:
                                            val_upper = str(value).strip().upper()
                                            if val_upper not in ['NFT', 'NFF', 'PASS', 'PASSED', 'N/A', 'NA', '']:
                                                tier_name = tier_col.replace(':', '').replace('_', ' ')[:20]
                                                customer_tier_fails[customer][tier_name] += 1
                                
                                if customer_tier_fails:
                                    fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    customers = list(customer_tier_fails.keys())
                                    tier_names_short = list(set(tier for c in customer_tier_fails.values() for tier in c.keys()))[:10]
                                    
                                    x = range(len(tier_names_short))
                                    width = 0.8 / len(customers)
                                    colors = ['#ff6b6b', '#51cf66', '#339af0', '#ffd43b', '#cc5de8']
                                    
                                    for i, customer in enumerate(customers[:5]):  # Max 5 customers
                                        counts = [customer_tier_fails[customer].get(t, 0) for t in tier_names_short]
                                        offset = width * i - (width * len(customers) / 2)
                                        ax.bar([p + offset for p in x], counts, width, label=customer, 
                                              color=colors[i % len(colors)])
                                    
                                    ax.set_xticks(x)
                                    ax.set_xticklabels(tier_names_short, rotation=45, ha='right', color='#ffffff', fontsize=9)
                                    ax.set_ylabel('Failure Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Failures by Customer and Tier', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.legend(loc='upper right', facecolor='#16213e', edgecolor='white', labelcolor='white')
                                    ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff')
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No customer-tier correlation data available")
                            
                            # Tab 3: Tier Heatmap
                            with tab3:
                                st.markdown("### Tier Failure Intensity Heatmap")
                                st.caption("Darker colors indicate more failures")
                                
                                # Build heatmap data
                                customers = list(customer_tier_fails.keys()) if 'customer_tier_fails' in locals() else []
                                if customers and all_tier_cols:
                                    import numpy as np
                                    
                                    # Build matrix
                                    matrix_data = []
                                    tier_labels = []
                                    for tier_col in all_tier_cols[:15]:  # Max 15 tiers
                                        tier_row = []
                                        tier_labels.append(tier_col.replace(':', '').replace('_', ' ')[:20])
                                        for customer in customers[:5]:  # Max 5 customers
                                            tier_name = tier_col.replace(':', '').replace('_', ' ')[:20]
                                            count = customer_tier_fails.get(customer, Counter()).get(tier_name, 0)
                                            tier_row.append(count)
                                        matrix_data.append(tier_row)
                                    
                                    matrix = np.array(matrix_data)
                                    
                                    fig, ax = plt.subplots(figsize=(10, max(6, len(tier_labels) * 0.4)), facecolor='#1a1a2e')
                                    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
                                    
                                    ax.set_xticks(range(len(customers[:5])))
                                    ax.set_xticklabels(customers[:5], rotation=45, ha='right', color='#ffffff', fontsize=10)
                                    ax.set_yticks(range(len(tier_labels)))
                                    ax.set_yticklabels(tier_labels, color='#ffffff', fontsize=9)
                                    ax.set_title('Failure Heatmap: Customer vs Tier', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    
                                    # Add colorbar
                                    cbar = plt.colorbar(im, ax=ax)
                                    cbar.ax.yaxis.set_tick_params(color='white')
                                    cbar.outline.set_edgecolor('white')
                                    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
                                    
                                    # Add text annotations
                                    for i in range(len(tier_labels)):
                                        for j in range(len(customers[:5])):
                                            text = ax.text(j, i, int(matrix[i, j]),
                                                          ha="center", va="center", color="black" if matrix[i, j] > matrix.max()/2 else "white",
                                                          fontsize=9, fontweight='bold')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("Not enough data for heatmap visualization")
                            
                            # Tab 4: Owner Workload
                            with tab4:
                                st.markdown("### Workload by Tier Owner")
                                st.caption("Shows failure distribution across tier owners")
                                
                                # Extract owners from tier columns or status
                                owner_counts = Counter()
                                for asset in group_assets:
                                    raw_data = asset.get('raw_data', {})
                                    
                                    # Look for owner/assigned fields
                                    owner_keywords = ['owner', 'assigned', 'drew', 'yucheng', 'neha', 'mohid', 'ashish', 'pradeep']
                                    for key, value in raw_data.items():
                                        if not key.startswith('_') and value:
                                            key_lower = key.lower()
                                            val_str = str(value).strip()
                                            
                                            # Check if this is an owner field
                                            if any(kw in key_lower for kw in ['owner', 'assigned', 'status']) and any(name in val_str.lower() for name in owner_keywords):
                                                # Extract owner name
                                                for name in ['Drew', 'Yucheng', 'Neha', 'Mohid', 'Ashish', 'Pradeep', 'Inventory']:
                                                    if name.lower() in val_str.lower():
                                                        owner_counts[name] += 1
                                                        break
                                
                                if owner_counts:
                                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    owners = list(owner_counts.keys())
                                    counts = list(owner_counts.values())
                                    colors = ['#ff6b6b', '#51cf66', '#339af0', '#ffd43b', '#cc5de8', '#ff8787', '#74c0fc']
                                    
                                    bars = ax.bar(owners, counts, color=colors[:len(owners)], edgecolor='white', linewidth=1)
                                    ax.set_ylabel('Failure Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Failures by Owner/Status', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff')
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    # Add value labels
                                    for bar in bars:
                                        height = bar.get_height()
                                        ax.text(bar.get_x() + bar.get_width()/2., height,
                                               f'{int(height)}', ha='center', va='bottom',
                                               fontsize=11, color='#ffffff', fontweight='bold')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No owner/status information available")
                            
                            # Tab 5: Platform vs Tier Performance
                            with tab5:
                                st.markdown("### Platform Performance Across Tiers")
                                st.caption("Shows which platforms fail at which test tiers")
                                
                                # Extract platform info
                                platform_tier_fails = {}
                                for asset in group_assets:
                                    raw_data = asset.get('raw_data', {})
                                    
                                    # Get platform
                                    platform = 'Unknown'
                                    platform_keywords = ['platform', 'platf orm', 'model', 'type', 'sku', 'product']
                                    for key, value in raw_data.items():
                                        if not key.startswith('_') and value and any(kw in key.lower() for kw in platform_keywords):
                                            platform = str(value).strip().upper()
                                            if platform in ['N/A', 'NA', 'NONE', '']:
                                                platform = 'Unknown'
                                            break
                                    
                                    if platform not in platform_tier_fails:
                                        platform_tier_fails[platform] = Counter()
                                    
                                    # Check which tiers failed
                                    for tier_col in all_tier_cols:
                                        value = raw_data.get(tier_col, '')
                                        if value:
                                            val_upper = str(value).strip().upper()
                                            if val_upper not in ['NFT', 'NFF', 'PASS', 'PASSED', 'N/A', 'NA', '']:
                                                tier_name = tier_col.replace(':', '').replace('_', ' ')[:20]
                                                platform_tier_fails[platform][tier_name] += 1
                                
                                if platform_tier_fails and any(platform_tier_fails.values()):
                                    fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    platforms = list(platform_tier_fails.keys())
                                    tier_names_short = list(set(tier for p in platform_tier_fails.values() for tier in p.keys()))[:10]
                                    
                                    x = range(len(tier_names_short))
                                    width = 0.8 / len(platforms)
                                    colors = ['#ff6b6b', '#51cf66', '#339af0', '#ffd43b', '#cc5de8', '#ff8787']
                                    
                                    for i, platform in enumerate(platforms[:6]):  # Max 6 platforms
                                        counts = [platform_tier_fails[platform].get(t, 0) for t in tier_names_short]
                                        offset = width * i - (width * len(platforms) / 2)
                                        ax.bar([p + offset for p in x], counts, width, label=platform[:15], 
                                              color=colors[i % len(colors)])
                                    
                                    ax.set_xticks(x)
                                    ax.set_xticklabels(tier_names_short, rotation=45, ha='right', color='#ffffff', fontsize=9)
                                    ax.set_ylabel('Failure Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Failures by Platform and Tier', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.legend(loc='upper right', facecolor='#16213e', edgecolor='white', labelcolor='white', fontsize=9)
                                    ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff')
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No platform-tier correlation data available")
                            
                            # Tab 6: Time-based Tier Trends
                            with tab6:
                                st.markdown("### Tier Failure Trends Over Time")
                                st.caption("Shows failure rate per tier over time - identify bottlenecks")
                                
                                # Extract date and tier failure info
                                tier_date_fails = {}
                                for asset in group_assets:
                                    raw_data = asset.get('raw_data', {})
                                    
                                    # Get date
                                    date_str = None
                                    date_keywords = ['date', 'time', 'mfg', 'deploy', 'rma', 'fail', 'ticket']
                                    for key, value in raw_data.items():
                                        if not key.startswith('_') and value and any(kw in key.lower() for kw in date_keywords):
                                            date_str = str(value).strip()
                                            break
                                    
                                    if date_str and date_str not in ['N/A', 'NA', '']:
                                        # Parse date to month
                                        try:
                                            if ' | ' in date_str:
                                                date_str = date_str.split(' | ')[0].strip()
                                            
                                            date_formats = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', 
                                                          '%d/%m/%Y', '%Y/%m/%d', '%Y_%m', '%Y-%m']
                                            
                                            month = None
                                            for fmt in date_formats:
                                                try:
                                                    date_obj = datetime.strptime(date_str.strip(), fmt)
                                                    month = date_obj.strftime('%Y-%m')
                                                    break
                                                except:
                                                    continue
                                            
                                            if month:
                                                # Check which tiers failed
                                                for tier_col in all_tier_cols[:5]:  # Top 5 tiers
                                                    value = raw_data.get(tier_col, '')
                                                    if value:
                                                        val_upper = str(value).strip().upper()
                                                        if val_upper not in ['NFT', 'NFF', 'PASS', 'PASSED', 'N/A', 'NA', '']:
                                                            tier_name = tier_col.replace(':', '').replace('_', ' ')[:15]
                                                            if tier_name not in tier_date_fails:
                                                                tier_date_fails[tier_name] = Counter()
                                                            tier_date_fails[tier_name][month] += 1
                                        except:
                                            pass
                                
                                if tier_date_fails:
                                    # Get all unique months
                                    all_months = sorted(set(month for tier_data in tier_date_fails.values() for month in tier_data.keys()))
                                    
                                    if len(all_months) > 1:  # Need at least 2 time points for trend
                                        fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1a1a2e')
                                        ax.set_facecolor('#16213e')
                                        
                                        colors = ['#ff6b6b', '#51cf66', '#339af0', '#ffd43b', '#cc5de8']
                                        
                                        for i, (tier_name, month_counts) in enumerate(list(tier_date_fails.items())[:5]):
                                            counts = [month_counts.get(m, 0) for m in all_months]
                                            ax.plot(range(len(all_months)), counts, color=colors[i % len(colors)], 
                                                   linewidth=2.5, marker='o', markersize=7, label=tier_name,
                                                   markerfacecolor=colors[i % len(colors)], markeredgecolor='white', markeredgewidth=1.5)
                                        
                                        ax.set_xticks(range(len(all_months)))
                                        ax.set_xticklabels(all_months, rotation=45, ha='right', color='#ffffff', fontsize=9)
                                        ax.set_ylabel('Failure Count', color='#ffffff', fontsize=12, fontweight='bold')
                                        ax.set_title('Tier Failure Trends Over Time', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                        ax.legend(loc='upper left', facecolor='#16213e', edgecolor='white', labelcolor='white', fontsize=9)
                                        ax.grid(axis='both', alpha=0.2, color='white', linestyle='--')
                                        ax.tick_params(colors='#ffffff')
                                        
                                        for spine in ax.spines.values():
                                            spine.set_color('#3a4a5c')
                                        
                                        plt.tight_layout()
                                        st.pyplot(fig)
                                        plt.close()
                                        
                                        # Add insights
                                        st.markdown("---")
                                        st.markdown("### 📊 Insights")
                                        for tier_name, month_counts in list(tier_date_fails.items())[:3]:
                                            counts = [month_counts.get(m, 0) for m in all_months]
                                            if len(counts) >= 2:
                                                trend = "📈 Increasing" if counts[-1] > counts[0] else "📉 Decreasing" if counts[-1] < counts[0] else "➡️ Stable"
                                                st.caption(f"**{tier_name}**: {trend} ({counts[0]} → {counts[-1]} failures)")
                                    else:
                                        st.info("Need at least 2 time points to show trends")
                                else:
                                    st.info("No time-series data available for tier analysis")
                        
                        show_tier_analysis()
                        # Clear the session state to prevent re-opening
                        st.session_state[show_dialog_key] = False
                    
                    else:
                        # General analysis for other groupings
                        @st.dialog(f"📊 Analysis: {group_name}", width="large")
                        def show_group_analysis():
                            # Create tabs for different analyses
                            tab1, tab2, tab3, tab4 = st.tabs(["👥 By Customer", "📅 Timeline", "🔧 By Status", "⚠️ Error Types"])
                            
                            # Tab 1: Customer Distribution
                            with tab1:
                                st.markdown("### Customer Distribution")
                                customer_counts = Counter()
                                
                                for asset in group_assets:
                                    raw_data = asset.get('raw_data', {})
                                    customer_keywords = ['customer', 'client', 'end_customer', 'end customer', 
                                                       'customer_name', 'customer name', '客户', 'cust']
                                    customer_found = False
                                    for key, value in raw_data.items():
                                        if not key.startswith('_') and value and any(kw in key.lower() for kw in customer_keywords):
                                            customer_name = str(value).strip().upper()
                                            if customer_name and customer_name not in ['N/A', 'NA', 'NONE', '']:
                                                customer_counts[customer_name] += 1
                                                customer_found = True
                                                break
                                    if not customer_found:
                                        customer_counts['Unknown'] += 1
                                
                                if customer_counts:
                                    sorted_customers = sorted(customer_counts.items(), key=lambda x: x[1], reverse=True)
                                    customers = [x[0] for x in sorted_customers]
                                    counts = [x[1] for x in sorted_customers]
                                    
                                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    colors = ['#ff6b6b', '#51cf66', '#339af0', '#cc5de8', '#ffd43b', 
                                             '#ff8787', '#ffa94d', '#74c0fc', '#b197fc', '#ffc9c9']
                                    
                                    bars = ax.barh(customers, counts, color=colors[:len(customers)], 
                                                  edgecolor='white', linewidth=0.5)
                                    ax.set_xlabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Assets by Customer', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.invert_yaxis()
                                    ax.grid(axis='x', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff', labelsize=10)
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    for i, bar in enumerate(bars):
                                        width = bar.get_width()
                                        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2., 
                                               f'{int(width)}', ha='left', va='center', 
                                               fontsize=11, color='#ffffff', fontweight='bold')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No customer data available")
                            
                            # Tab 2: Timeline Analysis
                            with tab2:
                                st.markdown("### Timeline Analysis")
                                date_months = []
                                
                                for asset in group_assets:
                                    key_cols = get_key_columns(asset)
                                    date_str = key_cols.get('Date', '')
                                    
                                    if date_str and date_str != 'N/A':
                                        try:
                                            if ' | ' in str(date_str):
                                                date_str = str(date_str).split(' | ')[0].strip()
                                            
                                            date_formats = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', 
                                                          '%d/%m/%Y', '%Y/%m/%d', '%Y_%m', '%Y-%m']
                                            
                                            for fmt in date_formats:
                                                try:
                                                    date_obj = datetime.strptime(str(date_str).strip(), fmt)
                                                    date_months.append(date_obj.strftime('%Y-%m'))
                                                    break
                                                except:
                                                    continue
                                        except:
                                            pass
                                
                                if date_months:
                                    month_counts = Counter(date_months)
                                    sorted_months = dict(sorted(month_counts.items()))
                                    
                                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    months_list = list(sorted_months.keys())
                                    values_list = list(sorted_months.values())
                                    
                                    ax.plot(range(len(months_list)), values_list, color='#51cf66', linewidth=3, 
                                           marker='o', markersize=8, markerfacecolor='#51cf66', 
                                           markeredgecolor='white', markeredgewidth=2)
                                    ax.fill_between(range(len(months_list)), values_list, alpha=0.3, color='#51cf66')
                                    
                                    ax.set_xticks(range(len(months_list)))
                                    ax.set_xticklabels(months_list, rotation=45, ha='right', color='#ffffff', fontsize=10)
                                    ax.set_ylabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Asset Trend Over Time', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff', labelsize=10)
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    for i, value in enumerate(values_list):
                                        ax.text(i, value + max(values_list)*0.02, f'{int(value)}', 
                                               ha='center', va='bottom', fontsize=10, color='#ffffff', fontweight='bold')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No date data available")
                            
                            # Tab 3: Status Distribution
                            with tab3:
                                st.markdown("### Status Distribution")
                                status_counts = Counter()
                                
                                for asset in group_assets:
                                    key_cols = get_key_columns(asset)
                                    status = key_cols.get('Status', 'Unknown')
                                    if status and status != 'N/A':
                                        status_counts[status] += 1
                                
                                if status_counts:
                                    sorted_status = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
                                    statuses = [x[0] for x in sorted_status]
                                    counts = [x[1] for x in sorted_status]
                                    
                                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    colors = ['#ffd43b', '#ffc107', '#ffb300', '#ffa000', '#ff8f00',
                                             '#ff6f00', '#fb8c00', '#f57c00', '#ef6c00', '#e65100']
                                    
                                    bars = ax.bar(range(len(statuses)), counts, color=colors[:len(statuses)], 
                                                 edgecolor='white', linewidth=0.5, width=0.7)
                                    
                                    ax.set_xticks(range(len(statuses)))
                                    ax.set_xticklabels(statuses, rotation=45, ha='right', 
                                                      fontsize=10, fontweight='bold', color='#ffffff')
                                    ax.set_ylabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Assets by Status', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff', labelsize=10)
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    for i, bar in enumerate(bars):
                                        height = bar.get_height()
                                        ax.text(bar.get_x() + bar.get_width()/2, height,
                                               f'{int(height)}', ha='center', va='bottom', 
                                               fontsize=10, color='#ffffff', fontweight='bold')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No status data available")
                            
                            # Tab 4: Error Type Breakdown
                            with tab4:
                                st.markdown("### Error Type Breakdown")
                                error_counts = Counter()
                                
                                for asset in group_assets:
                                    key_cols = get_key_columns(asset)
                                    error_type = key_cols.get('Error', 'Unknown')
                                    if error_type and error_type != 'N/A':
                                        error_counts[error_type] += 1
                                
                                if error_counts:
                                    top_errors = dict(error_counts.most_common(10))
                                    
                                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                                    ax.set_facecolor('#16213e')
                                    
                                    colors = ['#ff6b6b', '#ee5a6f', '#f06595', '#cc5de8', '#845ef7', 
                                             '#5c7cfa', '#339af0', '#22b8cf', '#20c997', '#51cf66']
                                    
                                    bars = ax.barh(list(top_errors.keys()), list(top_errors.values()), 
                                                  color=colors[:len(top_errors)], edgecolor='white', linewidth=0.5)
                                    ax.set_xlabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                                    ax.set_title('Top 10 Error Types', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                                    ax.grid(axis='x', alpha=0.2, color='white', linestyle='--')
                                    ax.tick_params(colors='#ffffff', labelsize=10)
                                    
                                    for spine in ax.spines.values():
                                        spine.set_color('#3a4a5c')
                                    
                                    for bar in bars:
                                        width = bar.get_width()
                                        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, 
                                               f'{int(width)}', ha='left', va='center', 
                                               fontsize=11, color='#ffffff', fontweight='bold')
                                    
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                    plt.close()
                                else:
                                    st.info("No error data available")
                            
                            # Close button
                            if st.button("✖ Close", type="secondary", use_container_width=True):
                                st.session_state[f'show_analytics_analysis_{group_name}'] = False
                                st.rerun()
                        
                        show_group_analysis()
                        # Clear the session state to prevent re-opening
                        st.session_state[show_dialog_key] = False
                
                if len(group_assets) > 50:
                    st.caption(f"Note: Limited to 50 assets per group for performance")
    else:
        st.info("🎯 No assets available for analytics. Upload data from the **Ingest Data** page to get started!")


# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Silicon Trace v3.0 | Built with FastAPI & Streamlit"
    "</div>",
    unsafe_allow_html=True
)
