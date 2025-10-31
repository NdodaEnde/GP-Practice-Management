#!/usr/bin/env python3
"""
Initialize users table and seed demo users
Uses psycopg2 for direct SQL execution
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from passlib.context import CryptContext
from datetime import datetime, timezone

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database connection string
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    # Try constructing from individual parts
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD', '')
    
    if 'supabase.co' in SUPABASE_URL:
        # Extract project ref from URL
        project_ref = SUPABASE_URL.split('//')[1].split('.')[0]
        DATABASE_URL = f"postgresql://postgres:{SUPABASE_DB_PASSWORD}@db.{project_ref}.supabase.co:5432/postgres"

if not DATABASE_URL:
    print("❌ Missing DATABASE_URL in environment")
    print("   Please set DATABASE_URL or SUPABASE_URL + SUPABASE_DB_PASSWORD")
    sys.exit(1)

def main():
    conn = None
    try:
        print("🔄 Connecting to PostgreSQL database...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Read migration SQL
        print("📄 Reading users migration SQL...")
        migration_path = os.path.join(os.path.dirname(__file__), 'database', 'users_migration.sql')
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Execute migration
        print("🔨 Creating users table...")
        cur.execute(migration_sql)
        conn.commit()
        print("✅ Users table created successfully")
        
        # Check if demo users already exist
        print("\n🔍 Checking for existing users...")
        cur.execute("SELECT email FROM users")
        existing_users = cur.fetchall()
        
        if existing_users:
            print(f"ℹ️  Found {len(existing_users)} existing users")
            print("   Skipping seed data to avoid duplicates")
            cur.close()
            conn.close()
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
            
            # Insert user
            cur.execute("""
                INSERT INTO users (
                    email, password_hash, first_name, last_name, role,
                    workspace_id, tenant_id, is_active, is_verified, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, email, role
            """, (
                user_data['email'],
                password_hash,
                user_data['first_name'],
                user_data['last_name'],
                user_data['role'],
                user_data['workspace_id'],
                user_data['tenant_id'],
                user_data['is_active'],
                user_data['is_verified'],
                datetime.now(timezone.utc)
            ))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                print(f"   ✅ Created user: {result['email']} (role: {result['role']}, id: {result['id']})")
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
        
        cur.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
