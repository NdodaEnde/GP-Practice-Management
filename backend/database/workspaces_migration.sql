-- Workspaces Table for Multi-Tenant Management
-- Each workspace represents a client organization using the DaaS platform

CREATE TABLE IF NOT EXISTS workspaces (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Workspace Information
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    
    -- Organization Details
    organization_name VARCHAR(255) NOT NULL,
    organization_type VARCHAR(100), -- 'gp_practice', 'occupational_health', 'hospital', 'clinic'
    
    -- Contact Information
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50),
    contact_person VARCHAR(255),
    
    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    province VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'South Africa',
    
    -- Subscription & Billing
    subscription_tier VARCHAR(50) DEFAULT 'free', -- 'free', 'basic', 'professional', 'enterprise'
    subscription_status VARCHAR(50) DEFAULT 'active', -- 'active', 'suspended', 'cancelled'
    billing_email VARCHAR(255),
    
    -- Tenant Isolation
    tenant_id VARCHAR(100) NOT NULL,
    
    -- Limits & Quotas
    max_users INTEGER DEFAULT 10,
    max_documents INTEGER DEFAULT 1000,
    storage_quota_gb INTEGER DEFAULT 10,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_trial BOOLEAN DEFAULT false,
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    settings JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces(slug);
CREATE INDEX IF NOT EXISTS idx_workspaces_tenant_id ON workspaces(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_is_active ON workspaces(is_active);
CREATE INDEX IF NOT EXISTS idx_workspaces_subscription_status ON workspaces(subscription_status);

-- Updated at trigger
CREATE TRIGGER update_workspaces_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE workspaces IS 'Client workspaces for multi-tenant DaaS platform';
COMMENT ON COLUMN workspaces.slug IS 'URL-friendly unique identifier';
COMMENT ON COLUMN workspaces.organization_type IS 'Type of healthcare organization';
COMMENT ON COLUMN workspaces.subscription_tier IS 'Billing tier: free, basic, professional, enterprise';
COMMENT ON COLUMN workspaces.tenant_id IS 'Tenant identifier for data isolation';

-- Workspace Users Junction Table (for future use)
CREATE TABLE IF NOT EXISTS workspace_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'owner', 'admin', 'member'
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_users_workspace ON workspace_users(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_users_user ON workspace_users(user_id);

COMMENT ON TABLE workspace_users IS 'Many-to-many relationship between workspaces and users';
