-- ============================================================
-- Mining FD: registry v3 — quarantine-queue review pass
-- ============================================================
-- v2 (c7516f8 era) covered the obvious wins; this pass reviews the
-- remaining ~100 quarantined surface forms and promotes the legitimate
-- entity references. Everything else stays in the queue intentionally —
-- the spec §4.2 rule that "common-noun noise stays in quarantine, never
-- auto-merged" still holds.
--
-- Three classes addressed:
--
-- A. EXXARO-001 alias extensions — the "Group (X impact)" qualifier
--    variants the model emits when summarising the FY2024 EBITDA waterfall.
--    Each is a variance-decomposition label ("Group (Forex impact)",
--    "Group (Price impact)" etc.) — same EXXARO-001 entity, parenthesised
--    descriptor. Pre-seeding these stops Q-DELTA / Q1 / grounded queries
--    from quarantining identical-but-suffixed forms each new ingest.
--
-- B. CENNERGI-001 Unicode-apostrophe variant — pg_trgm treats ASCII
--    apostrophe and the typographic right single quote (U+2019) as
--    distinct characters; the model emits the latter ("Cennergi's
--    operating wind assets"), the v2 registry only has the former
--    ("Cennergi''s …"). Adding both forms.
--
-- C. New canonical_id ESKOM-001 — Eskom (the South African state-owned
--    electricity utility) appears in the chapter as both a customer and
--    a counterparty / regulatory backdrop. Promoting from queue.
--
-- NOT promoted (intentional):
--   * Trade unions (AMCU, FAWU, NUM, NUMSA, Solidarity) — real orgs but
--     not load-bearing for the FD module's spec §1 scope (capital-
--     transition story). Module 02 (Occupational-Health, when built)
--     will want these; staying in the queue documents that.
--   * Commodity nouns (Coal, coal, Copper, Manganese, Ferrous, Energy)
--     — surface forms of commodity values, not entities. Leaving here
--     instead of inventing "commodity" registry rows that the schema
--     doesn't model.
--   * Verb-phrase narratives ("capital allocation ALLOCATED_TO deliver
--     returns for our shareholders") — the destination is a verb phrase,
--     not an entity. Genuinely shouldn't resolve.
--   * Common-noun noise ("operations", "intangible assets", "equity-
--     accounted investments", "five mines (including one JV)", "two
--     coal projects", "Education", "energy projects") — describing
--     types not nameable entities.
--
-- Idempotent.
-- ============================================================

DO $$
DECLARE
    v_workspace_id UUID;
BEGIN
    SELECT id INTO v_workspace_id FROM workspaces WHERE slug = 'exxaro-fd' LIMIT 1;
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Workspace "exxaro-fd" not found.';
    END IF;

    -- A. EXXARO-001 += Group (X impact) qualifier variants.
    UPDATE fd_entity_registry r
       SET surface_forms = (
           SELECT ARRAY(SELECT DISTINCT unnest(r.surface_forms || ARRAY[
               'Group (Export coal)',
               'Group (Buy-ins impact)',
               'Group (Forex impact)',
               'Group (Price impact)',
               'Group (Volume impact)',
               'Group (General impact)',
               'Group (Operational cost impact)',
               'Group (Other cost impact)',
               'Group (Inflation impact)',
               'Group (Insurance cost impact)',
               'Group (Domestic coal price impact)',
               'Group (Rehabilitation cost impact)',
               'Group (Selling and distribution cost impact)'
           ]))
       )
     WHERE r.workspace_id = v_workspace_id AND r.canonical_id = 'EXXARO-001';

    -- B. CENNERGI-001 += Unicode-apostrophe variant.
    --    U+2019 is the typographic right single quote the ADE markdown
    --    uses; v2 only has the ASCII variant.
    UPDATE fd_entity_registry r
       SET surface_forms = (
           SELECT ARRAY(SELECT DISTINCT unnest(r.surface_forms || ARRAY[
               'Cennergi’s operating wind assets'
           ]))
       )
     WHERE r.workspace_id = v_workspace_id AND r.canonical_id = 'CENNERGI-001';

    -- C. New canonical_id: ESKOM-001 (counterparty / utility).
    INSERT INTO fd_entity_registry
        (workspace_id, canonical_id, canonical_name, entity_type, surface_forms, owned_via, notes)
    VALUES
        (v_workspace_id, 'ESKOM-001', 'Eskom', 'Org',
         ARRAY['Eskom', 'Eskom Holdings', 'Eskom SOC', 'Eskom Holdings SOC Ltd'],
         NULL,
         'South African state-owned electricity utility. Appears as a coal-purchase counterparty and as the regulatory power-supply backdrop for Exxaro''s renewable-substitution narrative. Not a subsidiary.')
    ON CONFLICT (workspace_id, canonical_id) DO UPDATE
        SET surface_forms = EXCLUDED.surface_forms,
            notes         = EXCLUDED.notes,
            updated_at    = NOW();

    -- Mirror into fd_orgs so the §3.3 stamping helpers can read its shape
    -- when Eskom appears as a strategic-narrative endpoint.
    INSERT INTO fd_orgs (workspace_id, canonical_id, name, org_type)
    VALUES
        (v_workspace_id, 'ESKOM-001', 'Eskom', 'Counterparty')
    ON CONFLICT (workspace_id, canonical_id) DO NOTHING;

    RAISE NOTICE 'Registry v3 applied: EXXARO-001 + 13 variants; CENNERGI-001 Unicode variant; ESKOM-001 new (Org).';
END $$;
