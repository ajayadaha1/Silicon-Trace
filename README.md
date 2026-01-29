# 🔍 Silicon Trace v3.2

**Hardware Failure Analysis Tool with AI Co-Analyst & AI-Powered Data Normalization**

A powerful local application for intelligent parsing and analysis of hardware failure data from Excel and PowerPoint files. Now featuring **AI-powered data normalization** with AMD Nabu AI for automatic column classification and error cleaning, plus **AI conversational analytics** and **Model Context Protocol (MCP) server** for scalable data access. Built with FastAPI, PostgreSQL, Streamlit, and FastMCP.

## ✨ Key Features

### 🧹 AI-Powered Data Normalization (v3.2 - NEW!)
- **3-Phase Nabu AI Normalization**: Intelligent data cleaning using AMD Nabu AI
  - **Phase 1: Column Classification**: Nabu AI automatically classifies all columns into 10 categories (SERIAL_NUMBER, ERROR_TYPE, STATUS, TEST_TIER, DATE, CUSTOMER, PLATFORM, DIAGNOSTIC, DESCRIPTION, IGNORE)
  - **Phase 2: Smart Routing**: Intelligently separates ERROR_TYPE from DIAGNOSTIC data (logs, URLs, file paths)
  - **Phase 3: Error Cleaning**: Nabu AI cleans messy error values (dates, Chinese text, URLs, file names)
- **Tracking Number Extraction**: Automatically detects and extracts FedEx, UPS, DHL, USPS tracking numbers into dedicated field
- **Long Description Shortening**: Intelligently shortens verbose error descriptions to ~50 chars while preserving key information
- **Multi-Row Header Support**: Properly handles Excel files with merged header cells (e.g., "Tier1 - ATE - FT1")
- **Visual Indicators**: 🔄 emoji marks normalized columns in Complete View with info banner
- **Original Data Preservation**: All original values preserved in raw_data for search and verification
- **Bilingual Support**: Handles Chinese error descriptions (失败类型, 客户, 状态, 日期)
- **Batch Processing**: normalize_existing_data.py script to fix existing database records

### 🤖 AI Co-Analyst (v3.1)
- **Conversational Analytics**: Ask questions about your data in natural language with full database visibility
- **Auto-Insights**: AI automatically analyzes complete dataset and provides key findings
- **Dynamic Visualizations**: Generate custom charts by describing them - AI creates proper aggregations
- **Root Cause Analysis**: Multi-step autonomous investigation with AI agent
- **Safe Code Execution**: AI-generated code runs in sandboxed environment with pre-imported libraries
- **AMD Nabu Integration**: Uses internal AMD AI - all data stays private
- **Statistical Compression**: AI has complete statistics about all records (customers, errors, timelines) without sending raw data
- **Integrated Interface**: AI Co-Analyst appears as 5th tab - automatically uses data from File Manager

### 🔌 MCP Server (v3.1)
- **Model Context Protocol Server**: Local MCP server exposing Silicon Trace database via standardized protocol
- **6 MCP Tools**: `query_assets`, `get_asset_details`, `get_stats`, `search_failures`, `analyze_customer`, `count_assets`
- **4 MCP Resources**: Database summary, customer list, error types, tier statistics
- **SSE Transport**: Server-Sent Events endpoint at `http://localhost:8001/sse`
- **VS Code Integration**: Built-in MCP configuration for VS Code extension
- **Future-Ready**: Designed for scalability when dataset exceeds 10,000 records
- **Docker Deployed**: Runs as separate container with shared database access
- **Standards-Based**: Uses FastMCP framework for MCP protocol compliance

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

### 📈 Analytics (v3.2)
- **Grouped Analysis**: View assets by Customer, Status, Error Type, or **Tier Analysis**
- **Interactive Rows**: Click any group row to see detailed asset list
- **Tier Analysis** (IMPROVED): Comprehensive test tier progression tracking
  - Automatically detects tier columns (L1, L2, ATE, SLT, Tier0-5, FS1, FS2, etc.)
  - **Multi-Row Header Preservation**: Properly combines tier group names (Tier1-ATE) with specific tests (FT1)
  - Groups assets by first failing tier with failure type: "❌ Tier1 ATE: FT2 10C"
  - Handles "No Tier Data" gracefully instead of showing "Tier99"
  - **7-Tab Analysis Dialog**:
    - **Test Journey**: Complete tier progression table with color-coded results and tracking numbers
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
- Start Docker containers (PostgreSQL + FastAPI backend + MCP server)
- Launch the Streamlit frontend
- Open the app at http://localhost:8501
- MCP server available at http://localhost:8001/sse

