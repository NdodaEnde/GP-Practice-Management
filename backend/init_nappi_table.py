"""
Initialize NAPPI Codes Table in Supabase
Run this after executing nappi_codes_migration.sql in Supabase Dashboard
"""
import os
import sys
sys.path.append('/app/backend')

from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def check_nappi_table():
    """Verify NAPPI codes table exists"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("🔍 Checking NAPPI codes table...")
    try:
        result = supabase.table('nappi_codes').select('nappi_code', count='exact').limit(1).execute()
        print(f"  ✅ nappi_codes table exists")
        print(f"  📊 Current count: {result.count} codes")
        return True
    except Exception as e:
        print(f"  ❌ nappi_codes table - {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("NAPPI CODES TABLE - Initialization Check")
    print("=" * 70)
    
    if check_nappi_table():
        print("\n✅ NAPPI codes table exists!")
        print("\nNext step: Load NAPPI codes from CSV")
        print("Usage: python load_nappi_codes.py <path_to_csv>")
        print("\nExpected CSV format:")
        print("  Brand Name, Generic Name, Schedule, Strength/Dosage Form, Ingredients")
    else:
        print("\n⚠️  NAPPI codes table is missing!")
        print("\nPlease run the SQL migration:")
        print("1. Open Supabase Dashboard → SQL Editor")
        print("2. Copy /app/backend/database/nappi_codes_migration.sql")
        print("3. Paste and execute in SQL Editor")
        print("4. Run this script again to verify")
    
    print("=" * 70)
