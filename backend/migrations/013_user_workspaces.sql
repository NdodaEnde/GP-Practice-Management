-- ============================================================================
-- Migration 013 — Multi-practice support: user_workspaces join (Tranche A)
-- ============================================================================
-- Implements TRACEABILITY §11 Tranche A.
--
-- Today every user belongs to exactly one workspace via users.workspace_id.
-- That blocks a doctor running multiple clinics from having a single login
-- that flips between practices. We add a many-to-many join table; the
-- existing users.workspace_id column is preserved as the "primary"
-- workspace (backwards compat — every existing endpoint keeps working).
--
-- Roles:
--   - owner    : tenant-level decisions (can delete the workspace)
--   - admin    : workspace admin (manage users, capabilities)
--   - clinical : doctor / clinical staff (digitisation, validation)
--   - reception: front-desk
--   - billing  : finance / claims only
--   - readonly : view-only
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS user_workspaces (
    user_id        TEXT        NOT NULL,
    workspace_id   TEXT        NOT NULL,
    role           TEXT        NOT NULL DEFAULT 'clinical',
    is_primary     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by     TEXT,                 -- who added them (audit)
    PRIMARY KEY (user_id, workspace_id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'user_workspaces_role_chk'
    ) THEN
        ALTER TABLE user_workspaces
            ADD CONSTRAINT user_workspaces_role_chk
            CHECK (role IN ('owner', 'admin', 'clinical', 'reception',
                            'billing', 'readonly'));
    END IF;
END$$;

-- Enforce: at most ONE primary workspace per user (the one their default
-- session lands on). Other workspaces are explicit-switch.
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_workspaces_one_primary
    ON user_workspaces (user_id)
    WHERE is_primary = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_workspaces_workspace
    ON user_workspaces (workspace_id);

COMMENT ON TABLE user_workspaces IS
    'Multi-practice support: a user may belong to N workspaces (TRACEABILITY '
    '§11). Backfilled from users.workspace_id on this migration; new users '
    'get one row at provisioning time. users.workspace_id is preserved as '
    'the primary-workspace pointer for backwards compat — every existing '
    'endpoint still works because the JWT keeps an active workspace_id.';

-- ----------------------------------------------------------------------------
-- Backfill from existing users.workspace_id
-- ----------------------------------------------------------------------------
-- Each existing user gets a single user_workspaces row mirroring their
-- current workspace, marked is_primary=true. ON CONFLICT DO NOTHING so
-- re-running is safe.

INSERT INTO user_workspaces (user_id, workspace_id, role, is_primary, granted_by)
SELECT u.id, u.workspace_id,
       CASE WHEN u.role = 'admin' THEN 'admin' ELSE 'clinical' END,
       TRUE,
       'migration-013'
  FROM users u
 WHERE u.workspace_id IS NOT NULL
ON CONFLICT (user_id, workspace_id) DO NOTHING;

COMMIT;
