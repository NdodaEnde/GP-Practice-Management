import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '@/contexts/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';
const API_BASE = `${BACKEND_URL}/api/digitisation`;

const MIcon = ({ name, className = '' }) => (
  <span className={`material-symbols-outlined ${className}`} aria-hidden="true">{name}</span>
);

// Map backend `status` values (digitised_documents.status) to display label,
// badge style, and the row-action icon. Falls back to UPLOADED if unknown.
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
const metaFor = (status) =>
  statusMeta[(status || '').toLowerCase()] || statusMeta.uploaded;

// EHR connection status is not yet a backend concept (TRACEABILITY 6 / FHIR
// Connection Wizard). Keep the static placeholder until that endpoint lands.
const placeholderEhr = {
  state: 'connected',
  lastSyncRelative: '—',
  pendingRecords: 0,
  targetSystem: 'Not yet configured',
};

const ehrPills = {
  connected:    { label: 'Connected',    bg: 'bg-secondary-container', text: 'text-on-secondary-container', dot: 'bg-secondary' },
  attention:    { label: 'Auth Needed',  bg: 'bg-tertiary-fixed',      text: 'text-on-tertiary-fixed-variant', dot: 'bg-tertiary' },
  disconnected: { label: 'Disconnected', bg: 'bg-error-container',     text: 'text-on-error-container',     dot: 'bg-error' },
};

