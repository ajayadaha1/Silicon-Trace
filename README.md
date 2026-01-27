# 🔍 Silicon Trace v3.0

**Hardware Failure Analysis Tool**

A powerful local application for intelligent parsing and analysis of hardware failure data from Excel and PowerPoint files. Built with FastAPI, PostgreSQL, and Streamlit.

## ✨ Key Features

### 🎯 Intelligent Data Processing (v3.0)
- **Smart Multi-Format Parser**: Automatically processes Excel (.xlsx, .xls) and PowerPoint (.pptx) files
- **PowerPoint OCR Support**: Multi-phase extraction from native tables, text boxes, and image-based content
- **Smart Excel Parser**: Automatically detects serial number columns using heuristic scoring
- **Multi-Sheet Support**: Combines data from multiple Excel sheets based on serial numbers
- **Multi-File Merging**: Upload multiple files with overlapping serial numbers - data is intelligently merged and consolidated
- **CPU SN Format Priority**: Prioritizes CPU serial number format (e.g., `9AMA377P50091_100-000001359`)
- **Duplicate Prevention**: Prevents re-uploading the same file to avoid data duplication
- **Column Normalization**: Merges duplicate columns with case/spacing differences (e.g., " FA status " and "FA status")

### 📊 Advanced Dashboard (v3.0)
- **Modern Dark Theme**: High-contrast visualizations optimized for readability
- **Customer Segmentation**: All 3 graphs show customer breakdown with stacked visualizations
  - Top 10 Failure Types (Horizontal stacked bars by customer)
  - Asset Trend Over Time (Stacked area chart by customer)
  - Assets by Status (Vertical stacked bars by customer)
- **Customer Colors**: Consistent color mapping across all graphs (Alibaba=red, Tencent=green, etc.)
- **Intelligent Status Extraction**: Smart parsing of messy status fields with pattern matching
- **Chinese Translation**: Automatic detection and translation of Chinese characters to English
- **Serial Number Filtering**: Removes serial number clutter from status labels

### 🔍 Data Management (v3.0)
- **Multi-Criteria Search**: Build complex search queries with AND/OR logic operators
  - Example: "ALIBABA" AND "L1" returns only assets matching both criteria
  - Example: "Cache" OR "Memory" returns assets matching either criterion
- **Logical Chain Display**: Visual representation of search filters with color-coded operators
- **Dynamic Column Display**: Shows all captured columns from your Excel/PowerPoint files
- **Source Tracking**: Tracks which sheets and files contributed data for each serial number
- **Complete View**: See all assets with every captured field (up to 50,000 assets)
- **Scrollable Tables**: Large datasets displayed with 600px scrollable containers
- **Technical Data Tab**: View raw data with metadata about source files and sheets
- **File-Based Filtering**: Filter assets by source file
- **Bulk Delete**: Select and delete multiple files at once with checkboxes

### 📈 Analytics (v3.0)
- **Grouped Analysis**: View assets by Customer, Status, Error Type, or **Tier Analysis**
- **Interactive Rows**: Click any group row to see detailed asset list
- **Tier Analysis** (NEW): Comprehensive test tier progression tracking
  - Automatically detects tier columns (L1, L2, ATE, SLT, Tier0-5, FS1, FS2, etc.)
  - Groups assets by first failing tier
  - **7-Tab Analysis Dialog**:
    - **Test Journey**: Complete tier progression table with color-coded results
    - **Tier Waterfall**: Stacked bars showing pass/fail at each tier
    - **Customer Journey**: Which customers struggle at which test stages
    - **Tier Heatmap**: Color-coded customer vs tier matrix
    - **Owner Workload**: Failures by owner (Drew, Yucheng, Neha, etc.)
    - **Platform Analysis**: Platform performance across tiers
    - **Time Trends**: Failure rates per tier over time with insights
- **Standard Analysis**: 4-tab analysis for Customer/Status/Error groups:
  - Customer Distribution
  - Timeline Trends
  - Status Breakdown
  - Top Error Types
- **Smart State Management**: Dialogs open only when explicitly requested

