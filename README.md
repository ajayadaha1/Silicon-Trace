# 🔍 Silicon Trace

**Hardware Failure Analysis Tool**

A local application for intelligent parsing and analysis of hardware failure data from Excel files. Built with FastAPI, PostgreSQL, and Streamlit.

## Features

- **Intelligent Excel Parser**: Automatically detects serial number columns using heuristic scoring
- **Multi-Sheet Support**: Combines data from multiple Excel sheets based on serial numbers
- **CPU SN Format Priority**: Prioritizes CPU serial number format (e.g., `9AMA377P50091_100-000001359`)
- **Source Tracking**: Tracks which sheet and row each serial number was extracted from
- **Multi-File Upload**: Upload and process multiple Excel files simultaneously
- **File Management**: Filter assets by source file and delete unwanted datasets
- **Dynamic Column Display**: Shows all captured columns from your Excel files
- **RESTful API**: Complete backend API for programmatic access

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
- Combine data from multiple sheets
- Track source sheet and row for each entry

### View & Filter Assets

1. Navigate to the **"Trace Assets"** tab
2. Use the **"Filter by Source Files"** dropdown to select specific files
3. View all assets in the dynamic table
4. Delete unwanted source files using the **"Delete Source File"** dropdown

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

- `POST /upload` - Upload and parse Excel files
- `GET /assets` - List all assets (supports filtering by source files)
- `GET /assets/{serial_number}` - Get specific asset
- `GET /search?q={query}` - Search assets
- `GET /source-files` - List all source files with counts
- `DELETE /source-files/{filename}` - Delete all assets from a file

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
- Indexed serial numbers for fast lookups
- JSONB column for complete raw data
- Source file tracking
- Sheet and row tracking
- Timestamp metadata

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

- **Backend**: FastAPI 0.109.0, SQLModel, asyncpg
- **Database**: PostgreSQL 15 (Docker)
- **Frontend**: Streamlit 1.31.0
- **Parser**: Pandas 2.2.0, openpyxl 3.1.2
- **Container**: Docker Compose

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

For issues or questions, please create an issue on GitHub.

---

Built with ❤️ for hardware failure analysis
