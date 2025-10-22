"""
Initialize digitised_documents table in Supabase for Phase 1.7
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_digitised_documents_table():
    """Create digitised_documents table"""
    
    # Read SQL schema
    with open('database/digitised_documents_schema.sql', 'r') as f:
        sql_commands = f.read()
    
    print("Creating digitised_documents table in Supabase...")
    
    # Execute via Supabase API
    try:
        # Note: Supabase doesn't support direct SQL execution via Python client
        # This SQL needs to be run in Supabase SQL Editor or via psycopg2
        print("\n⚠️  Please run the SQL commands manually in Supabase SQL Editor:")
        print("\n" + "="*60)
        print(sql_commands)
        print("="*60 + "\n")
        
        print("After running the SQL, the table will be ready.")
        print("\nTable structure:")
        print("- id (primary key)")
        print("- workspace_id")
        print("- filename")
        print("- file_path")
        print("- status (uploaded/parsing/parsed/extracting/extracted/validated/approved)")
        print("- patient_id (FK)")
        print("- parsed_doc_id (MongoDB ref)")
        print("- And more metadata fields...")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    init_digitised_documents_table()
