-- ============================================================
-- Mining Gateway / Financial-Disclosure — seed the canonical-ID registry
-- ============================================================
-- Pre-seeds the entity registry per spec §4.2: "Pre-seed the registry. Before
-- ingesting anything, hand-seed 20–30 known aliases from Exxaro's investor
-- glossary, segment notes, and FAQ." This file is the first cut, drawn from
-- the spec's worked examples.
--
-- Discipline (plan, "what's NOT to do" carried from earlier feedback):
--   * canonical_id and canonical_name are platform-controlled identifiers —
--     safe to seed from the spec.
--   * surface_forms below are the spec's *illustrative* examples. They are
--     not yet verified against the actual Exxaro reports for FY2022–2025.
--     Before step 2 ingest begins, each surface_forms array MUST be cross-
--     checked against the real PDFs by a human, and any aliases that appear
--     in the reports but not below MUST be appended. The fd_facts_needs_review
--     quarantine bucket is the safety net for misses, but the discipline is:
--     don't rely on the safety net for what should have been in the registry.
--
-- Idempotency: each row uses ON CONFLICT (workspace_id, canonical_id) DO UPDATE
-- so re-running this file is a no-op against unchanged rows and updates only
-- the surface_forms / notes when they change.
--
-- The disambiguation traps from spec §4.2 (Tshipi Borwa-the-mine vs
-- Ntsimbintle-the-holding-company vs Kalahari Manganese Field-the-region) are
-- encoded both as separate canonical IDs and in the notes column.
-- ============================================================

-- Resolve the workspace once. Bail if it doesn't exist — running this file
-- before mining_seed_workspace.sql is a sequencing error worth surfacing.
DO $$
DECLARE
    v_workspace_id UUID;
