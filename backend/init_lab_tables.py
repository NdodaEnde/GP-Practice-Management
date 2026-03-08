"""
Initialize Lab Orders & Results Tables in Supabase
Run this after executing lab_orders_results_migration.sql in Supabase Dashboard
"""
import os
import sys
sys.path.append('/app/backend')

from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpenVqdGJlam5ucmRxY3ltZ2xlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDMyMTc0NiwiZXhwIjoyMDc1ODk3NzQ2fQ.g8gqEs3Ynb_577txVNjnp8_PYkuBNdac3LxeyBETppw')

def check_lab_tables():
    """Verify lab_orders and lab_results tables exist"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    tables_status = {}
    
    print("🔍 Checking lab tables...")
    
    # Check lab_orders
    try:
        result = supabase.table('lab_orders').select('id', count='exact').limit(1).execute()
        print(f"  ✅ lab_orders table exists")
        print(f"  📊 Current orders: {result.count}")
        tables_status['lab_orders'] = True
    except Exception as e:
        print(f"  ❌ lab_orders table - {str(e)}")
        tables_status['lab_orders'] = False
    
    # Check lab_results
    try:
        result = supabase.table('lab_results').select('id', count='exact').limit(1).execute()
        print(f"  ✅ lab_results table exists")
        print(f"  📊 Current results: {result.count}")
        tables_status['lab_results'] = True
    except Exception as e:
        print(f"  ❌ lab_results table - {str(e)}")
        tables_status['lab_results'] = False
    
    return all(tables_status.values())

if __name__ == '__main__':
    print("=" * 70)
    print("LAB ORDERS & RESULTS TABLES - Initialization Check")
    print("=" * 70)
    
    if check_lab_tables():
        print("\n✅ Lab tables exist!")
        print("\nReady to track:")
        print("  - Lab test orders (PathCare, Lancet, Ampath, etc.)")
        print("  - Test results with values and reference ranges")
        print("  - Abnormal result flagging")
        print("  - Historical trending for repeat tests")
        print("\nAPI Endpoints available:")
        print("  - POST /api/lab-orders - Create order")
        print("  - POST /api/lab-results - Record result")
        print("  - GET /api/lab-orders/patient/{id} - Patient orders")
        print("  - GET /api/lab-results/patient/{id}/test/{name} - Test history")
        print("  - GET /api/lab-results/patient/{id}/abnormal - Flagged results")
    else:
        print("\n⚠️  Lab tables are missing!")
        print("\nPlease run the SQL migration:")
        print("1. Open Supabase Dashboard → SQL Editor")
        print("2. Copy /app/backend/database/lab_orders_results_migration.sql")
        print("3. Paste and execute in SQL Editor")
        print("4. Run this script again to verify")
    
    print("=" * 70)
