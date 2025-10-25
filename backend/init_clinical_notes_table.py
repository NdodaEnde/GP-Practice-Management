"""
Initialize Clinical Notes Table in Supabase
Run this after executing clinical_notes_migration.sql in Supabase Dashboard
"""
import os
import sys
sys.path.append('/app/backend')

from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpenVqdGJlam5ucmRxY3ltZ2xlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDMyMTc0NiwiZXhwIjoyMDc1ODk3NzQ2fQ.g8gqEs3Ynb_577txVNjnp8_PYkuBNdac3LxeyBETppw')

def check_clinical_notes_table():
    """Verify clinical_notes table exists"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("🔍 Checking clinical_notes table...")
    try:
        result = supabase.table('clinical_notes').select('id', count='exact').limit(1).execute()
        print(f"  ✅ clinical_notes table exists")
        print(f"  📊 Current count: {result.count} notes")
        return True
    except Exception as e:
        print(f"  ❌ clinical_notes table - {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("CLINICAL NOTES TABLE - Initialization Check")
    print("=" * 70)
    
    if check_clinical_notes_table():
        print("\n✅ Clinical notes table exists!")
        print("\nReady to use structured SOAP notes")
        print("\nAI Scribe will now save:")
        print("  - Subjective section")
        print("  - Objective section")
        print("  - Assessment section")
        print("  - Plan section")
        print("  - Full text (for backward compatibility)")
    else:
        print("\n⚠️  Clinical notes table is missing!")
        print("\nPlease run the SQL migration:")
        print("1. Open Supabase Dashboard → SQL Editor")
        print("2. Copy /app/backend/database/clinical_notes_migration.sql")
        print("3. Paste and execute in SQL Editor")
        print("4. Run this script again to verify")
    
    print("=" * 70)
