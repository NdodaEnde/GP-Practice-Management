#!/usr/bin/env python3
"""
Initialize workspaces table and seed demo workspace
"""

import os
import sys
from supabase import create_client, Client
from datetime import datetime, timezone
import uuid

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
        
        print("\n⚠️  IMPORTANT: Make sure you've created the 'workspaces' table in Supabase first!")
        print("   Run the SQL from: /app/backend/database/workspaces_migration.sql")
        print("   in the Supabase SQL Editor\n")
        
        input("Press Enter to continue once the table is created...")
        
        # Check if demo workspace already exists
        print("\n🔍 Checking for existing workspaces...")
        try:
            existing = supabase.table('workspaces').select('slug').eq('slug', 'demo-gp-workspace').execute()
            
            if existing.data:
                print(f"ℹ️  Found {len(existing.data)} existing workspace(s)")
                response = input("\n❓ Do you want to skip creating demo workspace? (y/n): ")
                if response.lower() == 'y':
                    print("✅ Skipping workspace creation")
                    return
        except Exception as e:
            print(f"⚠️  Could not query workspaces table. Make sure it exists!")
            print(f"   Error: {e}")
            return
        
        # Create demo workspace
        print("\n🏢 Creating demo workspace...")
        
        workspace_data = {
            'id': str(uuid.uuid4()),
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
            'created_at': datetime.now(timezone.utc).isoformat(),
            'settings': {
                'features': {
                    'digitization': True,
                    'validation_queue': True,
                    'batch_upload': True,
                    'api_access': True
                },
                'branding': {
                    'logo_url': None,
                    'primary_color': '#14b8a6'
                }
            }
        }
        
        try:
            result = supabase.table('workspaces').insert(workspace_data).execute()
            
            if result.data:
                print(f"   ✅ Created workspace: {workspace_data['name']} (slug: {workspace_data['slug']})")
                workspace_id = result.data[0]['id']
                
                # Update existing users to link to this workspace
                print("\n🔗 Linking existing users to workspace...")
                users_result = supabase.table('users').select('id').execute()
                
                if users_result.data:
                    for user in users_result.data:
                        try:
                            # Create workspace_user relationship
                            workspace_user_data = {
                                'workspace_id': workspace_id,
                                'user_id': user['id'],
                                'role': 'member',
                                'joined_at': datetime.now(timezone.utc).isoformat()
                            }
                            supabase.table('workspace_users').insert(workspace_user_data).execute()
                            print(f"   ✅ Linked user {user['id']} to workspace")
                        except Exception as e:
                            if 'duplicate key' not in str(e).lower():
                                print(f"   ⚠️  Error linking user {user['id']}: {e}")
            else:
                print(f"   ⚠️  Failed to create workspace")
        except Exception as e:
            if 'duplicate key' in str(e).lower() or 'unique constraint' in str(e).lower():
                print(f"   ℹ️  Workspace already exists: {workspace_data['slug']}")
            else:
                print(f"   ❌ Error creating workspace: {e}")
                raise
        
        print("\n" + "="*60)
        print("✅ WORKSPACE INITIALIZATION COMPLETE")
        print("="*60)
        print("\n📝 Demo Workspace Created:")
        print(f"   Name: {workspace_data['name']}")
        print(f"   Slug: {workspace_data['slug']}")
        print(f"   Organization: {workspace_data['organization_name']}")
        print(f"   Type: {workspace_data['organization_type']}")
        print(f"   Subscription: {workspace_data['subscription_tier']}")
        print(f"   Max Users: {workspace_data['max_users']}")
        print(f"   Max Documents: {workspace_data['max_documents']}")
        print(f"   Storage: {workspace_data['storage_quota_gb']} GB")
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