BEGIN
    SELECT id INTO v_workspace_id
      FROM workspaces
     WHERE slug = 'exxaro-fd'
     LIMIT 1;

    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Workspace "exxaro-fd" not found. Run mining_seed_workspace.sql first.';
    END IF;

    -- ------------------------------------------------------------
    -- Org
    -- ------------------------------------------------------------
    INSERT INTO fd_entity_registry (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
    (v_workspace_id, 'EXXARO-001', 'Exxaro Resources Limited', 'Org',
        ARRAY['Exxaro', 'Exxaro Resources', 'Exxaro Resources Ltd', 'the Group', 'the Company'],
        NULL,
        'Issuer / parent. "the Group" and "the Company" are reporter-internal phrases — accept only inside fact-extraction context where the surrounding doc_id is an Exxaro report.'),
    (v_workspace_id, 'NTSIMBINTLE-001', 'Ntsimbintle Holdings (Pty) Ltd', 'Org',
        ARRAY['Ntsimbintle', 'Ntsimbintle Holdings'],
        NULL,
        'Holding company through which Exxaro owns its manganese stakes. NOT a mine. Distinct from any commodity asset.'),
    (v_workspace_id, 'CENNERGI-001', 'Cennergi (Pty) Ltd', 'Org',
        ARRAY['Cennergi', 'Cennergi Pty Ltd', 'Cennergi Holdings'],
        NULL,
        'Renewable-energy subsidiary. Operates wind / solar projects like Tsitsikamma. The reports may attribute funding flows to "Cennergi" as the subsidiary, not to specific assets — keep both representations.')
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET canonical_name = EXCLUDED.canonical_name,
            surface_forms  = EXCLUDED.surface_forms,
            owned_via      = EXCLUDED.owned_via,
            notes          = EXCLUDED.notes;

    -- ------------------------------------------------------------
    -- Assets — Coal
    -- ------------------------------------------------------------
    INSERT INTO fd_entity_registry (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
    (v_workspace_id, 'GROOT-001', 'Grootegeluk Coal Mine', 'Asset',
        ARRAY['Grootegeluk', 'Grootegeluk Mine', 'Grootegeluk Complex', 'Grootegeluk Coal Mine'],
        'EXXARO-001',
        'Largest coal-producing asset; central to the "coal cash funds transition" narrative (spec §7.5 Demo 1).'),
    (v_workspace_id, 'MATLA-001', 'Matla Coal Complex', 'Asset',
        ARRAY['Matla', 'Matla Mine', 'Matla Colliery', 'Matla Complex', 'Matla New Mine 1'],
        'EXXARO-001',
        'New Mine 1 is an expansion within the complex, NOT a separate asset. Do not split.'),
    (v_workspace_id, 'BELFAST-001', 'Belfast Mine', 'Asset',
        ARRAY['Belfast', 'Belfast Coal Mine'],
        'EXXARO-001',
        NULL),
    (v_workspace_id, 'LEEUWPAN-001', 'Leeuwpan Mine', 'Asset',
        ARRAY['Leeuwpan', 'Leeuwpan Coal Mine'],
        'EXXARO-001',
        NULL)
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET canonical_name = EXCLUDED.canonical_name,
            surface_forms  = EXCLUDED.surface_forms,
            owned_via      = EXCLUDED.owned_via,
            notes          = EXCLUDED.notes;

    -- ------------------------------------------------------------
    -- Assets — Manganese
    -- ------------------------------------------------------------
    INSERT INTO fd_entity_registry (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
    (v_workspace_id, 'TSHIPI-001', 'Tshipi Borwa Mine', 'Asset',
        ARRAY['Tshipi Borwa', 'Tshipi', 'Tshipi Borwa Mine'],
        'NTSIMBINTLE-001',
        'Mine asset, owned via NTSIMBINTLE-001 (holding company). Distinct from Ntsimbintle (the company) and Kalahari Manganese Field (the region). Effective ownership <100% — needs sourced effective_pct on the OWNS edge before any derived rollup.')
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET canonical_name = EXCLUDED.canonical_name,
            surface_forms  = EXCLUDED.surface_forms,
            owned_via      = EXCLUDED.owned_via,
            notes          = EXCLUDED.notes;

    -- ------------------------------------------------------------
    -- Assets — Renewable
    -- ------------------------------------------------------------
    INSERT INTO fd_entity_registry (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
    (v_workspace_id, 'TSITSIKAMMA-001', 'Tsitsikamma Community Wind Farm', 'Asset',
        ARRAY['Tsitsikamma', 'Tsitsikamma Community Wind Farm', 'Tsitsikamma Wind Farm'],
        'CENNERGI-001',
        'Wind-farm project; one of Cennergi''s assets. Owned via CENNERGI-001 (the subsidiary), not directly by EXXARO-001.')
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET canonical_name = EXCLUDED.canonical_name,
            surface_forms  = EXCLUDED.surface_forms,
            owned_via      = EXCLUDED.owned_via,
            notes          = EXCLUDED.notes;

    -- ------------------------------------------------------------
    -- Capital Funds (spec §3.1)
    -- ------------------------------------------------------------
    INSERT INTO fd_entity_registry (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
    (v_workspace_id, 'FUND-SUSTAINING-001', 'Sustaining Capital Fund', 'CapitalFund',
        ARRAY['Sustaining Capital', 'Sustaining capex', 'Sustaining capital allocation'],
        NULL,
        'Internal capital category — actual fund name in Exxaro reporting may differ. Confirm against 2022–2025 capex breakdowns before step 2.'),
    (v_workspace_id, 'FUND-EXPANSION-001', 'Expansion Capital Fund', 'CapitalFund',
        ARRAY['Expansion Capital', 'Expansion capex', 'Expansion capital allocation'],
        NULL,
        'Q-COMPLIANCE checks this fund_type ∉ Coal assets — i.e. expansion capital must not flow to coal under the company''s stated strategy.'),
    (v_workspace_id, 'FUND-DIVERSIFICATION-001', 'Diversification Capital Fund', 'CapitalFund',
        ARRAY['Diversification Capital', 'Diversification capex', 'Green Diversification Fund'],
        NULL,
        'Funds the Future Minerals + Green Energy pillars. Linkages from Coal Assets here are ALWAYS strategically_attributed, never disclosed (spec §3.3 hard rule).')
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET canonical_name = EXCLUDED.canonical_name,
            surface_forms  = EXCLUDED.surface_forms,
            owned_via      = EXCLUDED.owned_via,
            notes          = EXCLUDED.notes;

    -- ------------------------------------------------------------
    -- Strategic Pillars (spec §3.1)
    -- ------------------------------------------------------------
    INSERT INTO fd_entity_registry (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
    (v_workspace_id, 'PILLAR-COAL-OPS-001', 'Coal Operations', 'StrategicPillar',
        ARRAY['Coal Ops', 'Coal Operations', 'Coal segment'],
        NULL,
        NULL),
    (v_workspace_id, 'PILLAR-GREEN-ENERGY-001', 'Green Energy', 'StrategicPillar',
        ARRAY['Green Energy', 'Renewable Energy', 'Renewables', 'Energy Solutions'],
        NULL,
        NULL),
    (v_workspace_id, 'PILLAR-FUTURE-MINERALS-001', 'Future Minerals', 'StrategicPillar',
        ARRAY['Future Minerals', 'Manganese segment', 'Diversification pillar'],
        NULL,
        'Houses the manganese exposure (Tshipi Borwa via Ntsimbintle).')
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET canonical_name = EXCLUDED.canonical_name,
            surface_forms  = EXCLUDED.surface_forms,
            owned_via      = EXCLUDED.owned_via,
            notes          = EXCLUDED.notes;

    -- ------------------------------------------------------------
    -- Acquisitions (spec §1 worked example: Kalahari Manganese)
    -- ------------------------------------------------------------
    INSERT INTO fd_entity_registry (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
    (v_workspace_id, 'ACQ-KALAHARI-MN-001', 'Kalahari Manganese Acquisition', 'Acquisition',
        ARRAY['Kalahari Manganese', 'Kalahari Manganese acquisition', 'Kalahari deal', 'Manganese acquisition'],
        NULL,
        'The DEAL, not the asset and not the region. Distinct from "Kalahari Manganese Field" (the geological region) and from "Tshipi Borwa" (the specific mine inside it). Spec uses R10.6bn illustratively — VERIFY the actual figure against the closing-year report before any gold-set capture.')
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET canonical_name = EXCLUDED.canonical_name,
            surface_forms  = EXCLUDED.surface_forms,
            owned_via      = EXCLUDED.owned_via,
            notes          = EXCLUDED.notes;

    -- Sanity log
    RAISE NOTICE 'fd_entity_registry seeded for workspace_id=%', v_workspace_id;
END $$;

-- ============================================================
-- Coverage summary (informational; run after seeding)
-- ============================================================
-- SELECT entity_type, COUNT(*) AS rows
--   FROM fd_entity_registry r
--   JOIN workspaces w ON w.id = r.workspace_id
--  WHERE w.slug = 'exxaro-fd'
--  GROUP BY entity_type
--  ORDER BY entity_type;
--
-- Expected baseline (this file):
--   Acquisition     1
--   Asset           6   (4 coal + 1 manganese + 1 renewable)
--   CapitalFund     3
--   Org             3
--   StrategicPillar 3
--                  --
--                  16  rows
--
-- Spec §4.2 target is 20–30 rows. The remainder (4–14 rows) is expected to come
-- from the actual 2022–2025 reports — additional coal assets (e.g. Mafube,
-- Forzando, ECC, NCC), additional capital funds if the company names them
-- differently, and any second-tier subsidiaries that appear in segment notes.
-- ============================================================
