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
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .asset-card {
        padding: 1.5rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 1rem 0;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
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
                result[display_name] = str(value) if value else 'N/A'
                break
    
    return result
    with col1:
        st.markdown("**Source File**")
        st.write(asset.get('source_filename', 'N/A'))
    with col2:
        st.markdown("**Ingested At**")
        st.write(asset.get('ingest_timestamp', 'N/A'))
    
    st.markdown('</div>', unsafe_allow_html=True)


# Main App Header
st.markdown('<div class="main-header">🔍 Silicon Trace</div>', unsafe_allow_html=True)
st.markdown("**Hardware Failure Analysis Tool** - Ingest Excel data and trace assets")

# Sidebar - Connection Status
with st.sidebar:
    st.header("System Status")
    
    backend_status = check_backend_health()
    
    if backend_status:
        st.success("✓ Backend Connected")
    else:
        st.error("✗ Backend Offline")
        st.info(f"Make sure the backend is running at {BACKEND_URL}")
    
    st.markdown("---")
    st.markdown("### About")
    st.info(
        "Silicon Trace intelligently parses Excel files with inconsistent headers "
        "to extract hardware asset information. The system automatically detects "
        "serial number columns using heuristic scoring."
    )

# Main Content - Tabs
tab1, tab2 = st.tabs(["📤 Ingest Data", "🔎 Trace Assets"])

# TAB 1: Ingest Data
with tab1:
    st.header("Upload Excel Files")
    st.markdown("Upload one or more Excel files containing hardware asset data. The system will automatically detect serial numbers.")
    
    uploaded_files = st.file_uploader(
        "Choose Excel file(s)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Upload .xlsx or .xls files with asset data (multiple files supported)"
    )
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} file(s) selected")
        
        # Show file details
        for file in uploaded_files:
            st.text(f"  • {file.name} ({file.size:,} bytes)")
        
        if st.button("🚀 Process Files", type="primary", use_container_width=True):
            # Track overall results
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
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.success(f"✓ Successfully processed {success_count}/{len(uploaded_files)} file(s)")
                
                # Display metrics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Rows Processed", total_processed)
                with col2:
                    st.metric("New Assets", total_created)
                with col3:
                    st.metric("Updated Assets", total_updated)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                if success_count == len(uploaded_files):
                    st.balloons()
            
            if failed_files:
                st.markdown('<div class="error-box">', unsafe_allow_html=True)
                st.error(f"✗ Failed to process {len(failed_files)} file(s):")
                for fname in failed_files:
                    st.text(f"  • {fname}")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### Expected File Format")
    st.markdown("""
    The Excel file should contain:
    - **Serial Number Column**: Headers like 'SN', 'Serial', 'Barcode', 'PPID', '2D', etc.
    - **Optional Columns**: Error Type, Status, or other asset information
    
    The system will automatically detect which column contains serial numbers.
    """)

