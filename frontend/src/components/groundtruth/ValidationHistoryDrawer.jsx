/**
 * ValidationHistoryDrawer — slide-in panel showing the append-only edit log
 * for a single document. Pulled from /api/digitisation/validation/{id}/history.
 *
 * Two surfaces:
 *   1. Timeline of audit rows (newest first) — every edit / accept / approve /
 *      reject by every reviewer. The data feed for "active learning" later.
 *   2. "Show AI baseline" toggle — when on, EHRField renders a tiny
 *      "AI: <original>" caption beneath fields the reviewer has edited.
 *
 * Designed to feel like a slide-in drawer; not a modal. Page stays usable
 * underneath; reviewer can click the timeline AND keep editing.
 */

import React from 'react';
import { Clock, X, ShieldCheck, Edit3, CheckCircle, XCircle, RotateCcw, User } from 'lucide-react';

const ICONS = {
  edit:       Edit3,
  accept:     CheckCircle,
  approve:    ShieldCheck,
  reject:     XCircle,
  reprocess:  RotateCcw,
};

const COLORS = {
  edit:      '#0284c7',  // blue
  accept:    '#16a34a',  // green
  approve:   '#16a34a',  // green
  reject:    '#dc2626',  // red
  reprocess: '#9333ea',  // purple
};

const fmtTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  const ms = Date.now() - d.getTime();
  const m = Math.round(ms / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  const dd = Math.round(h / 24);
  if (dd < 14) return `${dd} day${dd === 1 ? '' : 's'} ago`;
  return d.toLocaleString('en-ZA', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const fmtVal = (v) => {
  if (v === null || v === undefined) return <span style={{ fontStyle: 'italic', color: '#9ca3af' }}>—</span>;
  if (typeof v === 'object') return <code style={{ fontSize: 11, fontFamily: 'monospace' }}>{JSON.stringify(v).slice(0, 80)}</code>;
  const s = String(v);
  return s.length > 80 ? s.slice(0, 80) + '…' : s;
};

export default function ValidationHistoryDrawer({
  open,
  onClose,
  history,           // array from /history endpoint
  hasOriginal,       // bool — whether `original` was returned by the API (migration 005 ran)
  showOriginal,      // bool — current toggle state
  onToggleOriginal,  // fn   — flip the toggle
  loading,
}) {
  if (!open) return null;

  const sortedHistory = (history || []).slice();
  // history is already DESC from the API but make sure
  sortedHistory.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));

  return (
    <>
      {/* dim backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(15, 23, 42, 0.35)',
          zIndex: 49,
        }}
      />
      {/* drawer */}
      <aside
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          height: '100vh',
          width: 420,
          maxWidth: '95vw',
          background: 'white',
          boxShadow: '-12px 0 28px rgba(15, 23, 42, 0.18)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* header */}
        <header
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid #e5e7eb',
            background: '#00478d',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Clock size={18} />
            <div>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, fontFamily: 'Manrope, sans-serif' }}>
                Edit history
              </h3>
              <p style={{ margin: 0, fontSize: 11, opacity: 0.85 }}>
                {history?.length || 0} action{(history?.length || 0) === 1 ? '' : 's'} · append-only
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'white',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 4,
            }}
          >
            <X size={20} />
          </button>
        </header>

        {/* AI baseline toggle */}
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #e5e7eb',
            background: '#f8f9fa',
            flexShrink: 0,
          }}
        >
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: hasOriginal ? 'pointer' : 'not-allowed',
              opacity: hasOriginal ? 1 : 0.5,
            }}
            title={hasOriginal ? 'Show what the AI extracted before any reviewer edits' : 'AI baseline not captured for this document. Run migration 005 + reprocess to enable.'}
          >
            <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>
              Show AI baseline beside fields
            </span>
            <input
              type="checkbox"
              checked={!!showOriginal}
              onChange={onToggleOriginal}
              disabled={!hasOriginal}
              style={{ width: 16, height: 16, cursor: hasOriginal ? 'pointer' : 'not-allowed' }}
            />
          </label>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#6b7280' }}>
            {hasOriginal
              ? 'When on, edited fields show the original AI value below in amber.'
              : 'Migration 005 + reprocess required to capture AI baseline for this doc.'}
          </p>
        </div>

        {/* timeline */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
          {loading && (
            <p style={{ textAlign: 'center', padding: 24, color: '#6b7280', fontSize: 13 }}>
              Loading history…
            </p>
          )}
          {!loading && sortedHistory.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px 16px', color: '#6b7280' }}>
              <Clock size={28} style={{ opacity: 0.4, marginBottom: 8 }} />
              <p style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>No edits yet</p>
              <p style={{ margin: '4px 0 0', fontSize: 11 }}>
                Every edit, accept, approve, and reject will appear here in real time.
              </p>
              <p style={{ margin: '8px 0 0', fontSize: 11, fontStyle: 'italic' }}>
                Note: requires migration 005. Until then, actions are not persisted.
              </p>
            </div>
          )}
          {!loading && sortedHistory.map((row) => {
            const Icon = ICONS[row.action] || Edit3;
            const color = COLORS[row.action] || '#6b7280';
            return (
              <div
                key={row.id}
                style={{
                  marginBottom: 10,
                  padding: 10,
                  border: '1px solid #e5e7eb',
                  borderRadius: 8,
                  background: 'white',
                  borderLeft: `3px solid ${color}`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <Icon size={14} style={{ color }} />
                  <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color, letterSpacing: '0.04em' }}>
                    {row.action}
                  </span>
                  <span style={{ marginLeft: 'auto', fontSize: 11, color: '#6b7280' }}>
                    {fmtTime(row.created_at)}
                  </span>
                </div>
                {row.field_path && (
                  <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#374151', marginBottom: 4 }}>
                    {row.field_path}
                  </div>
                )}
                {(row.from_value !== null && row.from_value !== undefined || row.to_value !== null && row.to_value !== undefined) && (
                  <div style={{ fontSize: 12, color: '#374151', display: 'flex', alignItems: 'baseline', gap: 4, flexWrap: 'wrap' }}>
                    <span>{fmtVal(row.from_value)}</span>
                    <span style={{ color: '#9ca3af' }}>→</span>
                    <span style={{ fontWeight: 600 }}>{fmtVal(row.to_value)}</span>
                  </div>
                )}
                {row.notes && (
                  <p style={{ margin: '6px 0 0', fontSize: 11, color: '#6b7280', fontStyle: 'italic' }}>
                    "{row.notes}"
                  </p>
                )}
                {/* Promotion summary — only on approve actions when the
                    promoter ran. metadata.promotion shape comes from
                    extraction_promoter.PromotionResult.to_dict(). */}
                {row.action === 'approve' && row.metadata?.promotion && (() => {
                  const p = row.metadata.promotion;
                  const ps = p.patient_summary || {};
                  const conf = p.match_confidence || 'n/a';
                  // Confidence pill: high (id_number) green, medium (name_dob)
                  // amber, ambiguous warning red, created neutral.
                  let confColor = '#6b7280', confLabel = 'NEW PATIENT';
                  if (conf === 'id_number')      { confColor = '#15803d'; confLabel = 'MATCHED · SA ID'; }
                  else if (conf === 'name_dob') {
                    confColor = ps.ambiguous ? '#dc2626' : '#a16207';
                    confLabel = ps.ambiguous ? 'AMBIGUOUS · NAME+DOB' : 'MATCHED · NAME+DOB';
                  }
                  return (
                    <div style={{
                      marginTop: 8, padding: 8, background: '#f0fdf4',
                      border: '1px solid #bbf7d0', borderRadius: 6, fontSize: 11,
                    }}>
                      <div style={{ fontWeight: 700, color: '#15803d', marginBottom: 4 }}>
                        Promoted to EHR
                      </div>
                      {/* Patient match summary */}
                      <div style={{
                        marginBottom: 6, padding: '4px 6px',
                        background: '#fff', border: '1px solid #d1fae5', borderRadius: 4,
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        gap: 6,
                      }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {[ps.first_name, ps.last_name].filter(Boolean).join(' ') || '(unknown name)'}
                          </div>
                          <div style={{ color: '#6b7280', fontSize: 10 }}>
                            DOB {ps.dob || '—'}{ps.id_number ? ` · ID ${ps.id_number}` : ''}
                          </div>
                        </div>
                        <span style={{
                          fontSize: 9, fontWeight: 700, letterSpacing: '0.04em',
                          color: confColor, padding: '2px 6px',
                          background: '#fff', border: `1px solid ${confColor}`,
                          borderRadius: 3, whiteSpace: 'nowrap',
                        }}>{confLabel}</span>
                      </div>
                      {ps.ambiguous && (
                        <div style={{
                          marginBottom: 6, padding: '4px 6px',
                          background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 4,
                          color: '#991b1b', fontSize: 10,
                        }}>
                          ⚠ {ps.other_candidates || 0} other patient(s) share this surname + DOB. Verify the right one was matched.
                        </div>
                      )}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 12px', color: '#374151' }}>
                        {Object.entries(p.counts || {}).map(([k, v]) => (
                          <div key={k}>
                            <span style={{ color: '#6b7280' }}>{k}:</span>{' '}
                            <span style={{ fontWeight: 600 }}>{v}</span>
                          </div>
                        ))}
                      </div>
                      {p.warnings?.length > 0 && (
                        <div style={{ marginTop: 4, color: '#a16207', fontStyle: 'italic' }}>
                          {p.warnings.length} warning(s)
                        </div>
                      )}
                    </div>
                  );
                })()}
                {row.action === 'approve' && row.metadata?.promotion_error && (
                  <div style={{
                    marginTop: 8, padding: 8, background: '#fef2f2',
                    border: '1px solid #fecaca', borderRadius: 6, fontSize: 11,
                    color: '#991b1b',
                  }}>
                    <div style={{ fontWeight: 700, marginBottom: 2 }}>
                      Promotion failed
                    </div>
                    <div style={{ fontFamily: 'monospace' }}>{row.metadata.promotion_error}</div>
                  </div>
                )}
                {row.user_email && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, color: '#6b7280' }}>
                    <User size={11} />
                    {row.user_email}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </aside>
    </>
  );
}
