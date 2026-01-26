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


def get_assets_filtered(source_files: List[str] = None, limit: int = 1000) -> Optional[Dict[str, Any]]:
    """Get assets with optional filtering by source files"""
    try:
        params = {"limit": limit}
        if source_files:
            params["source_files"] = ",".join(source_files)
        
        response = requests.get(f"{BACKEND_URL}/assets", params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch assets")
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
        'date': ['date', 'fail_date', 'failure_date', 'failure date', 'fail date', 
                 '日期', '故障日期', 'deploy_date', 'deployment_date'],
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
st.markdown('<div class="main-header">🔍 Silicon Trace v2.0</div>', unsafe_allow_html=True)
st.markdown("**Hardware Failure Analysis Dashboard** - Real-time insights and analytics")

# Sidebar Navigation
with st.sidebar:
    # Add some spacing at top
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Navigation menu with icons
    pages = [
        {"icon": "🏠", "label": "Dashboard", "page": "Dashboard"},
        {"icon": "📤", "label": "Ingest Data", "page": "Ingest"},
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
        "Silicon Trace v2.0 intelligently parses Excel files with inconsistent headers "
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
        
        # Extract metrics
        error_counts = Counter()
        status_counts = Counter()
        customer_counts = Counter()
        date_months = []
        
        for asset in assets:
            key_cols = get_key_columns(asset)
            raw_data = asset.get('raw_data', {})
            
            # Count errors
            error_type = key_cols.get('Error', 'Unknown')
            if error_type and error_type != 'N/A':
                error_counts[error_type] += 1
            
            # Count status
            status = key_cols.get('Status', 'Unknown')
            if status and status != 'N/A':
                status_counts[status] += 1
            
            # Extract customer
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
            
            # Extract month
            date_str = key_cols.get('Date', '')
            if date_str and date_str != 'N/A':
                try:
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                        try:
                            date_obj = datetime.strptime(str(date_str).split()[0], fmt)
                            date_months.append(date_obj.strftime('%Y-%m'))
                            break
                        except:
                            continue
                except:
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
        
        # Graph 1: Failures by Error Type
        with col1:
            st.subheader("📊 Failures by Error Type")
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
                           f'{int(width)}', ha='left', va='center', fontsize=11, 
                           color='#ffffff', fontweight='bold')
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            else:
                st.info("No error data available")
        
        # Graph 2: Assets by Month
        with col2:
            st.subheader("📅 Assets by Month")
            if month_counts:
                sorted_months = dict(sorted(month_counts.items()))
                
                fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                ax.set_facecolor('#16213e')
                
                # Line chart for trend
                months_list = list(sorted_months.keys())
                values_list = list(sorted_months.values())
                
                ax.plot(months_list, values_list, color='#51cf66', linewidth=3, 
                       marker='o', markersize=8, markerfacecolor='#51cf66', 
                       markeredgecolor='white', markeredgewidth=2)
                
                # Fill area under the line
                ax.fill_between(range(len(months_list)), values_list, alpha=0.3, color='#51cf66')
                
                ax.set_xticks(range(len(months_list)))
                ax.set_xticklabels(months_list, rotation=45, ha='right', color='#ffffff', fontsize=10)
                ax.set_ylabel('Count', color='#ffffff', fontsize=12, fontweight='bold')
                ax.set_title('Asset Trend Over Time', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                ax.tick_params(colors='#ffffff', labelsize=10)
                
                for spine in ax.spines.values():
                    spine.set_color('#3a4a5c')
                
                # Add value labels on points
                for i, (month, value) in enumerate(zip(months_list, values_list)):
                    ax.text(i, value + max(values_list)*0.02, f'{int(value)}', 
                           ha='center', va='bottom', fontsize=10, color='#ffffff', fontweight='bold')
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            else:
                st.info("No date data available")
        
        # Second row of graphs
        col3, col4 = st.columns(2)
        
        # Graph 3: Assets by Status
        with col3:
            st.subheader("🔧 Assets by Status")
            if status_counts:
                top_status = dict(status_counts.most_common(10))
                
                fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
                ax.set_facecolor('#16213e')  # Match dark theme like other graphs
                
                # Vertical bars with varied colors
                colors = ['#ffd43b', '#ffc107', '#ffb300', '#ffa000', '#ff8f00',
                         '#ff6f00', '#fb8c00', '#f57c00', '#ef6c00', '#e65100']
                
                bars = ax.bar(range(len(top_status)), list(top_status.values()), 
                             color=colors[:len(top_status)], edgecolor='white', linewidth=0.5, width=0.7)
                
                ax.set_xticks(range(len(top_status)))
                ax.set_xticklabels(list(top_status.keys()), rotation=45, ha='right', 
                                  fontsize=10, fontweight='bold', color='#ffffff')
                ax.set_ylabel('Total Assets', color='#ffffff', fontsize=12, fontweight='bold')
                ax.set_title('Assets by Status', color='#ffffff', fontsize=14, fontweight='bold', pad=15)
                ax.grid(axis='y', alpha=0.2, color='white', linestyle='--')
                ax.tick_params(axis='x', colors='#ffffff', labelsize=10)
                ax.tick_params(axis='y', colors='#ffffff', labelsize=10)
                
                for spine in ax.spines.values():
                    spine.set_color('#3a4a5c')
                
                # Add value labels on top of bars
                for i, bar in enumerate(bars):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, height,
                           f'{int(height)}', ha='center', va='bottom', fontsize=10, 
                           color='#ffffff', fontweight='bold')
                
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
    st.markdown("Upload Excel files containing hardware asset data. The system will automatically detect serial numbers.")
    
    uploaded_files = st.file_uploader(
        "Choose Excel file(s)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Upload .xlsx or .xls files with asset data"
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
    
    selected_files = None
    source_files_data = get_source_files()
    
    if source_files_data and len(source_files_data) > 0:
        mgmt_col1, mgmt_col2 = st.columns([2, 1])
        
        with mgmt_col1:
            st.markdown("**Filter by Source Files**")
            file_options = {
                f"{sf['filename']} ({sf['asset_count']} assets)": sf['filename'] 
                for sf in source_files_data
            }
            
            selected_display = st.multiselect(
                "Select files to display",
                options=list(file_options.keys()),
                help="Filter assets by source file",
                label_visibility="collapsed"
            )
            
            selected_files = [file_options[display] for display in selected_display] if selected_display else None
        
        with mgmt_col2:
            st.markdown("**Delete Source File**")
            delete_file_display = st.selectbox(
                "Select file to delete",
                options=["-- Select file --"] + list(file_options.keys()),
                help="Delete all assets from a source file",
                label_visibility="collapsed"
            )
            
            if delete_file_display != "-- Select file --":
                delete_filename = file_options[delete_file_display]
                if st.button("🗑️ Delete File Data", type="secondary", use_container_width=True):
                    with st.spinner(f"Deleting {delete_filename}..."):
                        result = delete_source_file(delete_filename)
                        if result and result.get('success'):
                            st.success(f"✓ {result['message']}")
                            st.rerun()

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
    st.markdown("Search for assets by serial number or keyword.")

    # Initialize search query in session state if not exists
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""
    
    # Search input (without key to avoid modification error)
    search_query = st.text_input(
        "Enter Serial Number or Search Term",
        value=st.session_state.search_query,
        placeholder="e.g., ABC12345XYZ or ALIBABA",
        help="Enter a serial number or search term to filter assets below"
    )
    
    # Search and Clear buttons below the search box
    btn_col1, btn_col2 = st.columns([1, 1])
    
    with btn_col1:
        search_button = st.button("🔍 Filter", type="primary", use_container_width=True)
    
    with btn_col2:
        clear_button = st.button("✖ Clear", type="secondary", use_container_width=True)
    
    # Handle clear button - must be before using search_query
    if clear_button:
        st.session_state.search_query = ""
        st.rerun()
    
    # Update session state with current search query
    st.session_state.search_query = search_query
    
    # Show active filter status
    if search_query:
        st.info(f"🔍 Active filter: **{search_query}** (showing filtered results in table below)")
    
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
        
        # Apply search filter if query exists
        if search_query and data and data.get('total', 0) > 0:
                all_assets = data['assets']
                filtered_assets = []
                search_lower = search_query.lower()
                
                for asset in all_assets:
                    # Check if search term matches serial number, error_type, status
                    if search_lower in asset.get('serial_number', '').lower():
                        filtered_assets.append(asset)
                        continue
                    if asset.get('error_type') and search_lower in asset.get('error_type', '').lower():
                        filtered_assets.append(asset)
                        continue
                    if asset.get('status') and search_lower in asset.get('status', '').lower():
                        filtered_assets.append(asset)
                        continue
                    
                    # Check raw_data fields
                    raw_data = asset.get('raw_data', {})
                    for key, value in raw_data.items():
                        if value and search_lower in str(value).lower():
                            filtered_assets.append(asset)
                            break
                
                # Update data with filtered results
                data = {
                    'total': len(filtered_assets),
                    'assets': filtered_assets
                }
                
                if len(filtered_assets) == 0:
                    st.warning(f"❌ No assets found matching '{search_query}'")
                else:
                    st.success(f"✓ Found {len(filtered_assets)} asset(s) matching '{search_query}'")
    
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
                key="asset_table"
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
                key="complete_asset_table"
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
    
    # Get all assets for analytics
    data = get_assets_filtered(source_files=None)
    
    if data and data.get('total', 0) > 0:
        assets = data['assets']
        
        # Add grouping selector
        group_by = st.radio(
            "Group By",
            options=["Error Type", "Month", "Status", "Customer"],
            horizontal=True,
            help="Select field to group assets by"
        )
        
        st.markdown("---")
        st.caption(f"Assets grouped by {group_by.lower()}")
        
        # Group assets by selected field
        from collections import defaultdict
        groups = defaultdict(list)
        
        for asset in assets:
            key_cols = get_key_columns(asset)
            raw_data = asset.get('raw_data', {})
            
            if group_by == "Error Type":
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
            
            if group_key:
                groups[group_key].append(asset)
        
        # Display grouped data
        for group_name, group_assets in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
            with st.expander(f"**{group_name}** ({len(group_assets)} assets)", expanded=False):
                # Show sample assets
                sample_data = []
                for asset in group_assets[:10]:  # Show first 10
                    key_cols = get_key_columns(asset)
                    sample_data.append(key_cols)
                
                df = pd.DataFrame(sample_data)
                st.dataframe(df, hide_index=True, use_container_width=True)
                
                if len(group_assets) > 10:
                    st.caption(f"Showing 10 of {len(group_assets)} assets")
    else:
        st.info("🎯 No assets available for analytics. Upload data from the **Ingest Data** page to get started!")


# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Silicon Trace v2.0 | Built with FastAPI & Streamlit"
    "</div>",
    unsafe_allow_html=True
)
