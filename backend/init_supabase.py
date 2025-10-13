#!/usr/bin/env python3
"""Initialize Supabase database schema"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

supabase_url = os.environ['SUPABASE_URL']
supabase_key = os.environ['SUPABASE_SERVICE_KEY']

print(f"Connecting to Supabase: {supabase_url}")
supabase: Client = create_client(supabase_url, supabase_key)

# Read SQL file
sql_file = ROOT_DIR / 'setup_supabase.sql'
with open(sql_file, 'r') as f:
    sql_content = f.read()

# Split by semicolons and execute each statement
statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]

print(f"\nExecuting {len(statements)} SQL statements...")

for i, statement in enumerate(statements, 1):
    try:
        # Skip empty statements and comments
        if not statement or statement.startswith('--'):
            continue
        
        print(f"\n[{i}/{len(statements)}] Executing: {statement[:100]}...")
        
        # Execute via Supabase REST API (for tables)
        # Note: Supabase Python client doesn't directly support raw SQL execution
        # We'll use the rpc method or direct HTTP call
        result = supabase.rpc('exec_sql', {'sql': statement}).execute()
        print(f"  ✓ Success")
    except Exception as e:
        # Some statements might fail if tables already exist - that's okay
        if 'already exists' in str(e).lower():
            print(f"  ⚠ Already exists (skipping)")
        else:
            print(f"  ✗ Error: {e}")

print("\n✓ Database initialization complete!")
print("\nNote: If you see errors about 'exec_sql' not existing, you need to:")
print("1. Go to Supabase Dashboard > SQL Editor")
print("2. Copy and paste the contents of setup_supabase.sql")
print("3. Run it manually")
print("\nAlternatively, the backend will create the demo tenant/workspace on startup.")
