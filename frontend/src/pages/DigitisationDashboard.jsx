import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '@/contexts/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';
const API_BASE = `${BACKEND_URL}/api/digitisation`;

const MIcon = ({ name, className = '' }) => (
  <span className={`material-symbols-outlined ${className}`} aria-hidden="true">{name}</span>
);

// Map backend `status` values to display label + badge style for the recent
// activity table. Falls back to UPLOADED if unknown.
const statusMeta = {
  validated:          { label: 'VALIDATED',  badge: 'bg-secondary-container text-on-secondary-container', action: 'visibility' },
  approved:           { label: 'VALIDATED',  badge: 'bg-secondary-container text-on-secondary-container', action: 'visibility' },
  extracted:          { label: 'AWAITING',   badge: 'bg-primary-fixed text-on-primary-fixed-variant',     action: 'play_circle' },
  pending_validation: { label: 'AWAITING',   badge: 'bg-primary-fixed text-on-primary-fixed-variant',     action: 'play_circle' },
  validating:         { label: 'IN REVIEW',  badge: 'bg-primary-fixed text-on-primary-fixed-variant',     action: 'play_circle' },
  parsed:             { label: 'PARSING',    badge: 'bg-tertiary-fixed text-on-tertiary-fixed-variant',   action: 'hourglass_empty' },
  parsing:            { label: 'PARSING',    badge: 'bg-tertiary-fixed text-on-tertiary-fixed-variant',   action: 'hourglass_empty' },
  uploaded:           { label: 'UPLOADED',   badge: 'bg-surface-variant text-on-surface-variant',         action: 'edit' },
  rejected:           { label: 'REJECTED',   badge: 'bg-error-container text-on-error-container',         action: 'visibility' },
};
const metaFor = (status) => statusMeta[(status || '').toLowerCase()] || statusMeta.uploaded;

