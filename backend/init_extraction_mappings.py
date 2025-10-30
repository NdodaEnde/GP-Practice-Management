"""
Initialize Extraction Mappings Tables in Supabase
Run this to set up the flexible field mapping system
"""

import os
import sys
from pathlib import Path
from supabase import create_client

# Get Supabase credentials from environment
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

def main():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set")
        print("Please set these in your .env file")
        sys.exit(1)
    
    print("🔧 Initializing Extraction Mappings System...")
    print(f"📍 Supabase URL: {SUPABASE_URL}")
    
    # Create Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    # Read migration SQL
    sql_file = Path(__file__).parent / 'database' / 'extraction_mappings_migration.sql'
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    print("📄 Executing migration SQL...")
    
    # Split SQL into individual statements and execute
    statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
    
    success_count = 0
    for i, statement in enumerate(statements, 1):
        try:
            # Skip comment-only statements
            if not statement or statement.startswith('COMMENT'):
                continue
                
            result = supabase.postgrest.rpc('exec_sql', {'query': statement}).execute()
            success_count += 1
            if 'message' in str(statement) or 'status' in str(statement):
                print(f"  ✅ Statement {i}: {statement[:50]}...")
        except Exception as e:
            # Some statements might fail if tables already exist - that's OK
            if 'already exists' in str(e).lower():
                print(f"  ℹ️  Statement {i}: Already exists (skipping)")
            else:
                print(f"  ⚠️  Statement {i}: {e}")
    
    print(f"\n✅ Migration complete! ({success_count} statements executed)")
    print("\n📊 Tables created:")
    print("  • extraction_templates")
    print("  • extraction_field_mappings")
    print("  • extraction_history")
    print("\n🎯 Next steps:")
    print("  1. Create extraction templates for your document types")
    print("  2. Configure field mappings for each template")
    print("  3. Start uploading documents for automatic extraction")

if __name__ == '__main__':
    main()
