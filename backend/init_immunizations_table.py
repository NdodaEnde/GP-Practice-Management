"""
Initialize Immunizations Table in Supabase
Run this after executing immunizations_migration.sql in Supabase Dashboard
"""
import os
import sys
sys.path.append('/app/backend')

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def check_immunizations_table():
    """Verify immunizations table exists"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("🔍 Checking immunizations table...")
    try:
        result = supabase.table('immunizations').select('id', count='exact').limit(1).execute()
        print(f"  ✅ immunizations table exists")
        print(f"  📊 Current count: {result.count} immunizations")
        return True
    except Exception as e:
        print(f"  ❌ immunizations table - {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("IMMUNIZATIONS TABLE - Initialization Check")
    print("=" * 70)
    
    if check_immunizations_table():
        print("\n✅ Immunizations table exists!")
        print("\nReady to track:")
        print("  - COVID-19 vaccines")
        print("  - Influenza vaccines")
        print("  - Hepatitis B series")
        print("  - Occupational health immunizations")
        print("  - Dose schedules and series completion")
        print("\nAPI Endpoints available:")
        print("  - POST /api/immunizations - Create immunization")
        print("  - GET /api/immunizations/patient/{id} - Patient immunizations")
        print("  - GET /api/immunizations/patient/{id}/summary - Summary by vaccine")
        print("  - GET /api/immunizations/patient/{id}/occupational - Occ health")
        print("  - GET /api/immunizations/overdue - Overdue doses")
    else:
        print("\n⚠️  Immunizations table is missing!")
        print("\nPlease run the SQL migration:")
        print("1. Open Supabase Dashboard → SQL Editor")
        print("2. Copy /app/backend/database/immunizations_migration.sql")
        print("3. Paste and execute in SQL Editor")
        print("4. Run this script again to verify")
    
    print("=" * 70)
