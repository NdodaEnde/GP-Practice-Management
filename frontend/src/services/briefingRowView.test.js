// Contract tests for briefingRowView — plain Jest (bundled with
// react-scripts; deliberately NO @testing-library, NO DOM: the §D.1-class
// hazard is a LOGIC hazard and is pinned at the logic layer, with zero
// new dependencies added to a thin PR).
//
// The load-bearing test is "flattening fails loud": a renderer that
// reads a flat signed_url path instead of the nested
// row_payload.source.signed_url renders the openable case as a dead
// button — the silent-dead-link failure one layer out. These tests bind
// the resolver to the real nested shape so that refactor breaks the
// build, not the user's trust.

import {
  resolveBriefingItemView,
  cohortCounts,
  cohortUnresolvableCount,
  briefingRowData,
  BRIEFING_SOURCE_STATE,
} from './briefingRowView';
import {
  OPENABLE_ITEM,
  UNRESOLVABLE_ITEM,
  NO_SOURCE_ITEM,
  BRIEFING_RESPONSE,
  FLATTENED_TRAP_ITEM,
} from './__fixtures__/briefingResponse';

describe('resolveBriefingItemView — the three honest states', () => {
  test('openable: href is the NESTED row_payload.source.signed_url', () => {
    const v = resolveBriefingItemView(OPENABLE_ITEM);
    expect(v.state).toBe(BRIEFING_SOURCE_STATE.OPENABLE);
    expect(v.openable).toBe(true);
    expect(v.href).toBe(OPENABLE_ITEM.row_payload.source.signed_url);
    expect(v.href).toContain('medical-records');
    expect(v.citation).toBe('Briefing demo patient file.pdf, 7 May 2026');
  });

  test('unresolvable: no link, locked truncated-id citation, reason present', () => {
    const v = resolveBriefingItemView(UNRESOLVABLE_ITEM);
    expect(v.state).toBe(BRIEFING_SOURCE_STATE.UNRESOLVABLE);
    expect(v.openable).toBe(false);
    expect(v.href).toBeNull();
    expect(v.citation).toBe('source document no longer available (id …e15a71)');
    expect(v.unresolvableReason).toBe('source_document_not_found_in_workspace');
  });

  test('no_source: distinct from unresolvable, no link, EHR wording', () => {
    const v = resolveBriefingItemView(NO_SOURCE_ITEM);
    expect(v.state).toBe(BRIEFING_SOURCE_STATE.NO_SOURCE);
    expect(v.state).not.toBe(BRIEFING_SOURCE_STATE.UNRESOLVABLE);
    expect(v.openable).toBe(false);
    expect(v.href).toBeNull();
    expect(v.citation).toBe('entered directly in the EHR (no source document)');
  });
});

describe('SHAPE CONTRACT — flattening fails loud (§D.1 one layer out)', () => {
  test('the trap item: flat signed_url is IGNORED; openable is refused', () => {
    const v = resolveBriefingItemView(FLATTENED_TRAP_ITEM);
    // Bound to the nested path: the nested signed_url is null, so this
    // is NOT openable, even though source.status says "openable" and
    // both wrong flat locations carry a URL.
    expect(v.openable).toBe(false);
    expect(v.href).toBeNull();
    // Explicitly prove neither wrong flat location leaked through —
    // a dead button is impossible, the flattening is caught.
    expect(v.href).not.toBe(FLATTENED_TRAP_ITEM.signed_url);
    expect(v.href).not.toBe(FLATTENED_TRAP_ITEM.source.signed_url);
    expect(v.state).toBe(BRIEFING_SOURCE_STATE.UNRESOLVABLE);
    expect(v.unresolvableReason).toBe('openable_without_signed_url');
  });

  test('href is bound to the nested path only (positive + negative)', () => {
    // Mutating the NESTED path changes the resolved href.
    const nestedChanged = JSON.parse(JSON.stringify(OPENABLE_ITEM));
    nestedChanged.row_payload.source.signed_url = 'https://nested/CHANGED';
    expect(resolveBriefingItemView(nestedChanged).href).toBe(
      'https://nested/CHANGED',
    );

    // Adding/poisoning FLAT locations does NOT change the resolved href:
    // proves a flattening refactor cannot pass these tests.
    const flatPoisoned = JSON.parse(JSON.stringify(OPENABLE_ITEM));
    flatPoisoned.signed_url = 'https://flat-top/POISON';
    flatPoisoned.source = { signed_url: 'https://flat-source/POISON' };
    expect(resolveBriefingItemView(flatPoisoned).href).toBe(
      OPENABLE_ITEM.row_payload.source.signed_url,
    );
  });

  test('silent-dead-link guard: nested openable + null signed_url ⇒ not openable', () => {
    const guarded = JSON.parse(JSON.stringify(OPENABLE_ITEM));
    guarded.row_payload.source.signed_url = null;
    const v = resolveBriefingItemView(guarded);
    expect(v.openable).toBe(false);
    expect(v.href).toBeNull();
    expect(v.state).toBe(BRIEFING_SOURCE_STATE.UNRESOLVABLE);
  });

  test('missing/odd row_payload.source ⇒ visible unknown, never openable', () => {
    expect(resolveBriefingItemView({}).openable).toBe(false);
    expect(resolveBriefingItemView({ row_payload: {} }).openable).toBe(false);
    expect(resolveBriefingItemView(null).openable).toBe(false);
    expect(resolveBriefingItemView({}).state).toBe(
      BRIEFING_SOURCE_STATE.UNRESOLVABLE,
    );
  });
});

describe('cohort signal — DERIVED, because /briefing carries no envelope count', () => {
  test('counts over the realistic 3-row response', () => {
    expect(cohortUnresolvableCount(BRIEFING_RESPONSE.items)).toBe(1);
    expect(cohortCounts(BRIEFING_RESPONSE.items)).toEqual({
      openable: 1,
      unresolvable: 1,
      no_source: 1,
      total: 3,
    });
  });

  test('robust to non-arrays', () => {
    expect(cohortUnresolvableCount(undefined)).toBe(0);
    expect(cohortCounts(null)).toEqual({
      openable: 0,
      unresolvable: 0,
      no_source: 0,
      total: 0,
    });
  });
});

describe('briefingRowData — strips the provenance plumbing', () => {
  test('returns clinical fields only, not provenance/source/additional_sources', () => {
    const d = briefingRowData(OPENABLE_ITEM);
    expect(d).toEqual({
      patient_id: 'pat-001',
      first_name: 'Thandeka',
      last_name: 'Mokoena',
      dob: '1979-03-11',
      last_consultation: '2025-09-02',
    });
    expect(d.provenance).toBeUndefined();
    expect(d.source).toBeUndefined();
    expect(d.additional_sources).toBeUndefined();
  });
});
