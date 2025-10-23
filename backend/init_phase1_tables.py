"""
Initialize Phase 1 Tables in Supabase
Run this after executing phase1_patient_safety_migration.sql in Supabase Dashboard
"""
import os
import sys
sys.path.append('/app/backend')

from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpenVqdGJlam5ucmRxY3ltZ2xlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDMyMTc0NiwiZXhwIjoyMDc1ODk3NzQ2fQ.g8gqEs3Ynb_577txVNjnp8_PYkuBNdac3LxeyBETppw')

def check_tables():
    """Verify Phase 1 tables exist"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("🔍 Checking Phase 1 tables...")
    tables = ['allergies', 'vitals', 'icd10_codes', 'diagnoses', 'document_refs']
    
    all_exist = True
    for table in tables:
        try:
            result = supabase.table(table).select('*').limit(1).execute()
            print(f"  ✅ {table}")
        except Exception as e:
            print(f"  ❌ {table} - {str(e)[:50]}")
            all_exist = False
    
    return all_exist

if __name__ == '__main__':
    print("=" * 70)
    print("PHASE 1: PATIENT SAFETY TABLES - Initialization Check")
    print("=" * 70)
    
    if check_tables():
        print("\n✅ All Phase 1 tables exist!")
        print("\nNext step: Load ICD-10 codes")
        print("Run: python load_icd10_codes.py")
    else:
        print("\n⚠️  Some tables are missing!")
        print("\nPlease run the SQL migration:")
        print("1. Open Supabase Dashboard → SQL Editor")
        print("2. Copy /app/backend/database/phase1_patient_safety_migration.sql")
        print("3. Paste and execute in SQL Editor")
        print("4. Run this script again to verify")
    
    print("=" * 70)
