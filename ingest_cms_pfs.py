# scripts/ingest_cms_pfs.py

import pandas as pd
import os
import sys

# --- CONFIGURATION ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

SOURCE_FILENAME = "PPRRVU2025_Oct.csv"  # <-- IMPORTANT: Change this to your exact file name
CONVERSION_FACTOR = 32.3465  # The final 2025 Conversion Factor

SOURCE_FILE_PATH = r'C:\bill_parser\source_data\rvu25d_0\PPRRVU2025_Oct.csv'
# In scripts/ingest_cms_pfs.py
OUTPUT_FILE_PATH =r'C:\bill_parser\cpt_pricing_data.csv.csv'
def find_header_row(file_path, keyword='HCPCS'):
    """
    Scans a CSV file to find the first row containing a specific keyword (like 'HCPCS').
    This is used to automatically skip junk header lines.
    Returns the row number (0-indexed).
    """
    try:
        with open(file_path, 'r', encoding='latin1') as f:
            for i, line in enumerate(f):
                if keyword in line:
                    print(f"Found correct header at row number: {i}")
                    return i
    except Exception as e:
        print(f"Error while trying to find header row: {e}")
    return None

def process_pfs_data_manually():
    """
    Reads the preliminary CMS RVU file, manually calculates the non-facility price,
    and generates a clean cpt_pricing_data.csv. This version is robust to junk headers
    and uses the exact column names found in the source file.
    """
    print(f"Starting manual calculation from local file: {SOURCE_FILE_PATH}")
    print(f"Using Conversion Factor: {CONVERSION_FACTOR}")

    header_row_index = find_header_row(SOURCE_FILE_PATH)
    if header_row_index is None:
        print(f"FATAL ERROR: Could not find the mandatory 'HCPCS' keyword in any row of the file.")
        return

    try:
        df = pd.read_csv(SOURCE_FILE_PATH, encoding='latin1', header=header_row_index, low_memory=False)
    except FileNotFoundError:
        print(f"FATAL ERROR: Source file not found at {SOURCE_FILE_PATH}")
        return

    print("Source data loaded successfully, skipping junk headers. Processing...")

    df.columns = df.columns.str.strip()
    
    # --- THIS IS THE CRITICAL FIX ---
    # Use the exact, but poorly named, columns from the actual file header.
    # Mapping: WORK RVU -> 'RVU', NON-FAC PE RVU -> 'PE RVU', NON-FAC MP RVU -> 'RVU.1'
    required_rvu_columns = ['HCPCS', 'RVU', 'PE RVU', 'RVU.1']
    
    if not all(col in df.columns for col in required_rvu_columns):
        print(f"FATAL ERROR: The source file is missing one of the required RVU component columns.")
        print(f"Expected columns: {required_rvu_columns}")
        print(f"Available columns are: {df.columns.tolist()}")
        return

    df_clean = df[required_rvu_columns].copy()
    
    # Convert the correctly-named RVU columns to numeric
    for col in ['RVU', 'PE RVU', 'RVU.1']:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    df_clean.dropna(inplace=True)

    # Perform the core calculation using the correct column names
    df_clean['total_non_facility_rvu'] = df_clean['RVU'] + df_clean['PE RVU'] + df_clean['RVU.1']
    df_clean['calculated_price'] = (df_clean['total_non_facility_rvu'] * CONVERSION_FACTOR).round(2)
    
    df_clean = df_clean[df_clean['calculated_price'] > 0]
    
    if len(df_clean) == 0:
        print("FATAL ERROR: No rows with a positive calculated price were found.")
        return

    # Finalize the DataFrame for our application
    final_df = df_clean[['HCPCS', 'calculated_price']].rename(columns={
        'HCPCS': 'cpt_code',
        'calculated_price': 'median_price'
    })

    final_df['cpt_code'] = final_df['cpt_code'].astype(str).str.strip()
    final_df.drop_duplicates(subset=['cpt_code'], keep='first', inplace=True)

    # Save the output file
    try:
        final_df.to_csv(OUTPUT_FILE_PATH, index=False)
        print(f"Successfully calculated and saved {len(final_df)} unique records.")
        print(f"Application knowledge base is now up-to-date: {OUTPUT_FILE_PATH}")
    except Exception as e:
        print(f"FATAL ERROR: Could not save the output file. Error: {e}")

if __name__ == "__main__":
    process_pfs_data_manually()