-- NAPPI Integration Migration for Prescription Items
-- This migration adds the missing nappi_code and generic_name columns to prescription_items table

-- Add NAPPI code and generic name columns to prescription_items
ALTER TABLE prescription_items 
ADD COLUMN IF NOT EXISTS nappi_code TEXT,
ADD COLUMN IF NOT EXISTS generic_name TEXT;

-- Create index for NAPPI code lookups
CREATE INDEX IF NOT EXISTS idx_prescription_items_nappi ON prescription_items(nappi_code) WHERE nappi_code IS NOT NULL;

-- Create index for generic name searches
CREATE INDEX IF NOT EXISTS idx_prescription_items_generic ON prescription_items(generic_name) WHERE generic_name IS NOT NULL;

-- Verify the changes
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'prescription_items' 
ORDER BY ordinal_position;