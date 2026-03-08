#!/usr/bin/env python3
"""
Apply template columns migration to digitised_documents table
Adds support for template-driven extraction tracking
"""

import os
import sys
from pathlib import Path
from postgrest import SyncPostgrestClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment")
    sys.exit(1)

def run_migration():
    """Run the template columns migration"""
    
    print("🔄 Starting template columns migration...")
    
    try:
        # Read the migration SQL
        migration_file = Path(__file__).parent / 'database' / 'add_template_columns_migration.sql'
        with open(migration_file, 'r') as f:
            sql_content = f.read()
        
        print(f"📄 Loaded migration from: {migration_file}")
        
        # Execute using Supabase RPC or direct SQL
        # Note: Supabase's REST API doesn't directly support DDL
        # We'll use psycopg2 directly
        import psycopg2
        from urllib.parse import urlparse
        
        # Parse Supabase URL to get PostgreSQL connection details
        # You'll need the direct PostgreSQL connection string from Supabase dashboard
        print("⚠️  Please run this SQL manually in Supabase SQL Editor:")
        print("=" * 60)
        print(sql_content)
        print("=" * 60)
        print("\nOr set SUPABASE_DB_URL environment variable with direct PostgreSQL connection string")
        
        # Check if we have direct database URL
        db_url = os.getenv('SUPABASE_DB_URL')
        if db_url:
            print("\n🔄 Attempting direct database connection...")
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Split and execute each statement
            statements = [s.strip() for s in sql_content.split(';') if s.strip()]
            for stmt in statements:
                if stmt:
                    print(f"  Executing: {stmt[:50]}...")
                    cursor.execute(stmt)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("✅ Migration applied successfully!")
        else:
            print("\n💡 To apply automatically, add SUPABASE_DB_URL to .env:")
            print("   SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres")
        
    except FileNotFoundError:
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
