"""
Generate sample Excel files for testing Silicon Trace
"""
import pandas as pd
from pathlib import Path

def generate_sample_data():
    """Generate sample hardware failure data"""
    data = {
        'SN': [
            'ABC12345XYZ',
            'DEF67890UVW',
            'GHI11111RST',
            'JKL22222MNO',
            'PQR33333ABC'
        ],
        'Error Type': [
            'Memory Failure',
            'Disk Error',
            'CPU Overheat',
            'Power Supply Failure',
            'Network Interface Error'
        ],
        'Status': [
            'Failed',
            'Warning',
            'Critical',
            'Failed',
            'Warning'
        ],
        'Date': [
            '2024-01-15',
            '2024-01-16',
            '2024-01-17',
            '2024-01-18',
            '2024-01-19'
        ],
        'Location': [
            'Data Center A',
            'Data Center B',
            'Data Center A',
            'Data Center C',
            'Data Center B'
        ]
    }
    
    return pd.DataFrame(data)


def generate_inconsistent_header_sample():
    """Generate sample with different column names (tests heuristic detection)"""
    data = {
        'Serial Number': [
            'XYZ98765ABC',
            'UVW54321DEF',
            'RST13579GHI'
        ],
        'Failure Classification': [
            'Hardware Fault',
            'Software Bug',
            'Configuration Error'
        ],
        'Current State': [
            'Offline',
            'Degraded',
            'Maintenance'
        ],
        'Timestamp': [
            '2024-01-20',
            '2024-01-21',
            '2024-01-22'
        ]
    }
    
    return pd.DataFrame(data)


def generate_ppid_sample():
    """Generate sample using PPID as serial number column"""
    data = {
        'PPID': [
            'PPID12345ABC',
            'PPID67890XYZ',
            'PPID11111RST'
        ],
        'Error': [
            'Fan Failure',
            'Temperature Sensor Error',
            'Battery Depleted'
        ],
        'Status': [
            'Replace',
            'Monitor',
            'Replace'
        ]
    }
    
    return pd.DataFrame(data)


if __name__ == '__main__':
    # Create data directory if it doesn't exist
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)
    
    # Generate sample files
    print("Generating sample Excel files...")
    
    # Sample 1: Standard format
    df1 = generate_sample_data()
    file1 = data_dir / 'sample_hardware_failures.xlsx'
    df1.to_excel(file1, index=False)
    print(f"✓ Created: {file1}")
    
    # Sample 2: Inconsistent headers
    df2 = generate_inconsistent_header_sample()
    file2 = data_dir / 'sample_inconsistent_headers.xlsx'
    df2.to_excel(file2, index=False)
    print(f"✓ Created: {file2}")
    
    # Sample 3: PPID format
    df3 = generate_ppid_sample()
    file3 = data_dir / 'sample_ppid_format.xlsx'
    df3.to_excel(file3, index=False)
    print(f"✓ Created: {file3}")
    
    print("\n✨ Sample files created successfully!")
    print(f"\nFiles are located in: {data_dir}")
