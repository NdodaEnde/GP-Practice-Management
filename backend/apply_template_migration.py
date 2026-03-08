#!/usr/bin/env python3
"""
Apply template columns migration using Supabase client
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment")
    sys.exit(1)

def run_migration():
    """Run the template columns migration using Supabase RPC"""
    
    print("🔄 Starting template columns migration...")
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        print("✅ Connected to Supabase")
        
        # Execute each ALTER TABLE statement individually
        statements = [
            "ALTER TABLE digitised_documents ADD COLUMN IF NOT EXISTS template_id TEXT",
            "ALTER TABLE digitised_documents ADD COLUMN IF NOT EXISTS template_used BOOLEAN DEFAULT FALSE",
            "ALTER TABLE digitised_documents ADD COLUMN IF NOT EXISTS records_created INTEGER DEFAULT 0",
            "ALTER TABLE digitised_documents ADD COLUMN IF NOT EXISTS tables_populated JSONB DEFAULT '{}'::jsonb",
        ]
        
        for i, stmt in enumerate(statements, 1):
            try:
                print(f"  [{i}/{len(statements)}] Executing: {stmt[:60]}...")
                # Use RPC to execute SQL
                result = supabase.rpc('exec_sql', {'query': stmt}).execute()
                print(f"     ✅ Success")
            except Exception as e:
                error_msg = str(e)
                if 'already exists' in error_msg or 'column already exists' in error_msg:
                    print(f"     ⚠️  Column already exists, skipping")
                elif 'exec_sql' not in error_msg and 'does not exist' not in error_msg:
                    # Real error, not just missing RPC function
                    raise
                else:
                    print(f"     ⚠️  RPC function not available, manual migration needed")
                    print("\n📋 Please run this SQL manually in Supabase SQL Editor:")
                    print("=" * 70)
                    with open('database/add_template_columns_migration.sql', 'r') as f:
                        print(f.read())
                    print("=" * 70)
                    return
        
        # Create index
        try:
            print(f"\n  Creating index...")
            result = supabase.rpc('exec_sql', {
                'query': 'CREATE INDEX IF NOT EXISTS idx_digitised_docs_template ON digitised_documents(template_id)'
            }).execute()
            print(f"  ✅ Index created")
        except Exception as e:
            if 'already exists' not in str(e):
                print(f"  ⚠️  Index creation: {e}")
        
        print("\n✅ Migration completed successfully!")
        print("\n📊 New columns added to digitised_documents:")
        print("   - template_id (TEXT)")
        print("   - template_used (BOOLEAN)")
        print("   - records_created (INTEGER)")
        print("   - tables_populated (JSONB)")
        
    except Exception as e:
        print(f"\n❌ Error running migration: {e}")
        print("\n📋 Please run this SQL manually in Supabase SQL Editor:")
        print("=" * 70)
        with open('database/add_template_columns_migration.sql', 'r') as f:
            print(f.read())
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
