"""
Load NAPPI codes from CSV file into Supabase database

This script loads the National Pharmaceutical Product Interface (NAPPI) codes,
which are South Africa's standard medication coding system.

Usage:
    python load_nappi_codes.py /path/to/nappi_codes.csv
    
CSV Format Expected:
    Brand Name, Generic Name, Schedule, Strength/Dosage Form, Ingredients
"""

import pandas as pd
import os
import sys
from supabase import create_client
from datetime import datetime

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpenVqdGJlam5ucmRxY3ltZ2xlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDMyMTc0NiwiZXhwIjoyMDc1ODk3NzQ2fQ.g8gqEs3Ynb_577txVNjnp8_PYkuBNdac3LxeyBETppw')


def normalize_schedule(schedule_str):
    """Normalize schedule text to standard format"""
    if pd.isna(schedule_str):
        return 'Unscheduled'
    
    schedule_str = str(schedule_str).strip().upper()
    
    # Map various formats to standard
    schedule_mapping = {
        'S0': 'S0', 'S1': 'S1', 'S2': 'S2', 'S3': 'S3', 
        'S4': 'S4', 'S5': 'S5', 'S6': 'S6', 'S7': 'S7', 'S8': 'S8',
        'SCHEDULE 0': 'S0', 'SCHEDULE 1': 'S1', 'SCHEDULE 2': 'S2',
        'SCHEDULE 3': 'S3', 'SCHEDULE 4': 'S4', 'SCHEDULE 5': 'S5',
        'SCHEDULE 6': 'S6', 'SCHEDULE 7': 'S7', 'SCHEDULE 8': 'S8',
        'OTC': 'S0', 'UNSCHEDULED': 'Unscheduled', 'NONE': 'Unscheduled'
    }
    
    return schedule_mapping.get(schedule_str, 'Unscheduled')


def load_nappi_from_csv(csv_path):
    """Load NAPPI codes from CSV into Supabase"""
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found at {csv_path}")
        return
    
    print(f"🔄 Loading NAPPI codes from CSV: {csv_path}")
    
    # Read CSV file
    df = pd.read_csv(csv_path)
    print(f"📊 Found {len(df)} NAPPI entries in CSV")
    
    # Display column names
    print(f"📋 CSV Columns: {list(df.columns)}")
    
    # Connect to Supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Connected to Supabase")
    
    # Prepare data for insertion
    codes_to_insert = []
    skipped_count = 0
    
    for idx, row in df.iterrows():
        try:
            # Expected columns (flexible mapping)
            # Try to find columns by name variations
            nappi_code = None
            brand_name = None
            generic_name = None
            schedule = None
            strength = None
            ingredients = None
            
            # Find NAPPI Code column
            for col in ['NAPPI Code', 'nappi_code', 'NAPPI', 'Code', 'nappi']:
                if col in df.columns and pd.notna(row.get(col)):
                    nappi_code = str(row[col]).strip()
                    break
            
            # Find Brand Name column
            for col in ['Brand Name', 'brand_name', 'Brand', 'Trade Name', 'Product Name']:
                if col in df.columns and pd.notna(row.get(col)):
                    brand_name = str(row[col]).strip()
                    break
            
            # Find Generic Name column
            for col in ['Generic Name', 'generic_name', 'Generic', 'Active Ingredient']:
                if col in df.columns and pd.notna(row.get(col)):
                    generic_name = str(row[col]).strip()
                    break
            
            # Find Schedule column
            for col in ['Schedule', 'schedule', 'Medicine Schedule', 'Class']:
                if col in df.columns and pd.notna(row.get(col)):
                    schedule = normalize_schedule(row[col])
                    break
            
            # Find Strength/Dosage Form column
            for col in ['Strength/Dosage Form', 'Strength', 'Dosage Form', 'strength', 'dosage_form']:
                if col in df.columns and pd.notna(row.get(col)):
                    strength = str(row[col]).strip()
                    break
            
            # Find Ingredients column
            for col in ['Ingredients', 'ingredients', 'Active Ingredients', 'Composition']:
                if col in df.columns and pd.notna(row.get(col)):
                    ingredients = str(row[col]).strip()
                    break
            
            # Validate required fields
            if not nappi_code or not brand_name or not generic_name:
                skipped_count += 1
                continue
            
            code_data = {
                'nappi_code': nappi_code,
                'brand_name': brand_name,
                'generic_name': generic_name,
                'schedule': schedule or 'Unscheduled',
                'strength': strength,
                'dosage_form': strength,  # Combined in input
                'ingredients': ingredients or generic_name,
                'status': 'active'
            }
            
            codes_to_insert.append(code_data)
            
        except Exception as e:
            print(f"⚠️  Warning: Error processing row {idx}: {e}")
            skipped_count += 1
            continue
    
    print(f"📝 Prepared {len(codes_to_insert)} codes for insertion")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} rows due to missing required fields")
    
    if len(codes_to_insert) == 0:
        print("❌ No valid NAPPI codes to insert. Please check CSV format.")
        return
    
    # Insert in batches (Supabase has limits)
    batch_size = 1000
    total_inserted = 0
    total_errors = 0
    
    for i in range(0, len(codes_to_insert), batch_size):
        batch = codes_to_insert[i:i + batch_size]
        
        try:
            # Use upsert to handle duplicates
            result = supabase.table('nappi_codes').upsert(batch).execute()
            total_inserted += len(batch)
            print(f"✅ Inserted batch {i//batch_size + 1}: {total_inserted}/{len(codes_to_insert)} codes")
        except Exception as e:
            print(f"❌ Error inserting batch {i//batch_size + 1}: {e}")
            total_errors += len(batch)
            # Continue with next batch
    
    print(f"\n🎉 NAPPI loading complete!")
    print(f"   Total inserted: {total_inserted}")
    print(f"   Total errors: {total_errors}")
    print(f"   Total skipped: {skipped_count}")
    
    # Verify insertion
    try:
        count_result = supabase.table('nappi_codes').select('nappi_code', count='exact').execute()
        print(f"\n📊 Total NAPPI codes in database: {count_result.count}")
        
        # Show sample codes
        sample = supabase.table('nappi_codes').select('*').limit(5).execute()
        print("\n📋 Sample NAPPI codes:")
        for code in sample.data:
            print(f"  - {code['nappi_code']}: {code['brand_name']} ({code['generic_name']}) - {code['schedule']}")
    except Exception as e:
        print(f"⚠️  Could not verify insertion: {e}")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("❌ Usage: python load_nappi_codes.py <path_to_csv>")
        print("\nExpected CSV format:")
        print("  Brand Name, Generic Name, Schedule, Strength/Dosage Form, Ingredients")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    load_nappi_from_csv(csv_path)


if __name__ == '__main__':
    main()