// Type C "Digitisation Workspace" landing page. Reads live data from
// /api/digitisation/dashboard. EHR-connection block remains a placeholder
// pending the FHIR Connection Wizard work.
const DigitisationDashboard = () => {
  const { user } = useAuth();
  const firstName = user?.first_name || 'Doctor';
  const workspaceName = user?.workspace_name || 'Your Practice';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_BASE}/dashboard`);
        if (!cancelled) setData(res.data);
      } catch (e) {
        if (!cancelled) setErr(e?.response?.data?.detail || e.message || 'Failed to load dashboard');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

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

  const credits             = data?.page_credits        || { used: 0, total: 0, percent: 0 };
  const awaitingValidation  = data?.awaiting_validation || { total: 0, high_confidence: 0 };
  const recentActivity      = data?.recent_activity     || [];
  const stats               = data?.quick_stats         || { total_digitised: 0, this_month: 0, validation_accuracy: null };
  const ehrStatus           = placeholderEhr;
  const ehrPill             = ehrPills[ehrStatus.state];

  return (
    <div className="max-w-[1200px] mx-auto space-y-lg">
      {/* Welcome header */}
      <div className="flex flex-col gap-xs">
        <h1 className="font-h1 text-h1 text-on-surface">Welcome back, Dr. {firstName}</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">{workspaceName}</p>
      </div>

      {/* Top KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-lg">
        {/* Page credits */}
        <div className="bg-surface-container-lowest p-lg rounded-xl border border-outline-variant flex flex-col gap-md">
          <div className="flex justify-between items-start gap-md">
            <div className="flex flex-col gap-xs">
              <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Page Credits This Month</p>
              <p className="font-h2 text-h2 text-on-surface">
                {Number(credits.used).toLocaleString()} / {Number(credits.total).toLocaleString()}
              </p>
            </div>
            <Link
              to="/digitisation/insights"
              className="bg-primary text-on-primary px-md py-sm rounded-lg font-body-sm font-bold hover:bg-primary-container transition-colors whitespace-nowrap"
            >
              View Usage History
            </Link>
          </div>
          <div className="space-y-xs">
            <div className="flex justify-between font-body-sm text-body-sm font-medium text-on-surface-variant">
              <span>Usage Progress</span>
              <span>{credits.percent}%</span>
            </div>
            <div className="h-3 w-full bg-surface-container-high rounded-full overflow-hidden">
              <div className="h-full bg-primary" style={{ width: `${credits.percent}%` }} />
            </div>
          </div>
        </div>

        {/* Awaiting validation */}
        <div className="bg-surface-container-lowest p-lg rounded-xl border border-outline-variant flex flex-col gap-md">
          <div className="flex flex-col gap-xs">
            <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Awaiting Validation</p>
            <div className="flex items-center gap-base">
              <MIcon name="pending_actions" className="text-primary !text-[28px]" />
              <p className="font-h2 text-h2 text-on-surface">{awaitingValidation.total} document{awaitingValidation.total === 1 ? '' : 's'}</p>
            </div>
            <p className="font-body-sm text-body-sm font-semibold text-secondary">
              ({awaitingValidation.high_confidence} high confidence)
            </p>
          </div>
          <div className="mt-auto">
            <Link
              to="/digitisation/validation"
              className="w-full bg-primary text-on-primary px-md py-sm rounded-lg font-body-sm font-bold hover:bg-primary-container transition-colors flex items-center justify-center gap-base"
            >
              <MIcon name="clinical_notes" className="!text-[18px]" />
              Open Validation Queue
            </Link>
          </div>
        </div>
      </div>

      {/* Central upload zone */}
      <Link
        to="/digitisation/documents"
        className="block bg-surface-container-low border-2 border-dashed border-outline-variant rounded-xl p-xl flex flex-col items-center justify-center text-center gap-md hover:border-primary transition-colors"
      >
        <div className="bg-primary-fixed p-md rounded-full">
          <MIcon name="cloud_upload" className="text-primary !text-[40px]" />
        </div>
        <div className="space-y-xs">
          <h2 className="font-h3 text-h3 text-on-surface">Drop PDFs here or click to upload</h2>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Accepts: handwritten notes, typed reports, scanned files
          </p>
        </div>
        <span className="bg-on-surface text-surface px-lg py-sm rounded-lg font-body-sm font-bold inline-flex items-center gap-base hover:bg-inverse-surface transition-colors">
          <MIcon name="upload_file" className="!text-[18px]" />
          Upload Documents
        </span>
      </Link>

      {/* Activity + EHR Connection */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        {/* Recent Activity */}
        <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
          <div className="p-md border-b border-outline-variant flex justify-between items-center bg-surface-container">
            <h3 className="font-h3 text-h3 text-on-surface">Recent Activity</h3>
            <Link to="/digitisation/archive" className="font-body-sm text-body-sm font-semibold text-primary hover:underline">
              View All
            </Link>
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

        {/* EHR Connection Status — placeholder until the FHIR Connection
            Wizard ships (TRACEABILITY 6, separate work item). */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-lg flex flex-col gap-md">
          <div className="flex items-center justify-between gap-base">
            <h3 className="font-h3 text-h3 text-on-surface">EHR Connection</h3>
            <span className={`inline-flex items-center gap-1.5 px-base py-1 rounded-full font-label-caps text-label-caps uppercase ${ehrPill.bg} ${ehrPill.text}`}>
              <span className={`w-2 h-2 rounded-full ${ehrPill.dot}`} />
              {ehrPill.label}
            </span>
          </div>
          <div className="bg-surface-container-low p-md rounded-lg border border-outline-variant">
            <p className="font-label-caps text-label-caps uppercase text-on-surface-variant tracking-tight">Target System</p>
            <p className="font-body-md text-body-md font-medium text-on-surface mt-1">{ehrStatus.targetSystem}</p>
          </div>
          <div className="grid grid-cols-2 gap-base">
            <div className="bg-surface-container-low p-md rounded-lg border border-outline-variant">
              <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Last Sync</p>
              <p className="font-body-sm text-body-sm font-medium text-on-surface mt-1">{ehrStatus.lastSyncRelative}</p>
            </div>
            <div className="bg-surface-container-low p-md rounded-lg border border-outline-variant">
              <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Pending</p>
              <p className="font-body-sm text-body-sm font-medium text-on-surface mt-1">{ehrStatus.pendingRecords} records</p>
            </div>
          </div>
          <div className="flex flex-col gap-sm mt-auto">
            <Link
              to="/digitisation/export"
              className="w-full bg-primary text-on-primary py-sm rounded-lg font-body-sm font-bold text-center hover:opacity-90 transition-opacity inline-flex items-center justify-center gap-base"
            >
              <MIcon name="send" className="!text-[18px]" />
              Export New Records
            </Link>
            <button className="w-full border border-primary text-primary py-sm rounded-lg font-body-sm font-bold hover:bg-primary-fixed transition-colors inline-flex items-center justify-center gap-base">
              <MIcon name="settings" className="!text-[18px]" />
              Configure Connection
            </button>
          </div>
        </div>
      </div>

      {/* Footer Quick Stats */}
      <div className="bg-surface-container-highest border-t border-outline-variant rounded-xl px-lg py-md">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-lg text-center md:text-left">
          <div className="flex flex-col gap-xs">
            <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Total Digitised</p>
            <p className="font-h2 text-h2 text-on-surface">{Number(stats.total_digitised || 0).toLocaleString()}</p>
          </div>
          <div className="flex flex-col gap-xs border-t md:border-t-0 md:border-x border-outline-variant py-md md:py-0 md:px-lg">
            <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">This Month</p>
            <p className="font-h2 text-h2 text-on-surface">{Number(stats.this_month || 0).toLocaleString()}</p>
          </div>
          <div className="flex flex-col gap-xs">
            <p className="font-label-caps text-label-caps uppercase text-on-surface-variant">Validation Accuracy</p>
            <div className="flex items-center justify-center md:justify-start gap-base">
              {stats.validation_accuracy == null ? (
                <p className="font-body-md text-body-md text-on-surface-variant italic">Pending</p>
              ) : (
                <>
                  <p className="font-h2 text-h2 text-on-surface">{Number(stats.validation_accuracy).toFixed(1)}%</p>
                  <MIcon name="trending_up" className="text-secondary !text-[22px]" />
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* POPIA strip */}
      <div className="w-full rounded-xl overflow-hidden bg-surface-container-highest p-lg flex flex-col md:flex-row items-start md:items-center gap-md">
        <div className="flex-1 space-y-xs">
          <h3 className="font-h3 text-h3 text-on-surface">Precision Data Conversion</h3>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-xl">
            SurgiScan interprets handwritten clinical notes and scanned reports
            into structured FHIR R4 and CSV records ready for your EHR.
          </p>
        </div>
        <div className="flex gap-md">
          <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-on-surface">
            <MIcon name="verified" className="text-secondary !text-[18px]" />
            POPIA Compliant
          </span>
          <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-on-surface">
            <MIcon name="encrypted" className="text-secondary !text-[18px]" />
            End-to-End Encryption
          </span>
        </div>
      </div>
    </div>
  );
};

export default DigitisationDashboard;
