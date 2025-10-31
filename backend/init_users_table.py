#!/usr/bin/env python3
"""
Initialize users table and seed demo users
Uses Supabase client for table operations
"""

import os
import sys
from supabase import create_client, Client
from passlib.context import CryptContext
from datetime import datetime, timezone
import uuid

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
        
        # Note: You need to create the users table manually in Supabase dashboard first
        # Or use the SQL editor to run the users_migration.sql file
        
        print("\n⚠️  IMPORTANT: Make sure you've created the 'users' table in Supabase first!")
        print("   Run the SQL from: /app/backend/database/users_migration.sql")
        print("   in the Supabase SQL Editor\n")
        
        input("Press Enter to continue once the table is created...")
        
        # Check if demo users already exist
        print("\n🔍 Checking for existing users...")
        try:
            existing_users = supabase.table('users').select('email').execute()
            
            if existing_users.data:
                print(f"ℹ️  Found {len(existing_users.data)} existing users:")
                for user in existing_users.data:
                    print(f"   - {user['email']}")
                
                response = input("\n❓ Do you want to skip creating demo users? (y/n): ")
                if response.lower() == 'y':
                    print("✅ Skipping user creation")
                    return
        except Exception as e:
            print(f"⚠️  Could not query users table. Make sure it exists!")
            print(f"   Error: {e}")
            return
        
        # Demo workspace/tenant IDs
        DEMO_WORKSPACE_ID = 'demo-gp-workspace-001'
        DEMO_TENANT_ID = 'demo-tenant-001'
        
        # Create demo users
        print("\n👥 Creating demo users...")
        demo_users = [
            {
                'id': str(uuid.uuid4()),
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
                'id': str(uuid.uuid4()),
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
                'id': str(uuid.uuid4()),
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
        
        created_count = 0
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
            
            try:
                # Insert user
                result = supabase.table('users').insert(user_record).execute()
                
                if result.data:
                    print(f"   ✅ Created user: {user_data['email']} (role: {user_data['role']})")
                    created_count += 1
                else:
                    print(f"   ⚠️  Failed to create user: {user_data['email']}")
            except Exception as e:
                if 'duplicate key' in str(e).lower() or 'unique constraint' in str(e).lower():
                    print(f"   ℹ️  User already exists: {user_data['email']}")
                else:
                    print(f"   ❌ Error creating user {user_data['email']}: {e}")
        
        print("\n" + "="*60)
        print(f"✅ USER INITIALIZATION COMPLETE ({created_count} users created)")
        print("="*60)
        print("\n📝 Demo Accounts:")
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
