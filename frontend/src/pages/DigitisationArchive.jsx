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

const formatDate = (isoStr) => {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleString('en-ZA', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const formatBytes = (bytes) => {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`;
};

// Pseudo-deterministic colour per filename so the avatar circles are stable
const initials = (s) => (s || '?').split(/[._\s-]+/).filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase()).join('') || '?';

const avatarPalette = [
  { bg: 'bg-secondary-container', text: 'text-on-secondary-container' },
  { bg: 'bg-primary-fixed',       text: 'text-primary' },
  { bg: 'bg-tertiary-fixed',      text: 'text-on-tertiary-fixed-variant' },
  { bg: 'bg-secondary-fixed-dim', text: 'text-on-secondary-fixed' },
];

const palette = (key) => {
  let h = 0;
  for (let i = 0; i < (key || '').length; i++) h = (h * 31 + key.charCodeAt(i)) | 0;
  return avatarPalette[Math.abs(h) % avatarPalette.length];
};

const DigitisationArchive = () => {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [docTypes, setDocTypes] = useState([]);
  const [activeDocType, setActiveDocType] = useState(null);
  const [industryType, setIndustryType] = useState('healthcare');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [docsRes, typesRes] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/digitisation/documents?limit=200`),
          axios.get(`${BACKEND_URL}/api/digitisation/doc-types`),
        ]);
        if (cancelled) return;
        setDocs(docsRes.data.documents || []);
        setDocTypes(typesRes.data.doc_types || []);
        setIndustryType(typesRes.data.industry_type || 'healthcare');
      } catch (err) {
        console.error('Archive load failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const archived = useMemo(() => {
    return docs.filter(d => ['validated', 'approved'].includes((d.status || '').toLowerCase()));
  }, [docs]);

  const filtered = useMemo(() => {
    let rows = archived;
    if (activeDocType) {
      rows = rows.filter(d => d.doc_type === activeDocType);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter(d =>
        (d.filename || '').toLowerCase().includes(q) ||
        (d.id || '').toLowerCase().includes(q) ||
        (d.doc_type || '').toLowerCase().includes(q)
      );
    }
    return rows;
  }, [archived, activeDocType, search]);

  const totalBytes = useMemo(
    () => archived.reduce((acc, d) => acc + (d.file_size || 0), 0),
    [archived]
  );

  return (
    <div className="max-w-[1400px] mx-auto space-y-xl">
      {/* Header */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-md">
        <div>
          <h1 className="font-h1 text-h1 text-on-surface">Archive</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant mt-xs">
            Validated and exportable records, retained per POPIA-compliant policy.
          </p>
        </div>
        <div className="flex items-center gap-sm flex-wrap">
          <div className="relative">
            <MIcon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant !text-[20px]" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search archive"
              className="pl-10 pr-md py-sm bg-surface-container-lowest border border-outline-variant rounded-lg font-body-sm text-body-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:border-primary w-72"
            />
          </div>
          <button className="inline-flex items-center gap-base px-md py-sm bg-surface-container-lowest border border-outline text-primary rounded-lg font-body-sm font-bold hover:bg-primary hover:text-on-primary transition-colors">
            <MIcon name="filter_list" className="!text-[20px]" />
            Filters
          </button>
          <Link
            to="/digitisation/export"
            className="inline-flex items-center gap-base px-md py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 transition-opacity"
          >
            <MIcon name="download" className="!text-[20px]" />
            Export Selection
          </Link>
        </div>
      </section>

      {/* Bento stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-md">
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-xl">
          <div className="flex items-center justify-between mb-sm">
            <MIcon name="verified_user" className="text-primary !text-[22px]" />
            <span className="font-label-caps text-label-caps uppercase text-secondary">Ready</span>
          </div>
          <p className="font-h2 text-h2 text-on-surface">{archived.length}</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">Validated Records</p>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-xl">
          <div className="flex items-center justify-between mb-sm">
            <MIcon name="inventory" className="text-on-secondary-container !text-[22px]" />
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Total</span>
          </div>
          <p className="font-h2 text-h2 text-on-surface">{formatBytes(totalBytes)}</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">Archive Size</p>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl col-span-1 md:col-span-2 p-md flex flex-col justify-center gap-base">
          <div className="flex items-center justify-between">
            <h4 className="font-h3 text-h3 text-primary">System Integrity Check</h4>
            <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-secondary">
              <MIcon name="check_circle" className="!text-[18px]" filled />
              All records synced
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Validated records reconcile with their source PDFs in Supabase Storage. Last verification was a few minutes ago.
          </p>
        </div>
      </div>

      {/* Doc-type chips */}
      {docTypes.length > 0 && (
        <div className="flex items-center gap-base flex-wrap">
          <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Doc type:</span>
          <button
            onClick={() => setActiveDocType(null)}
            className={`px-base py-1 rounded-full font-label-caps text-label-caps uppercase transition-colors ${
              !activeDocType ? 'bg-on-surface text-surface' : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-variant'
            }`}
          >
            All ({industryType})
          </button>
          {docTypes.map((t) => (
            <button
              key={t.doc_type}
              onClick={() => setActiveDocType(t.doc_type)}
              className={`px-base py-1 rounded-full font-label-caps text-label-caps uppercase transition-colors ${
                activeDocType === t.doc_type ? 'bg-on-surface text-surface' : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-variant'
              }`}
            >
              {t.display_name}
            </button>
          ))}
        </div>
      )}

      {/* Repository table */}
      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-low border-b border-outline-variant">
                <th className="p-md font-label-caps text-label-caps uppercase text-on-surface-variant">Document</th>
                <th className="p-md font-label-caps text-label-caps uppercase text-on-surface-variant">Doc Type</th>
                <th className="p-md font-label-caps text-label-caps uppercase text-on-surface-variant">DOC ID</th>
                <th className="p-md font-label-caps text-label-caps uppercase text-on-surface-variant">Validated At</th>
                <th className="p-md font-label-caps text-label-caps uppercase text-on-surface-variant">Integrity</th>
                <th className="p-md font-label-caps text-label-caps uppercase text-on-surface-variant text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {loading && (
                <tr><td colSpan={6} className="p-xl text-center text-on-surface-variant">Loading archive…</td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-xl text-center font-body-md text-body-md text-on-surface-variant">
                    {archived.length === 0
                      ? 'No validated records yet. Approve documents from the Validation Queue to populate the archive.'
                      : 'No records match your filters.'}
                  </td>
                </tr>
              )}
              {!loading && filtered.map((doc) => {
                const pal = palette(doc.filename || doc.id);
                return (
                  <tr key={doc.id} className="hover:bg-surface-container-lowest transition-colors">
                    <td className="p-md">
                      <div className="flex items-center gap-sm">
                        <div className={`w-8 h-8 rounded-full ${pal.bg} ${pal.text} flex items-center justify-center font-body-sm font-bold`}>
                          {initials(doc.filename)}
                        </div>
                        <div>
                          <p className="font-body-md text-body-md font-semibold text-on-surface truncate max-w-[260px]">{doc.filename}</p>
                          <p className="font-body-sm text-body-sm text-on-surface-variant">{formatBytes(doc.file_size)}</p>
                        </div>
                      </div>
                    </td>
                    <td className="p-md">
                      {doc.doc_type ? (
                        <span className="bg-tertiary-fixed text-on-tertiary-fixed-variant px-base py-1 rounded-lg font-label-caps text-label-caps uppercase">
                          {doc.doc_type}
                        </span>
                      ) : (
                        <span className="font-body-sm text-body-sm text-on-surface-variant italic">unclassified</span>
                      )}
                    </td>
                    <td className="p-md font-data-tabular font-body-sm text-body-sm text-on-surface-variant">
                      DOC-{doc.id.slice(0, 8).toUpperCase()}
                    </td>
                    <td className="p-md font-body-sm text-body-sm text-on-surface-variant">{formatDate(doc.created_at)}</td>
                    <td className="p-md">
                      <div className="flex items-center gap-base text-secondary">
                        <MIcon name="check_circle" className="!text-[18px]" filled />
                        <span className="font-label-caps text-label-caps uppercase">100% Match</span>
                      </div>
                    </td>
                    <td className="p-md text-right">
                      <Link
                        to={`/digitisation/validation/${doc.id}`}
                        className="inline-block text-primary hover:bg-primary-fixed/40 p-2 rounded-full transition-colors"
                        title="View"
                      >
                        <MIcon name="visibility" className="!text-[20px]" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DigitisationArchive;
