import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import DigitisationUploader from '@/components/DigitisationUploader';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';

// Material Symbols Outlined wrapper.
const MIcon = ({ name, className = '' }) => (
  <span className={`material-symbols-outlined ${className}`} aria-hidden="true">{name}</span>
);

// Five visible pipeline stages — the table renders a stepper for each row.
const STAGES = ['Uploaded', 'Parsing', 'Split', 'Extracted', 'Validated'];

// Map server statuses to a stage index (1-based — 0 means not started).
// Anything ≥ index is "complete"; equal to index is "active".
const STATUS_TO_STAGE = {
  uploaded:              1,
  uploading:             1,
  queued_for_processing: 1,
  parsing:               2,
  parsed:                3,
  split:                 3,
  extracting:            4,
  extracted:             4,
  pending_validation:    4,
  validated:             5,
  approved:              5,
  rejected:             -1,
  failed:               -1,
  parsing_failed:       -1,
};

const stageFor = (status) => STATUS_TO_STAGE[(status || '').toLowerCase()] ?? 0;

const statusFilters = [
  { id: 'all',         label: 'All',         server: null },
  { id: 'in_progress', label: 'In Progress', server: ['uploaded', 'parsing', 'parsed', 'pending_validation'] },
  { id: 'validated',   label: 'Validated',   server: ['validated', 'approved'] },
  { id: 'rejected',    label: 'Rejected',    server: ['rejected'] },
];

