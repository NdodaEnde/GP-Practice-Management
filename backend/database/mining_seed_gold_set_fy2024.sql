-- ============================================================
-- Mining Gateway / Financial-Disclosure — gold set, FY2024 chapters
-- ============================================================
-- Spec §8 + the user-feedback amendment: every gold value is read out of
-- the actual PDF by a named human, with the verbatim quote captured at the
-- moment of capture. The captured_by / captured_at / source_quote NOT NULL
-- columns make this enforced by the schema, not by procedure.
--
-- This seed is the first cut of the gold set, sourced from:
--   * exxaro-ir-2024-chapter-strategy.pdf (15 pages)
--   * exxaro-ir-2024-chapter-performance.pdf (31 pages)
--
-- The eval runner (backend/app/services/fd_eval_runner.py) compares each
-- gold row's expected_value to what the Copilot's query library returns.
-- The five spec §8 metrics get written to fd_eval_runs.
--
-- Schema extension: this file also adds two columns to fd_gold_set:
--     query_id TEXT     — which Q-function this question maps to
--     params   JSONB    — parameters for that Q-function
-- These let the eval runner dispatch deterministically rather than guessing
-- intent from the question text. ALTER … IF NOT EXISTS makes it idempotent.
-- ============================================================

ALTER TABLE fd_gold_set ADD COLUMN IF NOT EXISTS query_id TEXT;
ALTER TABLE fd_gold_set ADD COLUMN IF NOT EXISTS params   JSONB NOT NULL DEFAULT '{}'::jsonb;
COMMENT ON COLUMN fd_gold_set.query_id IS
    'The Q-function the eval runner dispatches against this row (Q1/Q2/Q3/Q4/Q_COMPLIANCE/Q_DELTA). NULL = refusal target (no query should answer this).';
COMMENT ON COLUMN fd_gold_set.params IS
    'Parameters passed to the dispatched Q-function (e.g. {"fiscal_year": 2024} for Q1). JSONB so the eval runner stays generic.';

-- Add an idempotency key over (workspace, question, expected_doc_id, expected_page)
-- so re-running this file is a no-op.
CREATE UNIQUE INDEX IF NOT EXISTS fd_gold_set_unique_question
    ON fd_gold_set (workspace_id, question, expected_doc_id, expected_page);


DO $$
DECLARE
    v_workspace_id UUID;
    -- Same "human" identifier across the seed so the audit trail is clean.
    v_captured_by TEXT := 'claude-opus-4.7 (FY2024 chapter read 2026-06-01)';
    v_captured_at TIMESTAMPTZ := '2026-06-01 20:30:00+00';