### 🔄 Cross-File Intelligence
- **Multi-File Data Consolidation**: When the same serial number appears in multiple files:
  - Columns with different values are concatenated with " | " separator
  - Duplicate values are automatically skipped
  - All source files are tracked in `_files_combined` field
  - Sheet information accumulated in `_sheets_combined` field
- **Merge Logging**: Detailed logs showing which serial numbers were merged from multiple files

### 🚀 RESTful API
- Complete backend API for programmatic access
- Async PostgreSQL for high performance
- Comprehensive API documentation

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- PowerShell (Windows)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/ajayadaha1/Silicon-Trace.git
   cd Silicon-Trace
   ```

2. **Start all services**
   ```powershell
   .\start.ps1
   ```

This single command will:
- Stop any existing services
- Start Docker containers (PostgreSQL + FastAPI backend)
- Launch the Streamlit frontend
- Open the app at http://localhost:8501

## Architecture

```
Silicon Trace v3.0/
├── backend/           # FastAPI application
│   ├── main.py       # API endpoints (limit: 50,000 assets)
│   ├── models.py     # SQLModel database models
│   ├── parser.py     # Intelligent Excel parser
│   ├── pptx_parser.py # PowerPoint parser with OCR support
│   ├── database.py   # Async PostgreSQL connection
│   └── Dockerfile    # Backend container
├── frontend/         # Streamlit dashboard
│   ├── app.py        # Main UI with multi-criteria search
│   └── requirements.txt
├── data/            # Place your Excel/PowerPoint files here (not committed)
├── docker-compose.yml
└── start.ps1        # All-in-one startup script
```

## Usage

### Upload Excel or PowerPoint Files (v3.0)

1. Navigate to the **"File Manager"** tab (formerly "Ingest Data")
2. Click **"Browse files"** or drag and drop files
3. Select one or multiple files (supports .xlsx, .xls, .pptx)
4. Click **"Process Files"**

**Supported File Types:**
- **Excel (.xlsx, .xls)**: Standard Excel workbooks with tables
- **PowerPoint (.pptx)**: Presentations with failure data in tables, text, or images

**PowerPoint Support (v3.0 NEW):**
The system uses a multi-phase extraction approach:
- **Phase 1 - Native Tables**: Extracts data from PowerPoint tables (fast, most accurate)
- **Phase 2 - Text Extraction**: Parses text boxes for "SERIAL (ERROR)" patterns
- **Phase 3 - OCR Fallback**: Uses Optical Character Recognition for image-based content (requires pytesseract)

The parser will:
- Detect which columns contain serial numbers
- Skip large reference sheets (>2000 rows)
- Skip sheets named "datecode", "sheet1", "lookup", etc.
- Combine data from multiple sheets within each file
- **Merge data from multiple files** if serial numbers overlap
- Normalize column names to handle case/spacing differences
- Track source sheet, row, and file for each entry
- Prevent duplicate file uploads

**Multi-File Merging Example**:
- File1.xlsx has serial "ABC123" with "FA status": "Closed as known issue"
- File2.xlsx has same serial "ABC123" with "FA status": "8/7: Scan failed..."
- Result: One record with "FA status": "Closed as known issue | 8/7: Scan failed..."
- Metadata shows: `_files_combined: "File1.xlsx | File2.xlsx"`

### View Dashboard (v3.0)

1. Navigate to the **"Dashboard"** tab
2. View customer-segmented graphs showing:
   - Top 10 Failure Types (horizontal stacked bars by customer)
   - Asset Trend Over Time (stacked area chart by customer)
   - Assets by Status (vertical stacked bars by customer)
3. All graphs feature:
   - Dark theme with high contrast white text
   - Customer segmentation with consistent color coding
   - Large, readable fonts (10-14pt)
   - Smart status extraction and normalization
   - Automatic Chinese-to-English translation
   - Legends showing customer breakdown

### Search & Filter Assets (v3.0)

1. Navigate to the **"Trace Assets"** tab
2. **Multi-Criteria Search** (NEW):
   - Add multiple search terms
   - Select AND/OR operators between terms
   - Visual display of logical chain: ":blue[🔍 ALIBABA] :green[AND] :blue[🔍 L1]"
   - Set-based filtering for accurate results
3. **Filter by Source Files**:
   - Select specific files to display
   - Combine with search criteria
4. Choose between two views:
   - **Complete View**: See all captured fields from your files (up to 50,000 assets)
   - **Summary View**: Compact view with key fields only
5. **Scrollable Tables**: 600px height containers for large datasets
6. Click on any asset to view:
   - Complete raw data in JSON format
   - Technical metadata (source files, sheets, timestamps)
   - All fields and values

### File Management (v3.0)

1. Navigate to the **"File Manager"** tab
2. View table of all uploaded files with:
   - Checkboxes for selection
   - Filename
   - Asset count
   - Last updated timestamp
3. **Bulk Delete** (NEW):
   - Select multiple files with checkboxes
   - Click "Delete Selected" to remove them all at once
   - Progress bar shows deletion status

### Analytics (v3.0 NEW)

1. Navigate to the **"Analytics"** tab
2. Group assets by:
   - **Customer**: Group by customer name
   - **Status**: Group by asset status
   - **Error Type**: Group by error/failure type
   - **Tier Analysis** (NEW): Group by first failing test tier
3. Click any row to view detailed asset list in a dialog
4. **For Customer/Status/Error groups**, click "Analyze" for 4-tab charts:
   - **Customer Tab**: Distribution pie chart
   - **Timeline Tab**: Monthly trend line chart
   - **Status Tab**: Status breakdown bar chart
   - **Error Types Tab**: Top error types bar chart
5. **For Tier Analysis groups**, click "Analyze" for 7-tab comprehensive view:
   - **Tab 0 - Test Journey**: Table showing complete tier progression per asset (CSV download)
   - **Tab 1 - Tier Waterfall**: Stacked bars showing pass/fail counts at each tier
   - **Tab 2 - Customer Journey**: Bar chart of customer failures by tier
   - **Tab 3 - Tier Heatmap**: Color-coded matrix (customers × tiers)
   - **Tab 4 - Owner Workload**: Failures grouped by owner/status
   - **Tab 5 - Platform Analysis**: Platform performance across tiers
   - **Tab 6 - Time Trends**: Failure rates over time with trend insights

## Serial Number Detection

The parser uses weighted scoring to detect serial number columns:

**Priority Keywords** (highest to lowest):
1. `cpu_sn`, `cpu sn`, `cpusn`
2. `2d_barcode_sn`, `2d_barcode`, `2d`
3. `sn`, `serial`, `barcode`, `ppid`
4. `system_sn`, `rma#`, `unit_sn`