# TAB 2: Trace Assets
with tab2:
    st.header("Trace Hardware Assets")
    
    # Section 1: File Management (TOP)
    st.subheader("📂 File Management & Filtering")
    
    # Initialize selected_files
    selected_files = None
    
    # Get list of source files
    source_files_data = get_source_files()
    
    if source_files_data and len(source_files_data) > 0:
        # Create two columns for file management
        mgmt_col1, mgmt_col2 = st.columns([2, 1])
        
        with mgmt_col1:
            st.markdown("**Filter by Source Files**")
            # Create multiselect with file info
            file_options = {
                f"{sf['filename']} ({sf['asset_count']} assets)": sf['filename'] 
                for sf in source_files_data
            }
            
            selected_display = st.multiselect(
                "Select files to display (leave empty for all)",
                options=list(file_options.keys()),
                help="Select one or more files to filter the asset table"
            )
            
            # Convert display names back to actual filenames
            selected_files = [file_options[display] for display in selected_display] if selected_display else None
        
        with mgmt_col2:
            st.markdown("**Delete Source File**")
            delete_file_display = st.selectbox(
                "Select file to delete",
                options=["-- Select file --"] + list(file_options.keys()),
                help="Delete all assets from a specific source file"
            )
            
            if delete_file_display != "-- Select file --":
                delete_filename = file_options[delete_file_display]
                if st.button("🗑️ Delete File Data", type="secondary", use_container_width=True):
                    with st.spinner(f"Deleting {delete_filename}..."):
                        result = delete_source_file(delete_filename)
                        if result and result.get('success'):
                            st.success(f"✓ {result['message']}")
                            st.rerun()
    
    # Section 2: Search (MIDDLE)
    st.markdown("---")
    st.subheader("🔍 Search Assets")
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
        options=["📋 List View", "📄 Complete View", "📊 Aggregate View", "📈 Graph View"],
        horizontal=True,
        help="Switch between simplified list, complete data, aggregated summary, and visual graphs"
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

            
            elif view_mode == "📊 Aggregate View":
                # Aggregate View: Group by error type
                st.caption("Assets grouped by error type")
                
                # Group assets by error type
                from collections import defaultdict
                groups = defaultdict(list)
                
                for asset in assets:
                    key_cols = get_key_columns(asset)
                    error_type = key_cols['Error']
                    groups[error_type].append(asset)
                
                # Sort by count (descending)
                sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
                
                # Display groups
                for error_type, group_assets in sorted_groups:
                    with st.expander(f"**{error_type}** ({len(group_assets)} assets)"):
                        # Show serial numbers in this group
                        sn_list = [asset['serial_number'] for asset in group_assets]
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(", ".join(sn_list[:10]))
                            if len(sn_list) > 10:
                                st.caption(f"... and {len(sn_list) - 10} more")
                        
                        with col2:
                            st.metric("Total Count", len(group_assets))
                        
                        # Show detailed list button
                        if st.button(f"Show all {len(group_assets)} assets", key=f"show_{error_type}"):
                            st.markdown("**Assets in this group:**")
                            group_table = []
                            for ga in group_assets:
                                key_cols = get_key_columns(ga)
                                group_table.append(key_cols)
                            
                            group_df = pd.DataFrame(group_table)
                            st.dataframe(
                                group_df[['Serial Number', 'Date', 'Status', 'Component']],
                                width='stretch',
                                hide_index=True
                            )
            
            elif view_mode == "📈 Graph View":
                # Graph View: Show visualizations
                st.caption("Visual analysis of asset data")
                
                # Extract data for graphs
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
                    
                    # Intelligently extract customer from raw_data
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
                    
                    # Extract month from date
                    date_str = key_cols.get('Date', '')
                    if date_str and date_str != 'N/A':
                        try:
                            # Try different date formats
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
                
                # Create graphs in 2-column layout
                col1, col2 = st.columns(2)
                
                # Graph 1: Failures by Error Type
                with col1:
                    st.subheader("📊 Failures by Error Type")
                    if error_counts:
                        # Sort by count and take top 10
                        top_errors = dict(error_counts.most_common(10))
                        
                        fig, ax = plt.subplots(figsize=(10, 6))
                        bars = ax.barh(list(top_errors.keys()), list(top_errors.values()), color='#1f77b4')
                        ax.set_xlabel('Count')
                        ax.set_title('Top 10 Error Types')
                        ax.grid(axis='x', alpha=0.3)
                        
                        # Add value labels on bars
                        for bar in bars:
                            width = bar.get_width()
                            ax.text(width, bar.get_y() + bar.get_height()/2, 
                                   f'{int(width)}', ha='left', va='center', fontsize=9)
                        
                        plt.tight_layout()
                        st.pyplot(fig)
                        plt.close()
                    else:
                        st.info("No error data available")
                
                # Graph 2: Assets by Month
                with col2:
                    st.subheader("📅 Assets by Month")
                    if month_counts:
                        # Sort by month
                        sorted_months = dict(sorted(month_counts.items()))
                        
                        fig, ax = plt.subplots(figsize=(10, 6))
                        bars = ax.bar(range(len(sorted_months)), list(sorted_months.values()), color='#2ca02c')
                        ax.set_xticks(range(len(sorted_months)))
                        ax.set_xticklabels(list(sorted_months.keys()), rotation=45, ha='right')
                        ax.set_ylabel('Count')
                        ax.set_title('Assets by Month')
                        ax.grid(axis='y', alpha=0.3)
                        
                        # Add value labels on bars
                        for i, bar in enumerate(bars):
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width()/2, height,
                                   f'{int(height)}', ha='center', va='bottom', fontsize=9)
                        
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
                        # Sort by count
                        top_status = dict(status_counts.most_common(10))
                        
                        fig, ax = plt.subplots(figsize=(10, 6))
                        bars = ax.barh(list(top_status.keys()), list(top_status.values()), color='#ff7f0e')
                        ax.set_xlabel('Count')
                        ax.set_title('Top 10 Status Types')
                        ax.grid(axis='x', alpha=0.3)
                        
                        # Add value labels on bars
                        for bar in bars:
                            width = bar.get_width()
                            ax.text(width, bar.get_y() + bar.get_height()/2,
                                   f'{int(width)}', ha='left', va='center', fontsize=9)
                        
                        plt.tight_layout()
                        st.pyplot(fig)
                        plt.close()
                    else:
                        st.info("No status data available")
                
                # Graph 4: Assets by Customer
                with col4:
                    st.subheader("🏢 Assets by Customer")
                    if customer_counts and len(customer_counts) > 1 or (len(customer_counts) == 1 and 'Unknown' not in customer_counts):
                        # Sort by count and exclude 'Unknown' if we have other customers
                        filtered_customers = {k: v for k, v in customer_counts.items() if k != 'Unknown'} if len(customer_counts) > 1 else customer_counts
                        
                        if filtered_customers:
                            # Sort by count and take top 10
                            sorted_customers = sorted(filtered_customers.items(), key=lambda x: x[1], reverse=True)[:10]
                            customers = [x[0] for x in sorted_customers]
                            counts = [x[1] for x in sorted_customers]
                            
                            fig, ax = plt.subplots(figsize=(10, 6))
                            bars = ax.barh(customers, counts, color='#9467bd')  # Purple color
                            ax.set_xlabel('Count')
                            ax.set_title('Top 10 Customers')
                            ax.invert_yaxis()
                            
                            # Add count labels on the bars
                            for bar in bars:
                                width = bar.get_width()
                                ax.text(width, bar.get_y() + bar.get_height()/2., 
                                       f'{int(width)}',
                                       ha='left', va='center', fontsize=9, 
                                       bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
                            
                            plt.tight_layout()
                            st.pyplot(fig)
                            plt.close()
                        else:
                            st.info("No customer data available")
                    else:
                        st.info("No customer data available - check for columns like 'end_customer', 'customer', 'client'")
                
                # Summary statistics
                st.markdown("---")
                st.subheader("📈 Summary Statistics")
                stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
                
                with stat_col1:
                    st.metric("Total Assets", len(assets))
                with stat_col2:
                    st.metric("Unique Errors", len(error_counts))
                with stat_col3:
                    st.metric("Status Types", len(status_counts))
                with stat_col4:
                    st.metric("Customers", len([k for k in customer_counts.keys() if k != 'Unknown']))
        
        else:
            if selected_files:
                st.info(f"No assets found from selected file(s).")
            else:
                st.info("No assets in the database yet. Upload a file to get started!")


# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Silicon Trace v1.0.0 | Built with FastAPI & Streamlit"
    "</div>",
    unsafe_allow_html=True
)