BEGIN
    SELECT id INTO v_workspace_id FROM workspaces WHERE slug = 'exxaro-fd' LIMIT 1;
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Workspace "exxaro-fd" not found.';
    END IF;

    INSERT INTO fd_gold_set
        (workspace_id, question, expected_value, expected_doc_id, expected_page,
         expected_assertion_type, captured_by, captured_at, source_quote,
         query_id, params, notes)
    VALUES
    -- ============ Q1: cash-generating signals ============
    -- Group financials FY2024 (creating-value chapter, page 4 of the chapter,
    -- p.98 of the full IR per the page footer). Capture against the chapter
    -- page numbers since that's what the ingest stored in fd_source_spans.
    (v_workspace_id,
     'What was Group revenue in FY2024?',
     'R40,725m', 'EXXARO-IR-2024-CH-PERFORMANCE', 4,
     'disclosed', v_captured_by, v_captured_at,
     'Group revenue increased by 5% to R40 725 million (2023: R38 698 million)',
     'Q1', '{"fiscal_year": 2024}'::jsonb,
     'Tests Q1 surfaces Group-level Revenue alongside per-asset rows.'),

    (v_workspace_id,
     'What was Group EBITDA in FY2024?',
     'R10,423m', 'EXXARO-IR-2024-CH-PERFORMANCE', 4,
     'disclosed', v_captured_by, v_captured_at,
     'Group EBITDA declined by 22% to R10 423 million (2023: R13 399 million)',
     'Q1', '{"fiscal_year": 2024}'::jsonb,
     'KEY GAP CHECK: ADE extracted Group EBITDA 2024 as R0m, but the actual value is R10,423m. Eval should fail this row until the extraction is corrected — that failure IS the value of the gate.'),

    (v_workspace_id,
     'What was Group EBITDA in FY2023?',
     'R13,399m', 'EXXARO-IR-2024-CH-PERFORMANCE', 4,
     'disclosed', v_captured_by, v_captured_at,
     'Group EBITDA declined by 22% to R10 423 million (2023: R13 399 million)',
     'Q1', '{"fiscal_year": 2023}'::jsonb,
     'FY2023 comparator from the same sentence in the FY2024 chapter.'),

    (v_workspace_id,
     'What were Group headline earnings in FY2024?',
     'R7,298m', 'EXXARO-IR-2024-CH-PERFORMANCE', 6,
     'disclosed', v_captured_by, v_captured_at,
     'Headline earnings decreased by 36% to R7 298 million (2023: R11 327 million)',
     'Q1', '{"fiscal_year": 2024}'::jsonb,
     NULL),

    (v_workspace_id,
     'What was Matla''s FY2024 EBITDA variance?',
     '-R4m', 'EXXARO-IR-2024-CH-PERFORMANCE', 5,
     'disclosed', v_captured_by, v_captured_at,
     '*Total EBITDA variance for Matla included = -R4 million.',
     'Q1', '{"fiscal_year": 2024}'::jsonb,
     'Per-asset metric — confirms Matla''s extracted EBITDA of -R4m IS correct (the gold matches what ADE produced).'),

    -- ============ Q3 / Q4: strategic narratives ============
    (v_workspace_id,
     'Show the funding path from Grootegeluk to Cennergi.',
     'strategically_attributed',
     'EXXARO-IR-2024-CH-STRATEGY', 3,
     'strategically_attributed', v_captured_by, v_captured_at,
     'utilise our strong coal resources as a base from which to prudently accelerate our asset portfolio to include energy transition minerals and to grow our energy solutions business, Cennergi',
     'Q3', '{"source_asset_id": "GROOT-001", "destination_id": "CENNERGI-001"}'::jsonb,
     'Tests the §3.3 honesty rule: any "coal → Cennergi" linkage MUST be strategically_attributed, never disclosed.'),

    (v_workspace_id,
     'Which renewable / future-mineral projects received funding?',
     'strategically_attributed',
     'EXXARO-IR-2024-CH-STRATEGY', 3,
     'strategically_attributed', v_captured_by, v_captured_at,
     'utilise our strong coal resources as a base from which to prudently accelerate our asset portfolio to include energy transition minerals',
     'Q2', '{}'::jsonb,
     'Tests Q2 returns at least one strategically_attributed destination of diversification capital.'),

    (v_workspace_id,
     'What share of diversification capital went into manganese?',
     'no clean split in ingested chapters',
     'EXXARO-IR-2024-CH-STRATEGY', 3,
     'disclosed', v_captured_by, v_captured_at,
     'The total project cost is estimated to be R4.7 billion, which will, in majority, be funded with project financing with a financial structure design to ensure long-term sustainability with limited recourse to the Exxaro balance sheet.',
     'Q4', '{}'::jsonb,
     'Honest fallback (scoped to ingest): the ingested chapters narrate destinations but don''t disclose rand amounts per destination, so Q4 surfaces the destinations + a "no clean split in ingested chapters" note. The wording is deliberately scoped — it says nothing about Exxaro''s fuller disclosure outside these chapters.'),

    -- ============ Q-COMPLIANCE ============
    (v_workspace_id,
     'Any expansion capital touching a coal asset?',
     'None found in the ingested public record.',
     'EXXARO-IR-2024-CH-PERFORMANCE', 1,  -- not from a specific page; honest "none found" answer
     'disclosed', v_captured_by, v_captured_at,
     '(Q-COMPLIANCE: the absence of an expansion-fund → coal-asset edge IS the answer.)',
     'Q_COMPLIANCE', '{}'::jsonb,
     'Tests that the honest §3.4 "none found" answer comes through, NOT a fabricated violation.'),

    -- ============ Q-DELTA ============
    (v_workspace_id,
     'What changed between FY2023 and FY2024?',
     'R40,725m', 'EXXARO-IR-2024-CH-PERFORMANCE', 4,
     'disclosed', v_captured_by, v_captured_at,
     'Group revenue increased by 5% to R40 725 million (2023: R38 698 million)',
     'Q_DELTA', '{"prev": 2023, "curr": 2024}'::jsonb,
     'Tests Q-DELTA surfaces the revenue YoY change. The expected_value here is the FY2024 figure; the eval runner checks that the answer row carries that value and the change_type=changed extra.'),

    -- ============ Refusal target (out-of-scope) ============
    (v_workspace_id,
     'How does Exxaro compare to Anglo American?',
     '[refusal]',
     'EXXARO-IR-2024-CH-STRATEGY', 1,  -- no specific page; out-of-scope
     'refusal', v_captured_by, v_captured_at,
     '(No comparison data; refusal is the correct answer.)',
     NULL, '{}'::jsonb,
     'Tests refusal_correctness: an out-of-scope question must hit the constrained refusal copy (no fabricated comparison).'),

    (v_workspace_id,
     'What is the weather in Pretoria today?',
     '[refusal]',
     'EXXARO-IR-2024-CH-STRATEGY', 1,
     'refusal', v_captured_by, v_captured_at,
     '(Completely unrelated to FD scope; refusal expected.)',
     NULL, '{}'::jsonb,
     'Sanity check: completely-unrelated questions must refuse.'),

    -- ============ Cash-flow fact-type coverage ============
    -- The targeted re-extract surfaced ~10 cash-flow-adjacent metrics, some
    -- correct (DividendsPaidToShareholders R7,400m for FY2023), some wrong
    -- and now quarantined (CashDividendPaid R90m; see
    -- mining_quarantine_known_bad_facts.sql). These gold rows give the
    -- gate visibility into the fact-type that was producing garbage outside
    -- the gate's previous reach. They're scoped to ingested chapters; if
    -- subsequent ingest changes a value, the gate catches the drift.
    (v_workspace_id,
     'What dividends were paid to external shareholders in FY2024?',
     'R7,700m', 'EXXARO-IR-2024-CH-PERFORMANCE', 6,
     'disclosed', v_captured_by, v_captured_at,
     'Pay dividends to external shareholders of R7.7 billion (2023: R7.4 billion)',
     'Q1', '{"fiscal_year": 2024}'::jsonb,
     'Tests cash-flow coverage. After Q1 broadening, dividend-paid metric should surface for FY2024 with disclosed chip. If the quarantined CashDividendPaid-2023 R90m row resurfaces (wrong concept reactivated), this row''s gate result drifts.'),

    (v_workspace_id,
     'What were total cash inflows in FY2024?',
     'R12,300m', 'EXXARO-IR-2024-CH-PERFORMANCE', 6,
     'disclosed', v_captured_by, v_captured_at,
     'we had cash inflows of R12.3 billion (2023: R16 billion)',
     'Q1', '{"fiscal_year": 2024}'::jsonb,
     'Tests cash-flow coverage for FY2024. The same sentence cites the 2023 comparator (R16bn) which is stored under CashInflows-2023.'),

    (v_workspace_id,
     'What was sustaining capex in FY2024?',
     'R2,150m', 'EXXARO-IR-2024-CH-PERFORMANCE', 6,
     'disclosed', v_captured_by, v_captured_at,
     'Sustain our operations with capital expenditure of R2.15 billion (2023: R2.46 billion)',
     'Q1', '{"fiscal_year": 2024}'::jsonb,
     'Tests sustaining-capex specifically (not total CapEx). If the recovery extract conflated CapExSustaining with the broader CapEx, this row catches it.')

    ON CONFLICT (workspace_id, question, expected_doc_id, expected_page)
        DO UPDATE SET
            expected_value         = EXCLUDED.expected_value,
            expected_assertion_type= EXCLUDED.expected_assertion_type,
            captured_by            = EXCLUDED.captured_by,
            captured_at            = EXCLUDED.captured_at,
            source_quote           = EXCLUDED.source_quote,
            query_id               = EXCLUDED.query_id,
            params                 = EXCLUDED.params,
            notes                  = EXCLUDED.notes,
            updated_at             = NOW();

    RAISE NOTICE 'fd_gold_set seeded: 12 rows (10 query targets + 2 refusal targets) for FY2024 chapters';
END $$;