const todayLabel = () =>
  new Date().toLocaleDateString('en-ZA', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

// Type C "Digitisation Workspace" landing page — a daily "what needs me now"
// to-do screen. Reads live data from /api/digitisation/dashboard; every number
// links to the list behind it. Same routes / destinations as before.
const DigitisationDashboard = () => {
  const { user } = useAuth();
  // No honorific — the digitisation user is often admin / reception, not a
  // clinician, so "Dr." is presumptuous. Greet by first name when we have it.
  const firstName = user?.first_name || '';
  const workspaceName = user?.workspace_name || 'Your Practice';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [retrying, setRetrying] = useState({});
  const [range, setRange] = useState('week'); // throughput toggle: today | week | month

  const load = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/dashboard`);
      setData(res.data);
      setErr(null);
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const retry = async (docId) => {
    setRetrying((r) => ({ ...r, [docId]: true }));
    try {
      await axios.post(`${API_BASE}/documents/${docId}/reprocess`);
      await load();
    } catch (_) {
      /* surfaced on next load; keep the row */
    } finally {
      setRetrying((r) => ({ ...r, [docId]: false }));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (err) {
    return (
      <div className="max-w-2xl mx-auto bg-error-container text-on-error-container p-lg rounded-xl">
        <p className="font-h3 text-h3 mb-xs">Couldn't load dashboard</p>
        <p className="font-body-sm text-body-sm">{err}</p>
      </div>
    );
  }

  const credits        = data?.page_credits        || { used: 0, total: 0, percent: 0 };
  const awaiting       = data?.awaiting_validation  || { total: 0, high_confidence: 0 };
  const pipeline       = data?.pipeline             || { uploaded: 0, processing: 0, needs_review: awaiting.total || 0, validated: 0 };
  const attention      = data?.needs_attention      || [];
  const recentActivity = data?.recent_activity      || [];
  const stats          = data?.quick_stats          || { total_digitised: 0, this_month: 0, validation_accuracy: null };
  const throughput     = data?.throughput           || { today: 0, week: 0, month: 0 };

  const windowOpts = [
    { id: 'today', label: 'Today' },
    { id: 'week',  label: '7 days' },
    { id: 'month', label: '30 days' },
  ];

  // Funnel cards — live pipeline snapshot (current state, not a time window).
  // Each links to the list behind it (per design decision).
  const funnel = [
    { key: 'uploaded',   n: pipeline.uploaded,     label: 'Uploaded',         dot: 'bg-on-surface-variant', to: '/digitisation/documents', tone: 'text-on-surface' },
    { key: 'processing', n: pipeline.processing,   label: 'Processing',       dot: 'bg-primary',            to: '/digitisation/documents', tone: 'text-on-surface' },
    { key: 'review',     n: pipeline.needs_review, label: 'Needs your review', dot: 'bg-amber-500',         to: '/digitisation/validation', tone: 'text-amber-600' },
    { key: 'validated',  n: pipeline.validated,    label: 'Validated',        dot: 'bg-secondary',          to: '/digitisation/archive',   tone: 'text-secondary' },
  ];

  // Three hero states: brand-new (nothing digitised yet) → onboarding;
  // caught-up (had work, none waiting) → reassurance; otherwise → to-do.
  const totalInPipeline =
    (pipeline.uploaded || 0) + (pipeline.processing || 0) + (pipeline.needs_review || 0) + (pipeline.validated || 0);
  const isFirstRun = totalInPipeline === 0 && recentActivity.length === 0 && attention.length === 0;
  const caughtUp = !isFirstRun && awaiting.total === 0;

  return (
    <div className="max-w-[1200px] mx-auto space-y-lg">
      {/* Greeting */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-md">
        <div className="flex flex-col gap-xs">
          <h1 className="font-h1 text-h1 text-on-surface">{firstName ? `Good day, ${firstName}` : 'Good day'}</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">{todayLabel()} · {workspaceName}</p>
        </div>
        <Link
          to="/digitisation/documents"
          className="inline-flex items-center gap-base px-lg py-sm bg-on-surface text-surface rounded-lg font-body-sm font-bold hover:bg-inverse-surface transition-colors whitespace-nowrap"
        >
          <MIcon name="upload_file" className="!text-[18px]" />
          Upload Documents
        </Link>
      </div>

      {/* Hero — three states: first-run · caught-up · to-do */}
      {isFirstRun ? (
        <div className="bg-primary-fixed/60 border border-primary rounded-xl p-xl flex flex-col items-center text-center gap-md">
          <div className="bg-surface rounded-full p-md">
            <MIcon name="cloud_upload" className="text-primary !text-[40px]" />
          </div>
          <div>
            <h2 className="font-h3 text-h3 text-on-surface">Welcome to your digitisation workspace</h2>
            <p className="font-body-md text-body-md text-on-surface-variant mt-xs max-w-xl">
              Upload your first document — a PDF or scan of a patient file — and we'll extract the
              data for you to review. Nothing's been digitised here yet.
            </p>
          </div>
          <Link
            to="/digitisation/documents"
            className="inline-flex items-center gap-base px-lg py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:bg-primary-container transition-colors"
          >
            <MIcon name="upload_file" className="!text-[18px]" />
            Upload your first document
          </Link>
        </div>
      ) : caughtUp ? (
        <div className="bg-secondary-container/40 border border-secondary rounded-xl p-lg flex items-center gap-lg">
          <MIcon name="task_alt" className="text-secondary !text-[40px]" />
          <div className="flex-1">
            <h2 className="font-h3 text-h3 text-on-surface">You're all caught up</h2>
            <p className="font-body-md text-body-md text-on-surface-variant mt-xs">
              No documents waiting for review. Upload a new batch to keep going.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 border-l-4 border-l-amber-500 rounded-xl p-lg flex flex-col sm:flex-row items-start sm:items-center gap-lg">
          <div className="font-h1 text-[46px] leading-none font-bold text-amber-600">{awaiting.total}</div>
          <div className="flex-1">
            <h2 className="font-h3 text-h3 text-on-surface">
              document{awaiting.total === 1 ? '' : 's'} waiting for your review
            </h2>
            <p className="font-body-md text-body-md text-on-surface-variant mt-xs">
              Reviewing keeps records trustworthy before they're stored or exported.
            </p>
          </div>
          <Link
            to="/digitisation/validation"
            className="inline-flex items-center gap-base px-lg py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:bg-primary-container transition-colors whitespace-nowrap"
          >
            Start reviewing
            <MIcon name="arrow_forward" className="!text-[18px]" />
          </Link>
        </div>
      )}

      {/* Funnel — live pipeline; each card links to its list */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-md">
        {funnel.map((c) => (
          <Link
            key={c.key}
            to={c.to}
            className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg hover:-translate-y-0.5 hover:border-primary transition-all"
          >
            <p className={`font-h1 text-h1 ${c.tone}`}>{Number(c.n || 0).toLocaleString()}</p>
            <p className="font-body-sm text-body-sm text-on-surface-variant mt-xs flex items-center gap-base">
              <span className={`w-2 h-2 rounded-full ${c.dot}`} />
              {c.label}
            </p>
          </Link>
        ))}
      </div>

      {/* Two-column: work (left) + practice info (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg items-start">
        <div className="lg:col-span-2 space-y-lg">
          {/* Needs attention — only when there's something */}
          {attention.length > 0 && (
            <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
              <div className="p-md border-b border-outline-variant flex items-center gap-base bg-surface-container">
                <MIcon name="warning" className="text-error !text-[20px]" />
                <h3 className="font-h3 text-h3 text-on-surface">Needs attention</h3>
              </div>
              {attention.map((a) => (
                <div key={a.document_id} className="flex items-center gap-md px-md py-md border-b border-outline-variant last:border-b-0">
                  <div className="w-9 h-9 rounded-lg bg-error-container text-on-error-container grid place-items-center flex-shrink-0">
                    <MIcon name="error" className="!text-[20px]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-body-sm text-body-sm font-semibold text-on-surface truncate" title={a.name}>{a.name}</p>
                    <p className="font-body-sm text-body-sm text-on-surface-variant truncate" title={a.reason}>{a.reason}</p>
                  </div>
                  <button
                    onClick={() => retry(a.document_id)}
                    disabled={retrying[a.document_id]}
                    className="font-body-sm text-body-sm font-bold text-primary bg-primary-fixed px-md py-1.5 rounded-lg hover:bg-primary hover:text-on-primary transition-colors disabled:opacity-50"
                  >
                    {retrying[a.document_id] ? 'Retrying…' : 'Retry'}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Recent activity */}
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
            <div className="p-md border-b border-outline-variant flex justify-between items-center bg-surface-container">
              <h3 className="font-h3 text-h3 text-on-surface">Recent activity</h3>
              <Link to="/digitisation/archive" className="font-body-sm text-body-sm font-semibold text-primary hover:underline">View all</Link>
            </div>
            <table className="w-full text-left border-collapse">
              <thead className="bg-surface-container-high">
                <tr>
                  <th className="px-md py-sm font-label-caps text-label-caps uppercase text-on-surface-variant">Document</th>
                  <th className="px-md py-sm font-label-caps text-label-caps uppercase text-on-surface-variant text-center">Status</th>
                  <th className="px-md py-sm font-label-caps text-label-caps uppercase text-on-surface-variant text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {recentActivity.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-md py-lg text-center font-body-sm text-body-sm text-on-surface-variant">
                      No recent activity yet — upload a document to get started.
                    </td>
                  </tr>
                )}
                {recentActivity.map((row) => {
                  const meta = metaFor(row.status);
                  const targetIsValidation = ['extracted', 'parsed', 'pending_validation', 'validating'].includes((row.status || '').toLowerCase());
                  return (
                    <tr key={row.document_id || row.name}>
                      <td className="px-md py-md font-data-tabular font-body-sm text-body-sm font-medium text-on-surface truncate max-w-[420px]" title={row.name}>
                        {row.name}
                      </td>
                      <td className="px-md py-md text-center">
                        <span className={`inline-block px-base py-1 rounded-lg font-label-caps text-label-caps uppercase ${meta.badge}`}>
                          {meta.label}
                        </span>
                      </td>
                      <td className="px-md py-md text-right">
                        {targetIsValidation && row.document_id ? (
                          <Link
                            to={`/digitisation/validation/${row.document_id}`}
                            className="inline-flex items-center justify-center p-1 rounded-full text-primary hover:text-primary-container hover:bg-surface-container transition-colors"
                            title="Open in validation"
                          >
                            <MIcon name={meta.action} className="!text-[20px]" />
                          </Link>
                        ) : (
                          <span className="inline-flex items-center justify-center p-1 rounded-full text-outline">
                            <MIcon name={meta.action} className="!text-[20px]" />
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-lg">
          {/* Page credits */}
          <div className="bg-surface-container-lowest p-lg rounded-xl border border-outline-variant flex flex-col gap-md">
            <div className="flex justify-between items-start gap-base">
              <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Pages this month</p>
              <Link to="/digitisation/insights" className="font-body-sm text-body-sm font-semibold text-primary hover:underline whitespace-nowrap">Usage history</Link>
            </div>
            <p className="font-h2 text-h2 text-on-surface">
              {Number(credits.used).toLocaleString()} / {Number(credits.total).toLocaleString()}
            </p>
            <div className="space-y-xs">
              <div className="flex justify-between font-body-sm text-body-sm font-medium text-on-surface-variant">
                <span>Monthly fair-use</span>
                <span>{credits.percent}%</span>
              </div>
              <div className="h-3 w-full bg-surface-container-high rounded-full overflow-hidden">
                <div
                  className={`h-full ${credits.percent >= 100 ? 'bg-error' : credits.percent >= 80 ? 'bg-amber-500' : 'bg-primary'}`}
                  style={{ width: `${Math.min(credits.percent, 100)}%` }}
                />
              </div>
              {credits.percent >= 80 && (
                <p className={`font-body-sm text-body-sm ${credits.percent >= 100 ? 'text-error' : 'text-amber-600'}`}>
                  {credits.percent >= 100
                    ? 'Over your monthly fair-use allowance — uploads still work; we may reach out about usage.'
                    : 'Approaching your monthly fair-use allowance.'}
                </p>
              )}
            </div>
          </div>

          {/* Throughput — windowed toggle (live data, never the queue) */}
          <div className="bg-surface-container-lowest p-lg rounded-xl border border-outline-variant">
            <div className="flex items-center justify-between gap-base mb-md">
              <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Activity</p>
              <div className="inline-flex bg-surface-container-high rounded-lg p-0.5">
                {windowOpts.map((o) => (
                  <button
                    key={o.id}
                    onClick={() => setRange(o.id)}
                    className={`px-base py-1 rounded-md font-label-caps text-label-caps uppercase transition-colors ${
                      range === o.id ? 'bg-surface text-primary shadow-sm' : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <p className="font-h2 text-h2 text-on-surface">{Number(throughput[range] || 0).toLocaleString()}</p>
            <p className="font-body-sm text-body-sm text-on-surface-variant mt-xs">
              Documents uploaded {range === 'today' ? 'today' : range === 'week' ? 'in the last 7 days' : 'in the last 30 days'}
            </p>
            <div className="flex justify-between items-center py-xs mt-md font-body-md text-body-md border-t border-outline-variant pt-md">
              <span className="text-on-surface-variant">Total validated</span>
              <b className="text-on-surface">{Number(stats.total_digitised || 0).toLocaleString()}</b>
            </div>
            {stats.validation_accuracy != null && (
              <div className="flex justify-between items-center py-xs font-body-md text-body-md border-t border-outline-variant">
                <span className="text-on-surface-variant">Validation accuracy</span>
                <b className="text-on-surface">{Number(stats.validation_accuracy).toFixed(1)}%</b>
              </div>
            )}
          </div>

          {/* Export entry (preserves the export workflow shortcut) */}
          <Link
            to="/digitisation/export"
            className="w-full bg-primary text-on-primary py-sm rounded-lg font-body-sm font-bold text-center hover:opacity-90 transition-opacity inline-flex items-center justify-center gap-base"
          >
            <MIcon name="send" className="!text-[18px]" />
            Export Centre
          </Link>
        </div>
      </div>

      {/* Trust reassurance */}
      <div className="flex flex-wrap items-center gap-md pt-xs">
        <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-on-surface-variant">
          <MIcon name="verified" className="text-secondary !text-[18px]" /> POPIA Compliant
        </span>
        <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-on-surface-variant">
          <MIcon name="encrypted" className="text-secondary !text-[18px]" /> End-to-End Encryption
        </span>
        <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-on-surface-variant">
          <MIcon name="lock" className="text-secondary !text-[18px]" /> Your data is isolated to {workspaceName}
        </span>
      </div>
    </div>
  );
};

export default DigitisationDashboard;
