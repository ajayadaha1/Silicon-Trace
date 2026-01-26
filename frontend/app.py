"""
Silicon Trace - Hardware Failure Analysis Dashboard

A Streamlit frontend for ingesting Excel files and tracing hardware assets.
"""

import streamlit as st
import requests
import pandas as pd
from typing import Optional, Dict, Any, List
import json


# Configuration
BACKEND_URL = "http://localhost:8000"

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
    st.markdown("Search for assets by serial number or keyword.")
    
    # Search input
    # Search input
    search_query = st.text_input(
        "🔍 Enter Serial Number or Search Term",
        placeholder="e.g., ABC12345XYZ",
        help="Enter a serial number or search term to find assets",
        key="search_input"
    )
    
    # Search and Clear buttons below the search box
    btn_col1, btn_col2 = st.columns([1, 1])
    
    with btn_col1:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    
    with btn_col2:
        clear_button = st.button("✖ Clear", type="secondary", use_container_width=True)
    
    # Handle clear button
    if clear_button:
        st.rerun()
    
    # Perform search if query exists and button clicked
    if search_query and search_button:
        with st.spinner("Searching..."):
            # Try exact match first
            asset = search_asset(search_query)
            
            if asset:
                st.success(f"✓ Found exact match: **{asset['serial_number']}**")
                
                # Display asset card
                display_asset_card(asset)
                
                # Display raw data in expandable section
                st.markdown("---")
                st.subheader("📋 Raw Data Verification")
                st.markdown("Original Excel row data (JSON format):")
                
                # Pretty print JSON
                st.json(asset['raw_data'])
                
                # Option to download raw data
                raw_json = json.dumps(asset['raw_data'], indent=2)
                st.download_button(
                    label="Download Raw Data (JSON)",
                    data=raw_json,
                    file_name=f"{asset['serial_number']}_raw_data.json",
                    mime="application/json"
                )
                
            else:
                # Try fuzzy search
                st.info("🔍 No exact match. Searching for similar assets...")
                search_results = search_assets(search_query)
                
                if search_results and search_results.get('total', 0) > 0:
                    st.success(f"✓ Found {search_results['total']} matching asset(s)")
                    
                    # Display results in table format
                    assets_list = []
                    for result_asset in search_results['assets']:
                        asset_row = {
                            'Serial Number': result_asset['serial_number'],
                            'Ingested': result_asset['ingest_timestamp'][:10],
                            'Source File': result_asset['source_filename']
                        }
                        # Add columns from raw_data
                        if result_asset.get('raw_data'):
                            for key, value in result_asset['raw_data'].items():
                                if not key.startswith('_'):
                                    asset_row[key] = str(value) if value is not None else 'N/A'
                        assets_list.append(asset_row)
                    
                    results_df = pd.DataFrame(assets_list)
                    st.dataframe(
                        results_df,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.warning(f"❌ No assets found matching '{search_query}'")
                    st.info("💡 Tips:\n- Try a shorter search term\n- Check spelling\n- Upload more data files")
    
    elif search_button and not search_query:
        st.warning("⚠️ Please enter a search term")
    
    # File Management & Filtering Section
    st.markdown("---")
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
    
    # All Assets Table
    st.markdown("---")
    st.subheader("All Assets" if not selected_files else f"Assets from {len(selected_files)} file(s)")
    
    with st.spinner("Loading assets..."):
        data = get_assets_filtered(source_files=selected_files)
        
        if data and data.get('total', 0) > 0:
            # Create a dynamic table with ALL columns from raw_data
            assets_list = []
            for a in data['assets']:
                # Start with basic info
                asset_row = {
                    'Serial Number': a['serial_number'],
                    'Ingested': a['ingest_timestamp'][:10],
                    'Source File': a['source_filename']
                }
                # Add all columns from raw_data
                if a.get('raw_data'):
                    for key, value in a['raw_data'].items():
                        # Skip metadata fields
                        if not key.startswith('_'):
                            # Convert all values to strings to avoid Arrow type errors
                            asset_row[key] = str(value) if value is not None else 'N/A'
                assets_list.append(asset_row)
            
            assets_df = pd.DataFrame(assets_list)
            
            st.success(f"✓ Loaded {len(assets_df)} assets")
            st.dataframe(
                assets_df,
                use_container_width=True,
                hide_index=True
            )
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
