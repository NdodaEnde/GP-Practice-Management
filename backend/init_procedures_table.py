"""
Initialize Procedures Table in Supabase
Run this after executing procedures_migration.sql in Supabase Dashboard
"""
import os
import sys
sys.path.append('/app/backend')

from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def check_procedures_table():
    """Verify procedures table exists"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("🔍 Checking procedures table...")
    try:
        result = supabase.table('procedures').select('id', count='exact').limit(1).execute()
        print(f"  ✅ procedures table exists")
        print(f"  📊 Current count: {result.count} procedures")
        return True
    except Exception as e:
        print(f"  ❌ procedures table - {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("PROCEDURES TABLE - Initialization Check")
    print("=" * 70)
    
    if check_procedures_table():
        print("\n✅ Procedures table exists!")
        print("\nReady to track:")
        print("  - Surgical procedures")
        print("  - Diagnostic procedures")
        print("  - Therapeutic procedures")
        print("  - Preventive procedures")
        print("\nAPI Endpoints available:")
        print("  - POST /api/procedures - Create procedure")
        print("  - GET /api/procedures/patient/{id} - Patient procedures")
        print("  - GET /api/procedures/patient/{id}/surgical-history - Surgeries")
        print("  - GET /api/procedures/patient/{id}/billable - Billing")
        print("  - GET /api/procedures/follow-up/due - Due follow-ups")
    else:
        print("\n⚠️  Procedures table is missing!")
        print("\nPlease run the SQL migration:")
        print("1. Open Supabase Dashboard → SQL Editor")
        print("2. Copy /app/backend/database/procedures_migration.sql")
        print("3. Paste and execute in SQL Editor")
        print("4. Run this script again to verify")
    
    print("=" * 70)
