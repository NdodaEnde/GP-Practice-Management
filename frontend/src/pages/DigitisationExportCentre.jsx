import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';

const MIcon = ({ name, className = '', filled = false }) => (
  <span
    className={`material-symbols-outlined ${className}`}
    style={filled ? { fontVariationSettings: "'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24" } : undefined}
    aria-hidden="true"
  >
    {name}
  </span>
);

const formatRel = (isoStr) => {
  if (!isoStr) return '—';
  const ms = Date.now() - new Date(isoStr).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.round(h / 24);
  return `${d} day${d === 1 ? '' : 's'} ago`;
};

const statusPill = {
  success: { bg: 'bg-secondary-container', text: 'text-on-secondary-container', label: 'SUCCESS' },
  partial: { bg: 'bg-tertiary-fixed',      text: 'text-on-tertiary-fixed-variant', label: 'PARTIAL' },
  failed:  { bg: 'bg-error-container',     text: 'text-on-error-container', label: 'FAILED' },
  queued:  { bg: 'bg-primary-fixed',       text: 'text-on-primary-fixed-variant', label: 'QUEUED' },
  running: { bg: 'bg-primary-fixed',       text: 'text-on-primary-fixed-variant', label: 'RUNNING' },
};

const formatLabel = (f) => ({ fhir_r4: 'FHIR R4', csv: 'CSV', json: 'JSON' }[f] || (f || '—').toUpperCase());

