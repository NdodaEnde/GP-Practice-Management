-- Add missing columns to existing workspaces table
-- Run this in Supabase SQL Editor

-- Add Workspace Information columns
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS slug VARCHAR(100) UNIQUE;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS organization_name VARCHAR(255);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS organization_type VARCHAR(100);

-- Add Contact Information columns
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS contact_person VARCHAR(255);

-- Add Address columns
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(255);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(255);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS province VARCHAR(100);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS country VARCHAR(100) DEFAULT 'South Africa';

-- Add Subscription & Billing columns
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(50) DEFAULT 'free';
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'active';
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS billing_email VARCHAR(255);

-- Add Limits & Quotas columns
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS max_users INTEGER DEFAULT 10;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS max_documents INTEGER DEFAULT 1000;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS storage_quota_gb INTEGER DEFAULT 10;

-- Add Status columns
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS is_trial BOOLEAN DEFAULT false;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP WITH TIME ZONE;

-- Add updated_at column
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Add Metadata columns
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'::jsonb;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces(slug);
CREATE INDEX IF NOT EXISTS idx_workspaces_tenant_id ON workspaces(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_is_active ON workspaces(is_active);
CREATE INDEX IF NOT EXISTS idx_workspaces_subscription_status ON workspaces(subscription_status);

-- Create updated_at trigger (if function exists)
DROP TRIGGER IF EXISTS update_workspaces_updated_at ON workspaces;
CREATE TRIGGER update_workspaces_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Update existing workspace with proper data
UPDATE workspaces 
SET 
    slug = 'demo-gp-workspace',
    organization_name = name,
    organization_type = 'gp_practice',
    contact_email = 'admin@demo-gp.co.za',
    contact_phone = '+27 11 123 4567',
    contact_person = 'Dr. John Smith',
    subscription_tier = 'professional',
    subscription_status = 'active',
    max_users = 50,
    max_documents = 10000,
    storage_quota_gb = 100,
    is_active = true,
    is_trial = false
WHERE id = 'demo-gp-workspace-001';

-- Create workspace_users table if it doesn't exist
CREATE TABLE IF NOT EXISTS workspace_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_users_workspace ON workspace_users(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_users_user ON workspace_users(user_id);

COMMENT ON TABLE workspace_users IS 'Many-to-many relationship between workspaces and users';

-- Success message
SELECT 'Workspace table updated successfully!' as message;
