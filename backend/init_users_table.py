#!/usr/bin/env python3
"""
Initialize users table and seed demo users
"""

import os
import sys
from supabase import create_client, Client
from passlib.context import CryptContext
from datetime import datetime, timezone

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment")
    sys.exit(1)

def main():
    try:
        print("🔄 Connecting to Supabase...")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Read migration SQL
        print("📄 Reading users migration SQL...")
        migration_path = os.path.join(os.path.dirname(__file__), 'database', 'users_migration.sql')
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Execute migration
        print("🔨 Creating users table...")
        result = supabase.rpc('exec_sql', {'query': migration_sql}).execute()
        print("✅ Users table created successfully")
        
        # Check if demo users already exist
        print("\n🔍 Checking for existing users...")
        existing_users = supabase.table('users').select('email').execute()
        
        if existing_users.data:
            print(f"ℹ️  Found {len(existing_users.data)} existing users")
            print("   Skipping seed data to avoid duplicates")
            return
        
        # Demo workspace/tenant IDs
        DEMO_WORKSPACE_ID = 'demo-gp-workspace-001'
        DEMO_TENANT_ID = 'demo-tenant-001'
        
        # Create demo users
        print("\n👥 Creating demo users...")
        demo_users = [
            {
                'email': 'admin@surgiscan.com',
                'password': 'password123',
                'first_name': 'Admin',
                'last_name': 'User',
                'role': 'admin',
                'workspace_id': DEMO_WORKSPACE_ID,
                'tenant_id': DEMO_TENANT_ID,
                'is_active': True,
                'is_verified': True
            },
            {
                'email': 'validator@surgiscan.com',
                'password': 'password123',
                'first_name': 'Validator',
                'last_name': 'User',
                'role': 'validator',
                'workspace_id': DEMO_WORKSPACE_ID,
                'tenant_id': DEMO_TENANT_ID,
                'is_active': True,
                'is_verified': True
            },
            {
                'email': 'uploader@surgiscan.com',
                'password': 'password123',
                'first_name': 'Uploader',
                'last_name': 'User',
                'role': 'uploader',
                'workspace_id': DEMO_WORKSPACE_ID,
                'tenant_id': DEMO_TENANT_ID,
                'is_active': True,
                'is_verified': True
            }
        ]
        
        for user_data in demo_users:
            # Hash password
            password = user_data.pop('password')
            password_hash = pwd_context.hash(password)
            
            # Prepare user record
            user_record = {
                **user_data,
                'password_hash': password_hash,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Insert user
            result = supabase.table('users').insert(user_record).execute()
            
            if result.data:
                print(f"   ✅ Created user: {user_data['email']} (role: {user_data['role']})")
            else:
                print(f"   ⚠️  Failed to create user: {user_data['email']}")
        
        print("\n" + "="*60)
        print("✅ USER INITIALIZATION COMPLETE")
        print("="*60)
        print("\n📝 Demo Accounts Created:")
        print("   1. admin@surgiscan.com (password: password123)")
        print("   2. validator@surgiscan.com (password: password123)")
        print("   3. uploader@surgiscan.com (password: password123)")
        print("\n🔐 All users are active and verified")
        print(f"🏢 Workspace: {DEMO_WORKSPACE_ID}")
        print(f"🏷️  Tenant: {DEMO_TENANT_ID}")
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
