import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';

const MIcon = ({ name, className = '' }) => (
  <span className={`material-symbols-outlined ${className}`} aria-hidden="true">{name}</span>
);

// Friendly relative-time formatter — close enough for queue timestamps.
const relativeTime = (isoStr) => {
  if (!isoStr) return '—';
  const ms = Date.now() - new Date(isoStr).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d} day${d === 1 ? '' : 's'} ago`;
  const mo = Math.round(d / 30);
  return `${mo} month${mo === 1 ? '' : 's'} ago`;
};

const statusFilters = [
  { id: 'all',     label: 'All',     match: () => true },
  { id: 'pending', label: 'Pending', match: (s) => ['pending_validation', 'extracted'].includes((s || '').toLowerCase()) },
  { id: 'parsed',  label: 'Parsed',  match: (s) => (s || '').toLowerCase() === 'parsed' },
];

const DigitisationValidationQueue = () => {
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState({ parsed: 0, pending: 0, validated: 0, rejected: 0, total: 0 });
  const [industryType, setIndustryType] = useState('healthcare');
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('pending');
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/digitisation/validation/queue?limit=200`);
        if (cancelled) return;
        setQueue(res.data.queue || []);
        setStats(res.data.stats || {});
        setIndustryType(res.data.industry_type || 'healthcare');
      } catch (err) {
        console.error('ValidationQueue load failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filteredQueue = useMemo(() => {
    const filter = statusFilters.find(f => f.id === activeFilter);
    let docs = filter ? queue.filter(d => filter.match(d.status)) : queue;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      docs = docs.filter(d =>
        (d.filename || '').toLowerCase().includes(q) ||
        (d.id || '').toLowerCase().includes(q) ||
        (d.doc_type || '').toLowerCase().includes(q)
      );
    }
    return docs;
  }, [queue, activeFilter, search]);

  const counts = useMemo(() => ({
    all:     queue.length,
    pending: queue.filter(d => statusFilters[1].match(d.status)).length,
    parsed:  queue.filter(d => statusFilters[2].match(d.status)).length,
  }), [queue]);

  return (
    <div className="max-w-[1280px] mx-auto space-y-xl">
      {/* Header */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-md">
        <div>
          <h1 className="font-h1 text-h1 text-on-surface">Validation Queue</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant mt-xs">
            Review extracted records and approve them for export to your EHR.
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <div className="relative">
            <MIcon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant !text-[20px]" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by filename or ID"
              className="pl-10 pr-md py-sm bg-surface-container-lowest border border-outline-variant rounded-lg font-body-sm text-body-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:border-primary w-72"
            />
          </div>
        </div>
      </section>

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-lg">
        {[
          { label: 'Pending Review',   value: stats.pending,   icon: 'pending_actions', hint: 'awaiting validation', accent: 'text-primary' },
          { label: 'Validated',        value: stats.validated, icon: 'verified',         hint: 'approved + exported', accent: 'text-secondary' },
          { label: 'Rejected',         value: stats.rejected,  icon: 'block',            hint: 'flagged + returned',  accent: 'text-error' },
          { label: 'Total Processed',  value: stats.total,     icon: 'inventory_2',      hint: 'all time',            accent: 'text-on-surface' },
        ].map((k) => (
          <div key={k.label} className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md flex flex-col gap-sm">
            <div className="flex items-start justify-between">
              <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">{k.label}</span>
              <MIcon name={k.icon} className={`${k.accent} !text-[22px]`} />
            </div>
            <div>
              <div className="font-h1 text-h1 text-on-surface">{k.value ?? 0}</div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">{k.hint}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Filter chips + queue table */}
      <section className="space-y-md">
        <div className="flex items-center justify-between flex-wrap gap-md">
          <h3 className="font-h3 text-h3 text-on-surface">Awaiting your review</h3>
          <div className="flex gap-base flex-wrap">
            {statusFilters.map((f) => (
              <button
                key={f.id}
                onClick={() => setActiveFilter(f.id)}
                className={`px-md py-1 rounded-full font-label-caps text-label-caps uppercase transition-colors ${
                  activeFilter === f.id
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-variant'
                }`}
              >
                {f.label} ({counts[f.id] ?? 0})
              </button>
            ))}
            <span className="px-md py-1 rounded-full font-label-caps text-label-caps uppercase bg-surface-container text-on-surface-variant">
              {industryType}
            </span>
          </div>
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead className="bg-surface-container-low border-b border-outline-variant">
              <tr>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Document</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Doc Type</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Uploaded</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Status</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {loading && (
                <tr><td colSpan={5} className="px-lg py-xl text-center text-on-surface-variant">Loading queue...</td></tr>
              )}
              {!loading && filteredQueue.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-lg py-xl text-center font-body-md text-body-md text-on-surface-variant">
                    Nothing waiting on you. {stats.total > 0 ? 'All caught up.' : 'Upload some documents to get started.'}
                  </td>
                </tr>
              )}
              {!loading && filteredQueue.map((doc) => {
                const isPdf = (doc.filename || '').toLowerCase().endsWith('.pdf');
                const status = (doc.status || '').toLowerCase();
                const statusPill = {
                  parsed:             { bg: 'bg-tertiary-fixed', text: 'text-on-tertiary-fixed-variant', label: 'PARSED' },
                  extracted:          { bg: 'bg-primary-fixed',  text: 'text-on-primary-fixed-variant',  label: 'EXTRACTED' },
                  pending_validation: { bg: 'bg-primary-fixed',  text: 'text-on-primary-fixed-variant',  label: 'PENDING' },
                }[status] || { bg: 'bg-surface-variant', text: 'text-on-surface-variant', label: status.toUpperCase() };
                return (
                  <tr key={doc.id} className="hover:bg-surface-container-low transition-colors">
                    <td className="px-lg py-md">
                      <div className="flex items-center gap-md">
                        <div className="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center">
                          <MIcon name={isPdf ? 'picture_as_pdf' : 'description'} className="!text-[22px]" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-data-tabular font-body-md text-body-md text-on-surface">
                            DOC-{doc.id.slice(0, 8).toUpperCase()}
                          </div>
                          <div className="font-body-sm text-body-sm text-on-surface-variant truncate max-w-[280px]">{doc.filename}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-lg py-md">
                      {doc.doc_type ? (
                        <span className="bg-secondary-container px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase text-on-secondary-container">
                          {doc.doc_type}
                        </span>
                      ) : (
                        <span className="font-body-sm text-body-sm text-on-surface-variant italic">unclassified</span>
                      )}
                    </td>
                    <td className="px-lg py-md font-body-sm text-body-sm text-on-surface-variant">
                      {relativeTime(doc.upload_date || doc.created_at)}
                    </td>
                    <td className="px-lg py-md">
                      <span className={`inline-block px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase ${statusPill.bg} ${statusPill.text}`}>
                        {statusPill.label}
                      </span>
                    </td>
                    <td className="px-lg py-md text-right">
                      <Link
                        to={`/digitisation/validation/${doc.id}`}
                        className="inline-flex items-center gap-base px-md py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 transition-opacity"
                      >
                        <MIcon name="rate_review" className="!text-[18px]" />
                        Review
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default DigitisationValidationQueue;
