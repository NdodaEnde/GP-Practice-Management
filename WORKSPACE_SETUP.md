# Workspace Setup Guide

## Current Status
✅ Workspace management API built and integrated
✅ Workspace database schema created
❌ Workspace table needs to be created in Supabase (manual step)

## How to Complete Setup

### Step 1: Create Workspaces Table in Supabase

**Option A: Using Supabase Dashboard (Recommended)**

1. Go to: https://supabase.com/dashboard
2. Select your project
3. Navigate to: **SQL Editor**
4. Click **New Query**
5. Copy the entire contents of: `/app/backend/database/workspaces_migration.sql`
6. Paste into SQL Editor
7. Click **Run** or press `Ctrl+Enter`
8. You should see: ✅ Success message

**Option B: Using Supabase CLI (if installed)**

```bash
supabase db push
```

### Step 2: Seed Demo Workspace

After creating the table, run:

```bash
cd /app/backend
export $(cat .env | grep -v '^#' | xargs)
python3 quick_workspace_setup.py
```

This will:
- Create demo workspace: "Demo GP Practice"
- Link existing users to the workspace
- Set up workspace_users relationships

### Step 3: Verify Setup

Check if workspace was created:

```bash
python3 << 'EOF'
from supabase import create_client
import os

supabase = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_KEY']
)

result = supabase.table('workspaces').select('*').execute()
print(f"Workspaces found: {len(result.data)}")
for ws in result.data:
    print(f"  - {ws['name']} ({ws['slug']})")
EOF
```

## What You Get After Setup

### 1. Multi-Tenant Architecture
- Each client gets their own workspace
- Data isolation by workspace_id
- Separate user teams per workspace

### 2. Workspace Features
- Organization details
- Contact information
- Subscription tiers (free, basic, professional, enterprise)
- Usage quotas (max users, documents, storage)
- Active/inactive status

### 3. API Endpoints Available
- `GET /api/workspaces/` - List all workspaces (admin)
- `GET /api/workspaces/{id}` - Get workspace details
- `POST /api/workspaces/` - Create new workspace (admin)
- `PUT /api/workspaces/{id}` - Update workspace (admin)
- `DELETE /api/workspaces/{id}` - Deactivate workspace (admin)
- `GET /api/workspaces/stats/summary` - Get statistics (admin)

## Next Steps After Setup

### Option 1: Build Workspace Management UI
Create admin interface for:
- Viewing all client workspaces
- Creating new workspaces (client onboarding)
- Managing workspace settings
- Viewing workspace statistics

### Option 2: Enforce Authentication
Make login required across the platform

### Option 3: Continue Digitization Features
Return to document processing workflow

## Troubleshooting

**Error: "column workspaces.slug does not exist"**
- Solution: Run Step 1 (create table in Supabase)

**Error: "relation 'workspaces' does not exist"**
- Solution: Run the SQL migration in Supabase SQL Editor

**Error: "duplicate key value violates unique constraint"**
- Solution: Demo workspace already exists, you're good to go!

## SQL Migration Location

Full SQL file: `/app/backend/database/workspaces_migration.sql`

This creates:
- `workspaces` table - Main workspace data
- `workspace_users` table - Many-to-many user-workspace relationships
- Indexes for performance
- Triggers for automatic timestamp updates

## Support

If you encounter issues:
1. Check Supabase dashboard for table creation
2. Verify environment variables are set
3. Check backend logs: `tail -f /var/log/supervisor/backend.err.log`
