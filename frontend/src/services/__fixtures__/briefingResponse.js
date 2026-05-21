// Fixtures for the morning-briefing renderer contract tests.
//
// PINNED FROM CODE, not hand-shaped to be convenient (the fake-property
// anti-pattern is a fixture shaped to pass; this one is shaped to MATCH
// production). Sources, read directly:
//   * backend/app/api/query.py:347-357 — GET /api/query/briefing returns
//       { workspace_id, count, items: [ raw briefing_items row ] }
//       (raw rows via .select("*"); NO ResolvedQueryResult envelope).
//   * backend/migrations/027_briefing_items.sql:65-82 — the row columns:
//       id, workspace_id, kind, as_of_date, template_id,
//       template_version, row_payload (jsonb), source_status, openable,
//       unresolvable_reason, citation, materialised_at.
//   * backend/ontology/query/provenance.py:204-214 — row_payload =
//       ResolvedRow.to_dict() = { ...data, provenance, source,
//       additional_sources }.
//   * provenance.py:176-185 — row_payload.source = ResolvedSource
//       .to_dict() = { status, openable, document_id, signed_url,
//       citation, unresolvable_reason, quality }.  signed_url is HERE,
//       nested. There is NO top-level item.signed_url and NO top-level
//       item.source.
//   * provenance.py:119-123 — quality = { section_confidence_recoverable,
//       superseded } | null.
//
// If a future maintainer changes the backend shape, these fixtures (and
// the contract test that reads them) must change WITH the code — that
// coupling is the point.

function makeItem({
  id,
  data,
  source, // the NESTED ResolvedSource.to_dict() shape
}) {
  return {
    // briefing_items top-level columns (027). The denormalised
    // source_status / openable / unresolvable_reason / citation are the
    // CHEAP badge copy of the nested source — they are NOT where the
    // signed_url lives.
    id,
    workspace_id: 'demo-briefing-workspace-001',
    kind: 'morning_briefing',
    as_of_date: '2026-05-17',
    template_id: 'patients_not_seen_since',
    template_version: 1,
    row_payload: {
      ...data,
      provenance: { source_document_id: source.document_id },
      source, // ResolvedSource.to_dict() — the authoritative per-row source
      additional_sources: null, // null for 100% of current corpus (CI invariant)
    },
    source_status: source.status,
    openable: source.openable,
    unresolvable_reason: source.unresolvable_reason ?? null,
    citation: source.citation,
    materialised_at: '2026-05-17T06:00:00.000Z',
  };
}

export const OPENABLE_ITEM = makeItem({
  id: 'bi-openable-0000-0000-000000000001',
  data: {
    patient_id: 'pat-001',
    first_name: 'Thandeka',
    last_name: 'Mokoena',
    dob: '1979-03-11',
    last_consultation: '2025-09-02',
  },
  source: {
    status: 'openable',
    openable: true,
    document_id: 'briefingdemo-doc-0000-0000-000000000001',
    // The ONLY place a signed URL legitimately appears (nested):
    signed_url:
      'https://demo.supabase.co/storage/v1/object/sign/medical-records/x?token=abc',
    citation: 'Briefing demo patient file.pdf, 7 May 2026',
    unresolvable_reason: null,
    quality: { section_confidence_recoverable: false, superseded: false },
  },
});

export const UNRESOLVABLE_ITEM = makeItem({
  id: 'bi-unresolvable-0000-0000-000000000002',
  data: {
    patient_id: 'pat-002',
    first_name: 'Sipho',
    last_name: 'Dlamini',
    dob: '1962-07-25',
    last_consultation: '2024-11-18',
  },
  source: {
    status: 'unresolvable',
    openable: false,
    document_id: 'orphan-doc-ffffffff-ffff-ffff-ffff-ffffffe15a71',
    signed_url: null,
    // Phase-3 LOCKED truncated-id wording (decision #3).
    citation: 'source document no longer available (id …e15a71)',
    unresolvable_reason: 'source_document_not_found_in_workspace',
    quality: null,
  },
});

export const NO_SOURCE_ITEM = makeItem({
  id: 'bi-nosource-0000-0000-000000000003',
  data: {
    patient_id: 'pat-003',
    first_name: 'Naledi',
    last_name: 'Khumalo',
    dob: '1990-01-30',
    last_consultation: '2025-02-14',
  },
  source: {
    status: 'no_source',
    openable: false,
    document_id: null,
    signed_url: null,
    citation: 'entered directly in the EHR (no source document)',
    unresolvable_reason: null,
    quality: null,
  },
});

// A realistic GET /api/query/briefing response (the envelope query.py
// actually returns: workspace_id, count, items — NO unresolvable_count).
export const BRIEFING_RESPONSE = {
  workspace_id: 'demo-briefing-workspace-001',
  count: 3,
  items: [OPENABLE_ITEM, UNRESOLVABLE_ITEM, NO_SOURCE_ITEM],
};

// THE §D.1-CLASS TRAP FIXTURE. This item claims source.status
// 'openable' but the signed_url is placed ONLY at the WRONG flat
// locations a naive/refactored renderer might read (item.signed_url and
// item.source.signed_url), while the real nested path
// row_payload.source.signed_url is null. A renderer bound to the real
// shape MUST refuse to render this openable (no dead button); a renderer
// that flattened the access would "work" off the wrong path here and the
// contract test would catch the flattening by going red.
export const FLATTENED_TRAP_ITEM = {
  id: 'bi-trap-0000-0000-000000000099',
  workspace_id: 'demo-briefing-workspace-001',
  kind: 'morning_briefing',
  as_of_date: '2026-05-17',
  template_id: 'patients_not_seen_since',
  template_version: 1,
  // Wrong flat locations a flattening refactor might reach for:
  signed_url:
    'https://demo.supabase.co/storage/v1/object/sign/WRONG-FLAT-TOP/x',
  source: {
    status: 'openable',
    openable: true,
    signed_url:
      'https://demo.supabase.co/storage/v1/object/sign/WRONG-FLAT-SOURCE/x',
  },
  row_payload: {
    patient_id: 'pat-099',
    first_name: 'Trap',
    last_name: 'Case',
    provenance: { source_document_id: 'd-099' },
    // The REAL nested source: status says openable but signed_url is
    // null — the resolver's silent-dead-link guard, mirrored.
    source: {
      status: 'openable',
      openable: true,
      document_id: 'd-099',
      signed_url: null,
      citation: 'trap — nested signed_url intentionally absent',
      unresolvable_reason: null,
      quality: null,
    },
    additional_sources: null,
  },
  source_status: 'openable',
  openable: true,
  unresolvable_reason: null,
  citation: 'trap — nested signed_url intentionally absent',
  materialised_at: '2026-05-17T06:00:00.000Z',
};