**Pattern Matching**:
- **CPU SN Format** (1.5x score): `9AMA377P50091_100-000001359`
- **Standard Format** (1.0x score): Alphanumeric 8-25 chars
- **Extended Format** (0.8x score): With underscores/dashes

## API Endpoints (v3.0)

- `POST /upload` - Upload and parse Excel/PowerPoint files (blocks duplicate filenames)
- `GET /assets` - List all assets (supports filtering by source files, limit up to 50,000)
- `GET /assets/{serial_number}` - Get specific asset with merged data
- `GET /search?q={query}` - Search assets
- `GET /source-files` - List all source files with counts and last updated timestamp
- `DELETE /source-files/{filename}` - Delete all assets from a file

**Multi-File Merge Logging**:
- Backend logs show which serial numbers were merged from multiple files
- Example log: `Merging data for serial ABC123: file1.xlsx + file2.xlsx`
- Summary: `✓ Multi-file merge summary: 5 serial numbers found in multiple files`

**Performance**:
- API limit increased to 50,000 assets per request
- 60-second timeout for large dataset requests
- Async PostgreSQL for high performance

API documentation: http://localhost:8000/docs

## Database Management

### Clear Database

To start fresh and delete all data:

```powershell
.\clear-database.ps1
```

Type "yes" to confirm deletion.

### Manual Docker Commands

```powershell
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f backend

# Restart backend
docker-compose restart backend
```

## Configuration

### Parser Settings

Edit `backend/parser.py`:

