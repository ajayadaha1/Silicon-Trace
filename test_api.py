"""
Test Silicon Trace API with sample data upload
"""
import requests
from pathlib import Path

BACKEND_URL = "http://localhost:8000"

def test_health():
    """Test backend health"""
    print("🔍 Testing backend health...")
    try:
        response = requests.get(f"{BACKEND_URL}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Backend is running: {data['service']} v{data['version']}")
            return True
        else:
            print(f"✗ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to backend. Is it running?")
        print("  Run: docker-compose up -d")
        return False

def test_upload(file_path):
    """Test file upload"""
    print(f"\n📤 Testing file upload: {file_path.name}")
    
    if not file_path.exists():
        print(f"✗ File not found: {file_path}")
        return False
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            response = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Upload successful!")
            print(f"  - Rows processed: {data['rows_processed']}")
            print(f"  - New assets: {data['rows_created']}")
            print(f"  - Updated assets: {data['rows_updated']}")
            return True
        else:
            print(f"✗ Upload failed with status {response.status_code}")
            print(f"  Error: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"✗ Upload error: {e}")
        return False

def test_search(serial_number):
    """Test asset search"""
    print(f"\n🔎 Testing asset search: {serial_number}")
    
    try:
        response = requests.get(f"{BACKEND_URL}/assets/{serial_number}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Asset found!")
            print(f"  - Serial Number: {data['serial_number']}")
            print(f"  - Error Type: {data.get('error_type', 'N/A')}")
            print(f"  - Status: {data.get('status', 'N/A')}")
            print(f"  - Source File: {data['source_filename']}")
            print(f"  - Raw Data Fields: {', '.join(data['raw_data'].keys())}")
            return True
        elif response.status_code == 404:
            print(f"✗ Asset not found")
            return False
        else:
            print(f"✗ Search failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Search error: {e}")
        return False

def test_list_assets():
    """Test listing assets"""
    print(f"\n📋 Testing asset listing...")
    
    try:
        response = requests.get(f"{BACKEND_URL}/assets", params={"limit": 5}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            total = data['total']
            print(f"✓ Retrieved {total} assets")
            
            if total > 0:
                print("  Sample assets:")
                for i, asset in enumerate(data['assets'][:3], 1):
                    print(f"    {i}. {asset['serial_number']} - {asset.get('error_type', 'N/A')}")
            
            return True
        else:
            print(f"✗ List failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ List error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Silicon Trace - API Test Suite")
    print("=" * 60)
    
    # Test 1: Health check
    if not test_health():
        print("\n❌ Backend is not running. Please start it first:")
        print("   docker-compose up -d")
        return
    
    # Test 2: Upload sample files
    data_dir = Path(__file__).parent / 'data'
    sample_files = [
        data_dir / 'sample_hardware_failures.xlsx',
        data_dir / 'sample_inconsistent_headers.xlsx',
        data_dir / 'sample_ppid_format.xlsx'
    ]
    
    uploaded_any = False
    for sample_file in sample_files:
        if sample_file.exists():
            if test_upload(sample_file):
                uploaded_any = True
    
    if not uploaded_any:
        print("\n⚠️  No sample files uploaded. Generate them with:")
        print("   python generate_samples.py")
    
    # Test 3: Search for specific assets
    test_serial_numbers = ['ABC12345XYZ', 'XYZ98765ABC', 'PPID12345ABC']
    
    for sn in test_serial_numbers:
        if test_search(sn):
            break
    
    # Test 4: List assets
    test_list_assets()
    
    print("\n" + "=" * 60)
    print("✨ Test suite complete!")
    print("=" * 60)
    print("\n📊 Next steps:")
    print("  1. Start the frontend: .\\start-frontend.ps1")
    print("  2. Open http://localhost:8501 in your browser")
    print("  3. Try uploading and searching for assets!")

if __name__ == '__main__':
    main()
