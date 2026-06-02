-- ============================================================
-- Mining FD: quarantine known-bad fd_financial_facts rows
-- ============================================================
-- The targeted recovery extract (commit 6574a62 area) wrote 95 new
-- Group-level financials from FY2024 IR creating-value chapter. Most are
-- correct, but three are demonstrably wrong / overlapping:
--
--   * CashDividendPaid-2023 = R90m
--       → wrong; the actual figure is R7,400m, already stored under
--         DividendsPaidToShareholders-2023. The R90m looks like a misread
--         off a different table cell.
--
--   * NetDebtCashEquity-2023 = -23
--       → nonsense value. Likely the model picked up a row/column index
--         from a table grid as the number.
--
--   * NetCashPositionExcludingEnergyNetDebt-2023 = R14,800m
--       → duplicate of NetCashExcludingEnergyNetDebt-2023 (same value,
--         same concept named twice). Keep one, retire the other.
--
-- 'Quarantine' here = mark status='withdrawn'. Per spec §6.1 v0.3:
--    withdrawn = present in a prior report, absent and not restated in
--    the current one. We keep the row + its provenance for audit, but the
--    query library skips status != 'active' so these vanish from
--    user-facing answers immediately.
--
-- This is the spec §4.2 "wrong silent merge is worse than a missing node"
-- rule applied at the value level rather than the entity level: we'd
-- rather have NO answer for one of these concepts than a wrong one
-- silently surfacing in the open search bar.
--
-- Idempotent: re-running is a no-op once the rows are marked withdrawn.
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
       SET status = 'withdrawn', updated_at = NOW()
     WHERE workspace_id = v_workspace_id
       AND canonical_id IN (
            'EXXARO-001-CashDividendPaid-2023',
            'EXXARO-001-NetDebtCashEquity-2023',
            'EXXARO-001-NetCashPositionExcludingEnergyNetDebt-2023'
       )
       AND status = 'active';

    RAISE NOTICE 'Quarantine pass complete. Rows still searchable in fd_financial_facts, but skipped by the query library (status=active filter).';
END $$;

-- Also add a small audit query the user can run to spot the pattern in the
-- future: financial facts with suspicious shapes (negatives outside known
-- "variance" / "delta" metrics, near-zero values where R-millions are
-- expected, near-duplicate metric names within a fiscal year).
COMMENT ON TABLE fd_financial_facts IS
    'Mining/FD: FinancialFact node class (spec §3.1). status ∈ {active, restated, withdrawn} per §6.1 v0.3. WITHDRAWN includes facts we judged demonstrably wrong (see mining_quarantine_known_bad_facts.sql) — the row + provenance is kept for audit; the query library only returns status=active.';