const DigitisationExportCentre = () => {
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading]           = useState(true);
  const [industryType, setIndustryType] = useState('healthcare');
  const [history, setHistory]           = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [submitting, setSubmitting]     = useState(false);
  const [submitMsg, setSubmitMsg]       = useState(null);
  const [defaultConn, setDefaultConn]   = useState(null);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await axios.get(`${BACKEND_URL}/api/digitisation/exports?limit=20`);
      setHistory(res.data.exports || []);
    } catch (err) {
      console.error('ExportCentre history load failed', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Pending = validated docs that haven't been exported. Until the export
        // pipeline tracks per-doc export state, "pending" ≈ all validated docs.
        const [docsRes, typesRes, connsRes] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/digitisation/documents?limit=200&status=validated`),
          axios.get(`${BACKEND_URL}/api/digitisation/doc-types`),
          axios.get(`${BACKEND_URL}/api/digitisation/fhir/connections`).catch(() => ({ data: { connections: [] } })),
        ]);
        if (cancelled) return;
        setPendingCount((docsRes.data.documents || []).length);
        setIndustryType(typesRes.data.industry_type || 'healthcare');
        const conns = connsRes.data?.connections || [];
        setDefaultConn(conns.find(c => c.is_default) || conns[0] || null);
      } catch (err) {
        console.error('ExportCentre load failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    loadHistory();
    return () => { cancelled = true; };
  }, []);

  const queueExport = async (format) => {
    setSubmitting(true);
    setSubmitMsg(null);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/digitisation/exports`, { format });
      const job = res.data.job;
      setSubmitMsg({
        kind: 'success',
        text: `Queued ${job.batch_id} — ${job.record_count} record${job.record_count === 1 ? '' : 's'} (${formatLabel(job.format)}). Bundle generation runs out-of-band.`,
      });
      await loadHistory();
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Failed to queue export';
      setSubmitMsg({ kind: 'error', text: detail });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto space-y-xl">
      {/* Header */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-md">
        <div>
          <h1 className="font-h1 text-h1 text-on-surface">Export Centre</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant mt-xs">
            Push validated records into your EHR via FHIR / CSV / JSON.
          </p>
        </div>
        <button
          onClick={() => queueExport('fhir_r4')}
          disabled={submitting || pendingCount === 0}
          className="inline-flex items-center gap-base px-lg py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <MIcon name={submitting ? 'progress_activity' : 'send'} className={`!text-[20px] ${submitting ? 'animate-spin' : ''}`} />
          {submitting ? 'Queuing…' : `Export New Records (FHIR)`}
        </button>
      </section>

      {submitMsg && (
        <div
          role="status"
          className={`rounded-lg px-md py-sm font-body-sm text-body-sm ${
            submitMsg.kind === 'success'
              ? 'bg-secondary-container text-on-secondary-container'
              : 'bg-error-container text-on-error-container'
          }`}
        >
          {submitMsg.text}
        </div>
      )}

      {/* Hero metric + System config */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <div className="lg:col-span-2 bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex flex-col md:flex-row md:items-center justify-between gap-md">
          <div>
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Pending Export</span>
            <div className="font-h1 text-[64px] leading-none font-extrabold text-on-surface mt-base">
              {loading ? '…' : pendingCount}
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant mt-xs">
              Validated records ready to push to your EHR.
            </p>
          </div>
          <div className="bg-primary-fixed text-primary p-md rounded-xl flex flex-col items-center gap-base min-w-[200px]">
            <MIcon name="cloud_sync" className="!text-[40px]" filled />
            <span className="font-label-caps text-label-caps uppercase">FHIR Sync Ready</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant">{industryType.replace(/_/g, ' ')}</span>
          </div>
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex flex-col gap-sm">
          <h3 className="font-h3 text-h3 text-on-surface mb-base">System Configuration</h3>
          <div className="bg-surface-container-low border border-outline-variant rounded-lg p-md flex items-center gap-md">
            <div className="w-10 h-10 rounded-lg bg-secondary-container text-on-secondary-container flex items-center justify-center">
              <MIcon name="dns" className="!text-[20px]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-body-sm text-body-sm font-bold text-on-surface">
                {defaultConn ? defaultConn.name : 'No FHIR endpoint configured'}
              </p>
              <p className="font-body-sm text-body-sm text-on-surface-variant truncate">
                {defaultConn ? defaultConn.fhir_url : 'Click Configure Connection to set one up'}
              </p>
            </div>
            {defaultConn ? (
              <span className="inline-flex items-center gap-1 font-label-caps text-label-caps uppercase text-on-surface-variant">
                <MIcon name="circle" className="!text-[10px]" />
                {defaultConn.environment}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 font-label-caps text-label-caps uppercase text-error">
                <MIcon name="info" className="!text-[16px]" />
                None
              </span>
            )}
          </div>
          <Link
            to="/digitisation/export/connect"
            className="mt-base inline-flex items-center justify-center gap-base px-md py-sm border border-primary text-primary rounded-lg font-body-sm font-bold hover:bg-primary-fixed transition-colors"
          >
            <MIcon name="settings" className="!text-[18px]" />
            Configure Connection
          </Link>
        </div>
      </div>

      {/* Recent export history */}
      <section className="space-y-md">
        <div className="flex items-center justify-between">
          <h3 className="font-h3 text-h3 text-on-surface">Recent Export History</h3>
          <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Last 30 days</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead className="bg-surface-container-low">
              <tr>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Batch ID</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Records</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Format</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Status</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Timestamp</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {historyLoading && (
                <tr><td colSpan={6} className="px-lg py-xl text-center text-on-surface-variant">Loading export history…</td></tr>
              )}
              {!historyLoading && history.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-lg py-xl text-center font-body-md text-body-md text-on-surface-variant">
                    No exports yet. Click <span className="font-bold">Export New Records</span> above to queue your first batch.
                  </td>
                </tr>
              )}
              {!historyLoading && history.map((row) => {
                const pill = statusPill[row.status] || statusPill.queued;
                return (
                  <tr key={row.id} className="hover:bg-surface-container-low transition-colors">
                    <td className="px-lg py-md font-data-tabular font-body-md text-body-md text-on-surface">{row.batch_id}</td>
                    <td className="px-lg py-md font-body-sm text-body-sm text-on-surface-variant">{row.record_count}</td>
                    <td className="px-lg py-md">
                      <span className="bg-secondary-container px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase text-on-secondary-container">
                        {formatLabel(row.format)}
                      </span>
                    </td>
                    <td className="px-lg py-md">
                      <span className={`inline-block px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase ${pill.bg} ${pill.text}`} title={row.error_message || ''}>
                        {pill.label}
                      </span>
                    </td>
                    <td className="px-lg py-md font-body-sm text-body-sm text-on-surface-variant">{formatRel(row.created_at)}</td>
                    <td className="px-lg py-md text-right">
                      <a
                        href={row.bundle_url ? `${BACKEND_URL}/api/digitisation/exports/${row.id}/download` : undefined}
                        target="_blank"
                        rel="noreferrer"
                        title={row.bundle_url ? 'Download FHIR bundle' : `Bundle not available (status: ${row.status})`}
                        aria-disabled={!row.bundle_url}
                        onClick={(e) => { if (!row.bundle_url) e.preventDefault(); }}
                        className={`inline-flex items-center gap-base px-md py-sm rounded-lg font-body-sm font-bold transition-colors ${
                          row.bundle_url
                            ? 'bg-primary-fixed text-primary hover:bg-primary hover:text-on-primary'
                            : 'bg-surface-container-high text-on-surface-variant opacity-50 cursor-not-allowed'
                        }`}
                      >
                        <MIcon name={row.bundle_url ? 'download' : 'receipt_long'} className="!text-[18px]" />
                        {row.bundle_url ? 'Download' : 'Receipt'}
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant italic">
          Bundle generation runs in the background — refresh this page after a few seconds to see queued jobs transition to <strong>SUCCESS</strong> with a downloadable FHIR bundle.
        </p>
      </section>
    </div>
  );
};

export default DigitisationExportCentre;
