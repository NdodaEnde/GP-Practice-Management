#!/usr/bin/env python3
"""
Quick workspace table creator - inserts demo workspace directly
"""

import os
import sys
from supabase import create_client, Client
from datetime import datetime, timezone
import uuid

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    sys.exit(1)

def main():
    try:
        print("🔄 Connecting to Supabase...")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        print("\n" + "="*70)
        print("⚠️  MANUAL STEP REQUIRED")
        print("="*70)
        print("\nThe 'workspaces' table needs to be created in Supabase first.")
        print("\n📋 Steps:")
        print("1. Open Supabase Dashboard: https://supabase.com/dashboard")
        print("2. Go to SQL Editor")
        print("3. Copy the SQL from: /app/backend/database/workspaces_migration.sql")
        print("4. Paste and run it in SQL Editor")
        print("\n" + "="*70)
        
        response = input("\nHave you created the workspaces table? (yes/no): ")
        
        if response.lower() != 'yes':
            print("\n✋ Please create the table first, then run this script again.")
            print("   Location: /app/backend/database/workspaces_migration.sql")
            sys.exit(0)
        
        # Test if table exists
        print("\n🔍 Testing if workspaces table exists...")
        try:
            test = supabase.table('workspaces').select('id').limit(1).execute()
            print("✅ Workspaces table exists!")
        except Exception as e:
            print(f"❌ Workspaces table not found: {e}")
            print("\n   Please run the SQL migration first.")
            sys.exit(1)
        
        # Check if demo workspace exists
        existing = supabase.table('workspaces').select('slug').eq('slug', 'demo-gp-workspace').execute()
        
        if existing.data:
            print(f"\n✅ Demo workspace already exists!")
            print(f"   Found: {len(existing.data)} workspace(s)")
            return
        
        # Create demo workspace
        print("\n🏢 Creating demo workspace...")
        
        workspace_id = str(uuid.uuid4())
        workspace_data = {
            'id': workspace_id,
            'name': 'Demo GP Practice',
            'slug': 'demo-gp-workspace',
            'organization_name': 'Demo General Practice',
            'organization_type': 'gp_practice',
            'contact_email': 'admin@demo-gp.co.za',
            'contact_phone': '+27 11 123 4567',
            'contact_person': 'Dr. John Smith',
            'address_line1': '123 Medical Street',
            'city': 'Johannesburg',
            'province': 'Gauteng',
            'postal_code': '2000',
            'country': 'South Africa',
            'subscription_tier': 'professional',
            'subscription_status': 'active',
            'billing_email': 'billing@demo-gp.co.za',
            'tenant_id': 'demo-tenant-001',
            'max_users': 50,
            'max_documents': 10000,
            'storage_quota_gb': 100,
            'is_active': True,
            'is_trial': False,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = supabase.table('workspaces').insert(workspace_data).execute()
        
        if result.data:
            print(f"   ✅ Created workspace: {workspace_data['name']}")
            
            # Link existing users to workspace
            print("\n🔗 Linking existing users to workspace...")
            users = supabase.table('users').select('id, email').execute()
            
            for user in users.data:
                try:
                    link_data = {
                        'workspace_id': workspace_id,
                        'user_id': user['id'],
                        'role': 'member',
                        'joined_at': datetime.now(timezone.utc).isoformat()
                    }
                    supabase.table('workspace_users').insert(link_data).execute()
                    print(f"   ✅ Linked: {user['email']}")
                except Exception as e:
                    if 'duplicate' not in str(e).lower():
                        print(f"   ⚠️  Error linking {user['email']}: {e}")
        
        print("\n" + "="*70)
        print("✅ WORKSPACE SETUP COMPLETE")
        print("="*70)
        print(f"\n📝 Workspace Details:")
        print(f"   Name: {workspace_data['name']}")
        print(f"   Slug: {workspace_data['slug']}")
        print(f"   Organization: {workspace_data['organization_name']}")
        print(f"   Subscription: {workspace_data['subscription_tier']}")
        print(f"   Max Users: {workspace_data['max_users']}")
        print(f"   Users Linked: {len(users.data)}")
        print("\n" + "="*70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
