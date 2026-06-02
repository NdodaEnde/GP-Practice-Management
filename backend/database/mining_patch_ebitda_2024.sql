-- ============================================================
-- Mining FD: patch EXXARO-001-EBITDA-2024 to the precise figure
-- ============================================================
-- The targeted recovery extract (backend/scripts/reextract_group_financials.py)
-- captured Group EBITDA FY2024 as R10,400m — from the executive-summary
-- bullet on p.2 of the creating-value chapter ("EBITDA* of R10.4 billion,
-- down 22%"). The same chapter's financial-review prose on p.3 gives the
-- precise figure: "Group EBITDA declined by 22% to R10 423 million
-- (2023: R13 399 million)".
--
-- The eval gate originally green-flagged the R10,400m display against the
-- R10,423m gold value because the matcher had a 0.5% relative tolerance
-- (gap = 23m / 0.22%, within band) — exactly the silent-crack failure mode
-- the external review caught. Two fixes were applied together:
--   1. (this file) UPDATE the stored value to R10,423m — the more
--      authoritative precise quote.
--   2. (fd_eval_runner.py) tighten the matcher to ±5m absolute on values
--      ≥100m, so any human-noticeable display drift fails the gate
--      instead of passing.
--
-- Idempotent: re-running this file when the value is already R10,423m
-- is a no-op on the row's content; only updated_at refreshes.
-- ============================================================

DO $$
DECLARE
    v_workspace_id UUID;
BEGIN
    SELECT id INTO v_workspace_id FROM workspaces WHERE slug = 'exxaro-fd' LIMIT 1;
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Workspace "exxaro-fd" not found.';
    END IF;

    UPDATE fd_financial_facts
       SET value_zar_m = 10423.0,
           updated_at  = NOW()
     WHERE workspace_id = v_workspace_id
       AND canonical_id = 'EXXARO-001-EBITDA-2024';

    -- Sanity confirm.
    PERFORM 1 FROM fd_financial_facts
     WHERE workspace_id = v_workspace_id
       AND canonical_id = 'EXXARO-001-EBITDA-2024'
       AND ABS(value_zar_m - 10423.0) < 0.5;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'EXXARO-001-EBITDA-2024 patch failed to write R10,423m.';
    END IF;

    RAISE NOTICE 'EXXARO-001-EBITDA-2024 = R10,423m (precise figure from CH-PERFORMANCE p.3).';
END $$;
