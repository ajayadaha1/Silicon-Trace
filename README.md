# 🔍 Silicon Trace

**Hardware Failure Analysis Tool**

A powerful local application for intelligent parsing and analysis of hardware failure data from Excel files. Built with FastAPI, PostgreSQL, and Streamlit.

## ✨ Key Features

### 🎯 Intelligent Data Processing
- **Smart Excel Parser**: Automatically detects serial number columns using heuristic scoring
- **Multi-Sheet Support**: Combines data from multiple Excel sheets based on serial numbers
- **Multi-File Merging**: Upload multiple files with overlapping serial numbers - data is intelligently merged and consolidated
- **CPU SN Format Priority**: Prioritizes CPU serial number format (e.g., `9AMA377P50091_100-000001359`)
- **Duplicate Prevention**: Prevents re-uploading the same file to avoid data duplication
- **Column Normalization**: Merges duplicate columns with case/spacing differences (e.g., " FA status " and "FA status")

### 📊 Advanced Dashboard (v2.0)
- **Modern Dark Theme**: High-contrast visualizations optimized for readability
- **4 Interactive Graphs**:
  - Error Type Distribution (Rainbow gradient bars)
  - Monthly Failure Trend (Green line chart with area fill)
  - Assets by Status (Yellow/orange vertical bars)
  - Top 10 Customers (Purple gradient bars)
- **Intelligent Status Extraction**: Smart parsing of messy status fields with pattern matching
- **Chinese Translation**: Automatic detection and translation of Chinese characters to English
- **Serial Number Filtering**: Removes serial number clutter from status labels

### 🔍 Data Management
- **Dynamic Column Display**: Shows all captured columns from your Excel files
- **Source Tracking**: Tracks which sheets and files contributed data for each serial number
- **Complete View**: See all assets with every captured field
- **Technical Data Tab**: View raw data with metadata about source files and sheets
- **File-Based Filtering**: Filter assets by source file
- **Bulk Delete**: Remove all assets from a specific source file

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
Silicon Trace/
├── backend/           # FastAPI application
│   ├── main.py       # API endpoints
│   ├── models.py     # SQLModel database models
│   ├── parser.py     # Intelligent Excel parser
│   ├── database.py   # Async PostgreSQL connection
│   └── Dockerfile    # Backend container
├── frontend/         # Streamlit dashboard
│   ├── app.py        # Main UI application
│   └── requirements.txt
├── data/            # Place your Excel files here (not committed)
├── docker-compose.yml
└── start.ps1        # All-in-one startup script
```

## Usage

### Upload Excel Files

1. Navigate to the **"Ingest Data"** tab
2. Click **"Browse files"** or drag and drop Excel files
3. Select one or multiple files (supports .xlsx, .xls)
4. Click **"Process Files"**

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

### View Dashboard

1. Navigate to the **"Dashboard"** tab
2. View modern graphs showing:
   - Top error types with rainbow gradient colors
   - Monthly failure trends over time
   - Asset distribution by status
   - Top 10 customers by asset count
3. All graphs feature:
   - Dark theme with high contrast white text
   - Large, readable fonts (10-14pt)
   - Smart status extraction and normalization
   - Automatic Chinese-to-English translation

### View & Filter Assets

1. Navigate to the **"Trace Assets"** tab
2. Choose between two views:
   - **Complete View**: See all captured fields from your Excel files
   - **Summary View**: Compact view with key fields only
3. Use the **"Filter by Source Files"** dropdown to select specific files
4. Click on any asset to view:
   - Complete raw data in JSON format
   - Technical metadata (source files, sheets, timestamps)
   - All fields and values
5. Delete unwanted source files using the **"Delete Source File"** dropdown

**Metadata Fields**:
- `_files_combined`: All files that contributed data
- `_sheets_combined`: All sheets where this serial was found
- `_total_sheets`: Number of sheets containing this serial
- `_source_sheet`, `_source_row`, `_serial_column`: Original location info

### Search Assets

- Enter a serial number or search term in the search box
- Get exact matches or fuzzy search results
- View complete raw data for each asset

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

## API Endpoints

- `POST /upload` - Upload and parse Excel files (blocks duplicate filenames)
- `GET /assets` - List all assets (supports filtering by source files)
- `GET /assets/{serial_number}` - Get specific asset with merged data
- `GET /search?q={query}` - Search assets
- `GET /source-files` - List all source files with counts
- `DELETE /source-files/{filename}` - Delete all assets from a file

**Multi-File Merge Logging**:
- Backend logs show which serial numbers were merged from multiple files
- Example log: `Merging data for serial ABC123: file1.xlsx + file2.xlsx`
- Summary: `✓ Multi-file merge summary: 5 serial numbers found in multiple files`

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

```powershell
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## Tech Stack

- **Backend**: FastAPI 0.109.0, SQLModel, asyncpg, pandas 2.2.0
- **Database**: PostgreSQL 15 (Docker) with JSONB support
- **Frontend**: Streamlit 1.53.1, matplotlib 3.10.8
- **Parser**: Pandas 2.2.0, openpyxl 3.1.2, intelligent column detection
- **Features**: Multi-file merging, column normalization, Chinese translation
- **Container**: Docker Compose for orchestration

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

For issues or questions, please create an issue on GitHub.

---

Built with ❤️ for hardware failure analysis
