-- =============================================
-- NAPPI CODES TABLE
-- National Pharmaceutical Product Interface Codes
-- South African medication coding system
-- =============================================

DROP TABLE IF EXISTS nappi_codes CASCADE;

CREATE TABLE nappi_codes (
    nappi_code TEXT PRIMARY KEY,
    
    -- Medication identification
    brand_name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    
    -- Product details
    strength TEXT,
    dosage_form TEXT,
    ingredients TEXT,
    
    -- Regulatory
    schedule TEXT CHECK (schedule IN ('S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'Unscheduled')),
    
    -- Classification
    atc_code TEXT,
    therapeutic_class TEXT,
    
    -- Additional metadata
    pack_size TEXT,
    manufacturer TEXT,
    route_of_administration TEXT,
    
    -- Status
    status TEXT CHECK (status IN ('active', 'discontinued', 'inactive')) DEFAULT 'active',
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Full-text search indexes
CREATE INDEX idx_nappi_brand_search ON nappi_codes USING gin(to_tsvector('english', brand_name));
CREATE INDEX idx_nappi_generic_search ON nappi_codes USING gin(to_tsvector('english', generic_name));
CREATE INDEX idx_nappi_ingredients_search ON nappi_codes USING gin(to_tsvector('english', ingredients));

-- Lookup indexes
CREATE INDEX idx_nappi_brand ON nappi_codes(brand_name);
CREATE INDEX idx_nappi_generic ON nappi_codes(generic_name);
CREATE INDEX idx_nappi_schedule ON nappi_codes(schedule) WHERE status = 'active';
CREATE INDEX idx_nappi_status ON nappi_codes(status);

-- Composite index for common queries
CREATE INDEX idx_nappi_active_search ON nappi_codes(status, brand_name, generic_name) WHERE status = 'active';

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE nappi_codes IS 'National Pharmaceutical Product Interface codes - South African medication database';
COMMENT ON COLUMN nappi_codes.nappi_code IS 'Unique NAPPI code identifier';
COMMENT ON COLUMN nappi_codes.brand_name IS 'Brand/trade name of medication';
COMMENT ON COLUMN nappi_codes.generic_name IS 'Generic/active ingredient name';
COMMENT ON COLUMN nappi_codes.schedule IS 'South African medicine schedule (S0-S8)';
COMMENT ON COLUMN nappi_codes.ingredients IS 'Active pharmaceutical ingredients';

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

SELECT 'NAPPI codes table created successfully!' as message;