```python
# Skip sheets matching these patterns
SKIP_SHEET_PATTERNS = ['datecode', 'sheet1', 'lookup', 'reference', 'master', 'database']

# Maximum rows per sheet (larger sheets are skipped)
MAX_SHEET_ROWS = 2000
```

### Add Serial Number Keywords

```python
HEADER_KEYWORDS = [
    'cpu_sn', '2d_barcode_sn', 'sn', 'serial',
    'your_custom_column_name'  # Add here
]
```

## Data Storage

All assets are stored in PostgreSQL with:
- **Indexed serial numbers** for fast lookups
- **JSONB column** for complete raw data with flexible schema
- **Multi-file tracking**: `_files_combined` field tracks all source files
- **Sheet tracking**: `_sheets_combined` and `_total_sheets` metadata
- **Timestamp metadata**: Original ingest time preserved across updates
- **Smart column merging**: Duplicate columns consolidated, different values concatenated
- **Normalized column names**: Case and spacing differences handled automatically

## Troubleshooting

### Backend not responding

```powershell
docker-compose logs backend
docker-compose restart backend
```

### Frontend errors

```powershell
cd frontend
python -m streamlit run app.py
```

### Reset everything

```powershell
.\clear-database.ps1
.\start.ps1
```

## Development

### Backend (FastAPI)

```powershell
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend (Streamlit)

```powershell, multi-row header support
  - PowerPoint: python-pptx 0.6.21, pytesseract (OCR), Pillow
- **Features**: 
  - Multi-file merging with column normalization
  - Multi-criteria search with AND/OR logic
  - Customer segmentation across all visualizations
  - Tier analysis with 7-tab comprehensive visualization
## Tech Stack

- **Backend**: FastAPI 0.109.0, SQLModel, asyncpg, pandas 2.2.0
- **Database**: PostgreSQL 15 (Docker) with JSONB support
- **Frontend**: Streamlit 1.53.1, matplotlib 3.10.8, pandas dataframes
- **Parser**: 
  - Excel: pandas 2.2.0, openpyxl 3.1.2, intelligent column detection
  - PowerPoint: python-pptx 0.6.21, pytesseract (OCR), Pillow
- **Features**: 
  - Multi-file merging with column normalization
  - Multi-criteria search with AND/OR logic
  - Customer segmentation across all visualizations
  - Bulk file deletion with checkboxes
  - Chinese translation (langdetect)
  - Up to 50,000 assets display support
- **Container**: Docker Compose for orchestration

## Version History

### **Tier Analysis**: Comprehensive test tier progression tracking with 7-tab visualization
  - Automatic tier column detection (L1, L2, ATE, SLT, Tier0-5, FS1, FS2, etc.)
  - Test Journey table showing complete progression per asset
  - Tier Waterfall, Customer Journey, Heatmap, Owner Workload, Platform Analysis, Time Trends
- ✨ **Multi-row Header Detection**: Parser now handles complex Excel headers spanning multiple rows
- ✨ PowerPoint (.pptx) file support with multi-phase extraction
- ✨ Multi-criteria search with AND/OR logical operators
- ✨ Customer segmentation in all 3 dashboard graphs (stacked visualizations)
- ✨ Analytics page with grouped analysis (4-tab for standard groups, 7-tab for tier analysis)
- ✨ Bulk file deletion with checkbox selection
- ✨ Increased display capacity to 50,000 assets
- ✨ Scrollable table containers (600px) for large datasets
- 🔧 Improved file management UI
- 🔧 Better state management for dialogs
- 🔧 Enhanced Excel parser skip logic (only skips generic names if multiple sheets exist)
- 🔧 Better state management for dialogs

### v2.0
- ✨ Modern dark theme dashboard
- ✨ 4 interactive graphs with intelligent status extraction
- ✨ Chinese character translation
- ✨ File-based filtering
- ✨ Multi-file data merging

### v1.0
- 🎯 Initial release with Excel parsing
- 🎯 Smart serial number detection
- 🎯 Multi-sheet support
- 🎯 Basic dashboard

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

For issues or questions, please create an issue on GitHub.

---

**Silicon Trace v3.0** - Built with ❤️ for hardware failure analysis
