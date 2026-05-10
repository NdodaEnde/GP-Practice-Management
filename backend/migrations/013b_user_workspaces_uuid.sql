-- ============================================================================
-- Migration 013b — Align user_workspaces.user_id type with users.id (UUID)
-- ============================================================================
-- Migration 013 created user_workspaces.user_id as TEXT, but users.id is UUID.
-- The backfill INSERT worked (implicit UUID → TEXT cast on assignment) but
-- JOINs fail with `operator does not exist: uuid = text`. Casting on every
-- query is ugly; fixing the column type once is cleaner.
--
-- The existing values are valid UUID strings (canonical format), so
-- ALTER COLUMN ... TYPE UUID USING user_id::uuid converts in place with
-- no data loss.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

DO $$
DECLARE
    cur_type TEXT;
BEGIN
    SELECT data_type INTO cur_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'user_workspaces'
       AND column_name = 'user_id';
    IF cur_type = 'text' THEN
        ALTER TABLE user_workspaces
            ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
        RAISE NOTICE 'Converted user_workspaces.user_id text → uuid';
    ELSE
        RAISE NOTICE 'user_workspaces.user_id already %, skipping', cur_type;
    END IF;
END$$;

COMMIT;