const DocumentsPipeline = () => {
  const [docTypes, setDocTypes] = useState([]);
  const [industryType, setIndustryType] = useState('healthcare');
  const [documents, setDocuments] = useState([]);
  const [activeFilter, setActiveFilter] = useState('all');
  const [activeDocType, setActiveDocType] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploaderOpen, setUploaderOpen] = useState(false);

  const reloadDocuments = async () => {
    try {
      const docsRes = await axios.get(`${BACKEND_URL}/api/digitisation/documents?limit=50`);
      setDocuments(docsRes.data.documents || []);
    } catch (err) {
      console.error('reloadDocuments failed', err);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [typesRes, docsRes] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/digitisation/doc-types`),
          axios.get(`${BACKEND_URL}/api/digitisation/documents?limit=50`),
        ]);
        if (cancelled) return;
        setDocTypes(typesRes.data.doc_types || []);
        setIndustryType(typesRes.data.industry_type || 'healthcare');
        setDocuments(docsRes.data.documents || []);
      } catch (err) {
        console.error('DocumentsPipeline load failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Auto-refresh every 6s when the uploader is open OR the table has any
  // in-progress rows. Stops polling once everything settles.
  useEffect(() => {
    const inProgress = documents.some(d => statusFilters[1].server.includes((d.status || '').toLowerCase()));
    if (!inProgress && !uploaderOpen) return;
    const interval = setInterval(reloadDocuments, 6000);
    return () => clearInterval(interval);
  }, [documents, uploaderOpen]);

  const filteredDocs = useMemo(() => {
    let docs = documents;
    const filter = statusFilters.find(f => f.id === activeFilter);
    if (filter?.server) {
      docs = docs.filter(d => filter.server.includes((d.status || '').toLowerCase()));
    }
    if (activeDocType) {
      docs = docs.filter(d => d.doc_type === activeDocType);
    }
    return docs;
  }, [documents, activeFilter, activeDocType]);

  const counts = useMemo(() => ({
    all:         documents.length,
    in_progress: documents.filter(d => statusFilters[1].server.includes((d.status || '').toLowerCase())).length,
    validated:   documents.filter(d => statusFilters[2].server.includes((d.status || '').toLowerCase())).length,
    rejected:    documents.filter(d => statusFilters[3].server.includes((d.status || '').toLowerCase())).length,
  }), [documents]);

  const queueActive = counts.in_progress;
  const queueProgressPct = Math.min(100, Math.round((queueActive / Math.max(documents.length, 1)) * 100));

  return (
    <div className="max-w-[1280px] mx-auto space-y-xl">
      {/* Header */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-md">
        <div>
          <h1 className="font-h1 text-h1 text-on-surface">Documents Pipeline</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant mt-xs">Precision OCR and automated data extraction.</p>
        </div>
        <div className="flex gap-sm">
          <button className="flex items-center gap-base px-lg py-sm bg-surface-container-lowest border border-outline rounded-lg font-body-sm font-bold text-primary hover:bg-primary hover:text-on-primary transition-colors">
            <MIcon name="filter_list" className="!text-[20px]" />
            Filter View
          </button>
          <button
            onClick={() => setUploaderOpen(v => !v)}
            className="flex items-center gap-base px-lg py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 transition-opacity"
          >
            <MIcon name={uploaderOpen ? 'close' : 'upload_file'} className="!text-[20px]" />
            {uploaderOpen ? 'Close Uploader' : 'New Batch'}
          </button>
        </div>
      </section>

      {/* Upload zone + stat cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <div className="lg:col-span-2">
          <DigitisationUploader onComplete={reloadDocuments} />
        </div>

        {/* Bento stat cards */}
        <div className="grid grid-cols-1 gap-md">
          <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Queue Status</span>
              <MIcon name="bolt" className="text-secondary !text-[22px]" />
            </div>
            <div className="mt-md">
              <div className="font-h1 text-h1 text-on-surface">{queueActive}</div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">Active in pipeline</p>
            </div>
            <div className="mt-lg h-2 w-full bg-surface-container-high rounded-full overflow-hidden">
              <div className="bg-secondary h-full" style={{ width: `${queueProgressPct}%` }} />
            </div>
          </div>

          <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Validated</span>
              <MIcon name="verified" className="text-primary !text-[22px]" />
            </div>
            <div className="mt-md">
              <div className="font-h1 text-h1 text-on-surface">{counts.validated}</div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">Successfully extracted</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter chips */}
      <section className="space-y-md">
        <div className="flex items-center justify-between flex-wrap gap-md">
          <h3 className="font-h3 text-h3 text-on-surface">Processing Pipeline</h3>
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
                {f.label} ({counts[f.id]})
              </button>
            ))}
          </div>
        </div>
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

        {/* Pipeline table */}
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead className="bg-surface-container-low border-b border-outline-variant">
              <tr>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Batch ID & Source</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Status Pipeline</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Metadata</th>
                <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {loading && (
                <tr><td colSpan={4} className="px-lg py-xl text-center text-on-surface-variant">Loading documents...</td></tr>
              )}
              {!loading && filteredDocs.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-lg py-xl text-center font-body-md text-body-md text-on-surface-variant">
                    No documents yet. Drop a PDF above to start the pipeline.
                  </td>
                </tr>
              )}
              {!loading && filteredDocs.map((doc) => {
                const stage = stageFor(doc.status);
                const errored = stage === -1;
                const sizeKB = doc.file_size ? Math.round(doc.file_size / 1024) : null;
                const isPdf = (doc.filename || '').toLowerCase().endsWith('.pdf');
                const sourceIconName = errored ? 'error' : isPdf ? 'picture_as_pdf' : 'description';
                const sourceIconBg = errored ? 'bg-error-container/40 text-error' : 'bg-primary-fixed text-primary';
                return (
                  <tr key={doc.id} className="hover:bg-surface-container-low transition-colors">
                    <td className="px-lg py-md">
                      <div className="flex items-center gap-md">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${sourceIconBg}`}>
                          <MIcon name={sourceIconName} className="!text-[22px]" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-data-tabular font-body-md text-body-md text-on-surface">
                            DOC-{doc.id.slice(0, 8).toUpperCase()}
                          </div>
                          <div className="font-body-sm text-body-sm text-on-surface-variant truncate max-w-[260px]">{doc.filename}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-lg py-md">
                      <Stepper stage={stage} />
                    </td>
                    <td className="px-lg py-md">
                      <div className="flex flex-wrap gap-xs">
                        {doc.pages_count != null && (
                          <span className="bg-surface-container-high px-base py-0.5 rounded-lg font-label-caps text-label-caps text-on-surface-variant">
                            {doc.pages_count} Pages
                          </span>
                        )}
                        {sizeKB != null && (
                          <span className="bg-surface-container-high px-base py-0.5 rounded-lg font-label-caps text-label-caps text-on-surface-variant">
                            {sizeKB} KB
                          </span>
                        )}
                        {doc.doc_type && (
                          <span className="bg-secondary-container px-base py-0.5 rounded-lg font-label-caps text-label-caps text-on-secondary-container">
                            {doc.doc_type}
                          </span>
                        )}
                        {errored && (
                          <span className="bg-error-container/40 px-base py-0.5 rounded-lg font-label-caps text-label-caps text-error">
                            Error
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-lg py-md text-right">
                      <button className="p-sm hover:bg-surface-container-high rounded-full transition-colors">
                        <MIcon name="more_vert" className="text-on-surface-variant !text-[20px]" />
                      </button>
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

const Stepper = ({ stage }) => {
  // stage = -1 (error) | 0 (not started) | 1..5 (current/last completed)
  return (
    <div className="flex items-center gap-xs">
      {STAGES.map((label, idx) => {
        const i = idx + 1;
        const isActive = stage === i;
        const isComplete = stage >= i && stage !== -1;
        const isErrored = stage === -1 && i === 2;

        let iconName = 'pending';
        let iconColor = 'text-outline';
        let labelColor = 'text-on-surface-variant';

        if (isErrored) {
          iconName = 'cancel';
          iconColor = 'text-error';
          labelColor = 'text-error';
        } else if (isComplete) {
          iconName = i === 5 ? 'verified' : 'check_circle';
          iconColor = 'text-secondary';
          labelColor = 'text-secondary';
        } else if (isActive) {
          iconName = 'hourglass_empty';
          iconColor = 'text-primary animate-pulse';
          labelColor = 'text-primary';
        }

        const showFilled = isComplete || isErrored;

        return (
          <React.Fragment key={label}>
            <div className="flex flex-col items-center gap-1 min-w-[58px]">
              <span
                className={`material-symbols-outlined !text-[18px] ${iconColor}`}
                style={showFilled ? { fontVariationSettings: "'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24" } : undefined}
                aria-hidden="true"
              >
                {iconName}
              </span>
              <span className={`font-label-caps text-[10px] uppercase font-bold tracking-tight ${labelColor}`}>
                {isErrored ? 'Failed' : label}
              </span>
            </div>
            {idx < STAGES.length - 1 && (
              <div className={`w-base h-[2px] mb-md ${
                stage > i && stage !== -1 ? 'bg-secondary' :
                stage === -1 && idx === 0 ? 'bg-error' :
                'bg-outline-variant'
              }`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default DocumentsPipeline;