3. **Configure AI Co-Analyst** (Optional but recommended)
   ```powershell
   # Copy environment template
   cp .env.example .env
   
   # Edit .env and add your Nabu API token
   # NABU_API_TOKEN=your_token_here
   ```

## Architecture

```
Silicon Trace v3.1/
├── backend/           # FastAPI application
│   ├── main.py       # API endpoints + AI endpoints (v3.1)
│   ├── models.py     # SQLModel database models
│   ├── parser.py     # Intelligent Excel parser
│   ├── pptx_parser.py # PowerPoint parser with OCR support
│   ├── nabu_client.py # AMD Nabu AI client (v3.1 NEW)
│   ├── code_sandbox.py # Safe code execution (v3.1 NEW)
│   ├── silicon_trace_mcp.py # MCP server with 6 tools + 4 resources (v3.1 NEW)
│   ├── queries.py    # Shared query logic for API and MCP (v3.1 NEW)
│   ├── database.py   # Async PostgreSQL connection
│   ├── Dockerfile    # Backend container
│   └── Dockerfile.mcp # MCP server container (v3.1 NEW)
├── frontend/         # Streamlit dashboard
│   ├── app.py        # Main UI with AI Co-Analyst integrated
│   └── requirements.txt
├── .vscode/          # VS Code configuration
│   └── mcp.json      # MCP client configuration (v3.1 NEW)
├── data/            # Place your Excel/PowerPoint files here (not committed)
├── docker-compose.yml # Orchestrates 4 containers: postgres, backend, frontend, mcp-server
├── start.ps1        # All-in-one startup script (includes MCP server)
├── start-with-mcp.ps1 # Alternative startup with explicit MCP focus
├── MCP_README.md    # MCP server documentation (v3.1 NEW)
└── README.md        # This file
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

### AI Co-Analyst (v3.1 NEW) 🤖

Navigate to the **"AI Co-Analyst"** tab (5th tab after Analytics) for intelligent data analysis. All data from File Manager is automatically available - no file selection needed.

#### 💬 Chat Mode
- Ask questions in natural language about your **complete dataset**
- AI has access to full statistics for all records (not just samples)
- Get data-driven answers with exact counts and percentages
- AI remembers conversation history
- Request visualizations on-the-fly

**Examples:**
- "List all serial numbers from the database"
- "Which customer has the most failures and how many?"
- "Show me exact counts for each error type"
- "What's the timeline of failures by date?"
- "Compare failure rates by customer with exact numbers"

#### 🔍 Auto-Insights Mode
- Click "Analyze" for automatic analysis
- Get key metrics, insights, anomalies, recommendations
- Focus on specific areas (failures, customers, trends, errors, tiers)
- Executive summary in seconds

#### automatically creates proper aggregations for categorical data
- Generates and renders charts live using Plotly
- View/download generated Python code
- Export visualizations as HTML

**Examples:**
- "Create a bar graph of all High Failure Rate at ATE"
- "Show a Sankey diagram of tier progression"
- "Make a heatmap of errors vs customers"
- "Create a timeline of failures with trendline"
- "Create a sunburst chart of customer → tier → errorssion"
- "Make a heatmap of errors vs customers"
- "Create a 3D scatter plot of failures"

#### 🔬 Root Cause Analysis
- Select investigation topic or describe custom investigation
- AI performs multi-step autonomous analysis
- Get hypothesis, investigation steps, findings
- Root causes identified with confidence levels
- Actionable recommendations provided

**Investigation Depth**: Set 3-10 steps for analysis

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
- **Extended For

### Data Management
- `POST /upload` - Upload and parse Excel/PowerPoint files (blocks duplicate filenames)
- `GET /assets` - List all assets (supports filtering by source files, limit up to 50,000)
- `GET /assets/{serial_number}` - Get specific asset with merged data
- `GET /search?q={query}` - Search assets
- `GET /source-files` - List all source files with counts and last updated timestamp
- `GET /files` - Get list of uploaded files
- `DELETE /source-files/{filename}` - Delete all assets from a file

### AI Co-Analyst (v3.1)
- `POST /ai/chat` - Natural language Q&A with conversation history
- `POST /ai/analyze` - Auto-insights with focus area support
- `POST /ai/visualize` - Generate custom visualizations from descriptions
- `POST /ai/investigate` - Root cause analysis with multi-step investigation
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
  - AI Platform**: AMD Nabu AI with httpx async client
- **Code Execution**: Custom sandboxed environment with Plotly, pandas, numpy
- **Parser**: 
  - Excel: pandas 2.2.0, openpyxl 3.1.2, intelligent column detection
  - PowerPoint: python-pptx 0.6.21, pytesseract (OCR), Pillow
- **Features**: 
  - Multi-file merging with column normalization
  - Multi-criteria search with AND/OR logic
  - Customer segmentation across all visualizations
  - AI-powered analytics with statistical compressionupport
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
 - Current)
- 🤖 **AI Co-Analyst Integration**: AMD Nabu AI-powered conversational analytics
  - **Chat Mode**: Natural language Q&A with full database visibility via statistical compression
  - **Auto-Insights**: Automatic pattern detection, anomaly identification, and recommendations
  - **Visualization Studio**: AI-generated dynamic Plotly charts with automatic data aggregation
  - **Root Cause Analysis**: Multi-step autonomous investigation agent
- 🔒 **Safe Code Execution**: Sandboxed environment with pre-imported libraries (Plotly, pandas, numpy)
- 📊 **Statistical Compression**: AI accesses complete dataset statistics without raw data overhead
  - All serial numbers, customer counts, error distributions, timelines
  - Token-efficient approach optimal for <10,000 records
  - Provides exact counts and complete visibility
- 🔌 **MCP Server**: Model Context Protocol server for standardized data access
  - **6 MCP Tools**: query_assets, get_asset_details, get_stats, search_failures, analyze_customer, count_assets
  - **4 MCP Resources**: silicon-trace://database/summary, customers, error-types, tiers
  - **SSE Transport**: Server-Sent Events endpoint at port 8001
  - **VS Code Integration**: Built-in configuration for MCP extension
  - **Docker Deployment**: Separate container with shared database
  - **FastMCP Framework**: Standards-compliant MCP implementation (v2.14.4)
  - **Future-Ready**: Designed for scalability when dataset grows beyond 10,000 records
  - **Documentation**: Comprehensive MCP_README.md with tool examples
- 🔧 **Backend Enhancements**: 
  - New AI endpoints: `/ai/chat`, `/ai/analyze`, `/ai/visualize`, `/ai/investigate`
  - AMD Nabu AI client (`nabu_client.py`) with unified response parsing
  - Code sandbox (`code_sandbox.py`) for safe execution
  - Enhanced data context with comprehensive statistics
  - MCP server infrastructure ready for portal registration
  - Shared query logic (`queries.py`) for API and MCP
  - `/files` endpoint for file list
- 🎨 **Integrated UI**: AI Co-Analyst appears as 5th tab, uses data directly from database
- 🐛 **Bug Fixes**: 
  - Fixed timestamp JSON serialization across all AI methods
  - Fixed Nabu API response parsing (responseText field)
  - Fixed code extraction (removed import statements, fig.show() calls, encoding artifacts)
  - Fixed bar chart and timeline generation with proper aggregations

### v3.0 (Major Feature Release)
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

## License1

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## MCP Server Usage

The Silicon Trace MCP server exposes your database via the Model Context Protocol.

### Tools Available

1. **query_assets** - Query assets with filters (customer, error type, status, tier, date range)
2. **get_asset_details** - Get complete details for a specific serial number
3. **get_stats** - Get database statistics (total assets, customers, error types)
4. **search_failures** - Search for specific failure patterns
5. **analyze_customer** - Get detailed analysis for a specific customer
6. **count_assets** - Count assets matching criteria

### Resources Available

1. **silicon-trace://database/summary** - Database overview with statistics
2. **silicon-trace://database/customers** - List of all customers with asset counts
3. **silicon-trace://database/error-types** - All error types with frequencies
4. **silicon-trace://database/tiers** - Tier progression statistics

### VS Code Integration

The MCP server is pre-configured for VS Code:

1. Install the VS Code MCP extension
2. Configuration is already in `.vscode/mcp.json`
3. Connect to `http://localhost:8001/sse`
4. Use MCP tools directly in VS Code

For detailed MCP documentation, see [MCP_README.md](MCP_README.md).

## Support

For issues or questions, please create an issue on GitHub.

---

**Silicon Trace v3.1** - Built with ❤️ for hardware failure analysis
