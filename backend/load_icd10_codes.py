"""
Load ICD-10 codes from Excel file into Supabase database
"""
import pandas as pd
import os
from supabase import create_client
from datetime import datetime

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpenVqdGJlam5ucmRxY3ltZ2xlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDMyMTc0NiwiZXhwIjoyMDc1ODk3NzQ2fQ.g8gqEs3Ynb_577txVNjnp8_PYkuBNdac3LxeyBETppw')

def load_icd10_codes(excel_path='/tmp/icd10.xlsx'):
    """Load ICD-10 codes from Excel into Supabase"""
    
    print("🔄 Loading ICD-10 codes from Excel...")
    
    # Read Excel file
    df = pd.read_excel(excel_path)
    print(f"📊 Found {len(df)} ICD-10 codes")
    
    # Connect to Supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Connected to Supabase")
    
    # Prepare data for insertion
    codes_to_insert = []
    
    for _, row in df.iterrows():
        # Only insert codes with ICD10_Code (not just category headers)
        if pd.notna(row.get('ICD10_Code')):
            code_data = {
                'code': str(row['ICD10_Code']).strip(),
                'chapter_no': str(row['Chapter_No']) if pd.notna(row.get('Chapter_No')) else None,
                'chapter_desc': str(row['Chapter_Desc']) if pd.notna(row.get('Chapter_Desc')) else None,
                'group_code': str(row['Group_Code']) if pd.notna(row.get('Group_Code')) else None,
                'group_desc': str(row['Group_Desc']) if pd.notna(row.get('Group_Desc')) else None,
                'code_3char': str(row['ICD10_3_Code']) if pd.notna(row.get('ICD10_3_Code')) else None,
                'code_3char_desc': str(row['ICD10_3_Code_Desc']) if pd.notna(row.get('ICD10_3_Code_Desc')) else None,
                'who_full_desc': str(row['WHO_Full_Desc']) if pd.notna(row.get('WHO_Full_Desc')) else '',
                
                # Boolean flags
                'valid_clinical_use': row.get('Valid_ICD10_ClinicalUse') == 'Y',
                'valid_primary': row.get('Valid_ICD10_Primary') == 'Y',
                'valid_asterisk': row.get('Valid_ICD10_Asterisk') == 'Y',
                'valid_dagger': row.get('Valid_ICD10_Dagger') == 'Y',
                
                # Restrictions
                'age_range': str(row['Age_Range']) if pd.notna(row.get('Age_Range')) else None,
                'gender': str(row['Gender']) if pd.notna(row.get('Gender')) else None,
                'status': str(row['Status']) if pd.notna(row.get('Status')) else None,
                
                # Dates - convert to ISO string format
                'who_start_date': row['WHO_Start_date'].date().isoformat() if pd.notna(row.get('WHO_Start_date')) else None,
                'who_end_date': row['WHO_End_date'].date().isoformat() if pd.notna(row.get('WHO_End_date')) else None,
                'sa_start_date': row['SA_Start_Date'].date().isoformat() if pd.notna(row.get('SA_Start_Date')) else None,
                'sa_end_date': row['SA_End_Date'].date().isoformat() if pd.notna(row.get('SA_End_Date')) else None,
            }
            
            codes_to_insert.append(code_data)
    
    print(f"📝 Prepared {len(codes_to_insert)} codes for insertion")
    
    # Insert in batches (Supabase has limits)
    batch_size = 1000
    total_inserted = 0
    
    for i in range(0, len(codes_to_insert), batch_size):
        batch = codes_to_insert[i:i + batch_size]
        
        try:
            # Use upsert to handle duplicates
            result = supabase.table('icd10_codes').upsert(batch).execute()
            total_inserted += len(batch)
            print(f"✅ Inserted batch {i//batch_size + 1}: {total_inserted}/{len(codes_to_insert)} codes")
        except Exception as e:
            print(f"❌ Error inserting batch {i//batch_size + 1}: {e}")
            # Continue with next batch
    
    print(f"\n🎉 ICD-10 loading complete! Total inserted: {total_inserted}")
    
    # Verify insertion
    count_result = supabase.table('icd10_codes').select('code', count='exact').execute()
    print(f"📊 Total codes in database: {count_result.count}")
    
    # Show sample codes
    sample = supabase.table('icd10_codes').select('*').limit(5).execute()
    print("\n📋 Sample codes:")
    for code in sample.data:
        print(f"  - {code['code']}: {code['who_full_desc']}")

if __name__ == '__main__':
    load_icd10_codes()
