// briefingRowView — PURE source-resolution logic for the morning-briefing
// screen. No axios, no React: this is the layer the §D.1-class shape
// hazard lives in, so it is isolated and contract-tested
// (briefingRowView.test.js) independently of any rendering.
//
// SHAPE PINNED FROM CODE (not a summary — the §D.1 lesson: verify the
// premise, not the wording):
//   * GET /api/query/briefing  → backend/app/api/query.py:347-357 returns
//       { workspace_id, count, items: [ <raw briefing_items row> ] }
//     i.e. NO ResolvedQueryResult envelope, NO envelope-level
//     unresolvable_count — the cohort signal must be DERIVED from the
//     rows here (cohortCounts below).
//   * each item = a raw briefing_items row → backend/migrations/
//       027_briefing_items.sql: top-level denormalised columns
//       source_status / openable / unresolvable_reason / citation
//       (the CHEAP badge signal) + row_payload JSONB.
//   * row_payload = ResolvedRow.to_dict() → backend/ontology/query/
//       provenance.py:204-214 = { ...data, provenance, source,
//       additional_sources }.
//   * row_payload.source = ResolvedSource.to_dict() →
//       provenance.py:176-185 = { status, openable, document_id,
//       signed_url, citation, unresolvable_reason, quality }.
//
// THE LOAD-BEARING INVARIANT: the openable link target is
// row_payload.source.signed_url — NESTED. There is NO top-level
// item.signed_url and NO top-level item.source object. A renderer that
// reads a flat path renders the openable case as a DEAD BUTTON — exactly
// the silent-dead-link failure the whole Phase-3 close-condition exists
// to catch, reproduced one layer out. This module reads ONLY the nested
// path, and briefingRowView.test.js fails loud if a refactor flattens it.

export const BRIEFING_SOURCE_STATE = Object.freeze({
  OPENABLE: 'openable',
  UNRESOLVABLE: 'unresolvable',
  NO_SOURCE: 'no_source',
});

// The authoritative per-row source object is the NESTED one. We read the
// nested ResolvedSource.to_dict() and deliberately do NOT fall back to
// any top-level/flat location — binding the renderer to the real shape
// so a flattening refactor breaks the test, never the user's trust.
function nestedSource(item) {
  const rp = item && item.row_payload;
  return rp && typeof rp === 'object' ? rp.source || null : null;
}

// Resolve one raw briefing item to the view model the screen renders.
// Returns a stable shape regardless of state so the renderer never has
// to reach into row_payload itself (single choke-point for the shape).
export function resolveBriefingItemView(item) {
  const src = nestedSource(item);

  // No usable nested source object at all → treat as a visible unknown,
  // never as openable. (Defensive: an item the resolver did not shape.)
  if (!src || typeof src !== 'object') {
    return {
      state: BRIEFING_SOURCE_STATE.UNRESOLVABLE,
      openable: false,
      href: null,
      citation:
        (item && item.citation) ||
        'source unavailable (no resolved provenance on this row)',
      unresolvableReason: 'no_resolved_source_on_row',
    };
  }

  const status = src.status;
  const signedUrl = src.signed_url; // NESTED ONLY — see header invariant.
  const citation = src.citation || (item && item.citation) || '';

  if (status === BRIEFING_SOURCE_STATE.OPENABLE) {
    // Silent-dead-link guard, mirrored client-side: OPENABLE is honoured
    // ONLY if a real signed URL is present at the nested path. If it is
    // missing we degrade to a visible unresolvable, never a dead button.
    if (typeof signedUrl === 'string' && signedUrl.length > 0) {
      return {
        state: BRIEFING_SOURCE_STATE.OPENABLE,
        openable: true,
        href: signedUrl,
        citation,
        unresolvableReason: null,
      };
    }
    return {
      state: BRIEFING_SOURCE_STATE.UNRESOLVABLE,
      openable: false,
      href: null,
      citation:
        citation ||
        'source marked openable but no link available — not opened',
      unresolvableReason: 'openable_without_signed_url',
    };
  }

  if (status === BRIEFING_SOURCE_STATE.NO_SOURCE) {
    return {
      state: BRIEFING_SOURCE_STATE.NO_SOURCE,
      openable: false,
      href: null,
      citation: citation || 'entered directly in the EHR (no source document)',
      unresolvableReason: null,
    };
  }

  // UNRESOLVABLE (or any unknown status → treated as a visible unknown,
  // never openable: the safe default).
  return {
    state: BRIEFING_SOURCE_STATE.UNRESOLVABLE,
    openable: false,
    href: null,
    citation: citation || 'source document no longer available',
    unresolvableReason: src.unresolvable_reason || 'unresolvable',
  };
}

// /api/query/briefing carries NO envelope-level unresolvable_count
// (query.py:347-357 returns raw rows + a plain `count`). The cohort
// signal a clinician reads a 40-row list at is therefore DERIVED here
// from the resolved view of each row — never from a field that does not
// exist on this endpoint.
export function cohortCounts(items) {
  const out = { openable: 0, unresolvable: 0, no_source: 0, total: 0 };
  if (!Array.isArray(items)) return out;
  for (const item of items) {
    const v = resolveBriefingItemView(item);
    out.total += 1;
    if (v.state === BRIEFING_SOURCE_STATE.OPENABLE) out.openable += 1;
    else if (v.state === BRIEFING_SOURCE_STATE.NO_SOURCE) out.no_source += 1;
    else out.unresolvable += 1;
  }
  return out;
}

export function cohortUnresolvableCount(items) {
  return cohortCounts(items).unresolvable;
}

// The patient/clinical fields of the row, with the provenance plumbing
// stripped, for display. row_payload = { ...data, provenance, source,
// additional_sources } (provenance.py:204-214) — so the data IS the
// payload minus those three reserved keys.
export function briefingRowData(item) {
  const rp = (item && item.row_payload) || {};
  const { provenance, source, additional_sources, ...data } = rp;
  return data;
}
