import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Lifted from groundtruth, verbatim — pointed at our local api adapter.
import EHRValidationPanel from '@/components/groundtruth/EHRValidationPanel';
import { FieldMetadataProvider } from '@/components/groundtruth/FieldMetadataContext';
import ValidationHistoryDrawer from '@/components/groundtruth/ValidationHistoryDrawer';
import PatientMatchModal from '@/components/groundtruth/PatientMatchModal';
import '@/components/groundtruth/ParsedView.css';

pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

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

// Strip markdown anchor tags for the chunk preview body.
const cleanChunkText = (s) => (s || '')
  .replace(/<a[^>]*>.*?<\/a>/g, '')
  .replace(/^[\s\n]+/, '');

// Resolve a fieldPath like "patient_demographics.full_names" or
// "diagnoses[0].icd10_code" against the extraction_metadata tree.
// Returns the leaf {value, references} or null.
function lookupFieldMetadata(metadata, fieldPath) {
  if (!metadata || !fieldPath) return null;
  const segments = fieldPath.split(/\.(?![^\[]*\])/); // split on dots outside [] segments
  let node = metadata;
  for (const seg of segments) {
    if (node == null) return null;
    const arrMatch = seg.match(/^([^\[]+)((?:\[\d+\])*)$/);
    if (!arrMatch) return null;
    const [, key, indices] = arrMatch;
    if (key) {
      node = node[key];
      if (node == null) return null;
    }
    if (indices) {
      const ix = [...indices.matchAll(/\[(\d+)\]/g)].map(m => Number(m[1]));
      for (const i of ix) {
        if (!Array.isArray(node)) return null;
        node = node[i];
        if (node == null) return null;
      }
    }
  }
  // Leaf form is { value, references }
  if (node && typeof node === 'object' && 'value' in node && 'references' in node) {
    return node;
  }
  return null;
}

const DigitisationValidationDetail = () => {
  const { documentId } = useParams();
  const navigate = useNavigate();

  const [docMeta, setDocMeta]                       = useState(null);
  const [pdfUrl, setPdfUrl]                         = useState(null);
  const [chunks, setChunks]                         = useState([]);
  const [extractionMetadata, setExtractionMetadata] = useState(null);
  const [loading, setLoading]                       = useState(true);
  const [error, setError]                           = useState(null);

  const [numPages, setNumPages]       = useState(null);
  const [pageNumber, setPageNumber]   = useState(1);
  const [pdfScale, setPdfScale]       = useState(1.0);
  const [pageSize, setPageSize]       = useState({ width: 0, height: 0 });

  const [selectedChunkId, setSelectedChunkId] = useState(null);
  const [hoveredChunkId, setHoveredChunkId]   = useState(null);
  const [activeTab, setActiveTab]     = useState('parsed'); // 'parsed' | 'validate'

  // Edit-history drawer state. `original` holds the AI baseline (extractions
  // captured at extract time, never modified) when migration 005 is in place.
  const [historyOpen, setHistoryOpen]       = useState(false);
  const [history, setHistory]               = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [aiBaseline, setAiBaseline]         = useState(null);
  const [showAiBaseline, setShowAiBaseline] = useState(false);

  // Patient-match confirmation modal — opens when /approve returns 409
  // with candidates (or pre-emptively via /preview-match). Reviewer
  // explicitly picks an existing patient or chooses to create new.
  const [matchModal, setMatchModal] = useState({
    open:         false,
    candidates:   [],
    demographics: null,
  });

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await axios.get(`${BACKEND_URL}/api/digitisation/validation/${documentId}/history`);
      setHistory(res.data.history || []);
      setAiBaseline(res.data.original || null);
    } catch (err) {
      console.warn('history load failed', err);
    } finally {
      setHistoryLoading(false);
    }
  }, [documentId]);

  useEffect(() => { refreshHistory(); }, [refreshHistory]);

  // Resizable divider — left pane width as % (clamped 25-75)
  const [leftWidth, setLeftWidth]     = useState(50);
  const [isDragging, setIsDragging]   = useState(false);
  const containerRef                  = useRef(null);

  const [busy, setBusy]               = useState(false);
  const overviewScrollRef             = useRef(null);
  const chunkRefs                     = useRef({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${BACKEND_URL}/api/digitisation/validation/${documentId}`);
        if (cancelled) return;
        setDocMeta(res.data.document);
        setPdfUrl(res.data.pdf_url);
        setChunks(res.data.chunks || []);
        setExtractionMetadata(res.data.extraction_metadata || null);
      } catch (err) {
        console.error('ValidationDetail load failed', err);
        setError(err.response?.data?.detail || err.message || 'Failed to load document');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [documentId]);

  // ----- Resizable divider handlers (lifted from groundtruth App.jsx) -----
  const onDividerMouseDown = (e) => { setIsDragging(true); e.preventDefault(); };
  const handleMouseMove = useCallback((e) => {
    if (!isDragging || !containerRef.current) return;
    e.preventDefault();
    const rect = containerRef.current.getBoundingClientRect();
    const newLeft = ((e.clientX - rect.left) / rect.width) * 100;
    setLeftWidth(Math.max(25, Math.min(75, newLeft)));
  }, [isDragging]);
  const handleMouseUp = useCallback(() => setIsDragging(false), []);

  useEffect(() => {
    if (!isDragging) return;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // ----- Bidirectional grounding -----
  // PDF box clicked → scroll Overview to that chunk + select it
  const handleBoxClick = (chunk) => {
    setSelectedChunkId(chunk.id);
    setActiveTab('parsed');
    // Defer to allow tab switch to render the panel before scrolling.
    requestAnimationFrame(() => {
      const node = chunkRefs.current[chunk.id];
      if (node) node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  };
  // Overview chunk clicked → jump PDF to that page + select
  const handleChunkClick = (chunk) => {
    setSelectedChunkId(chunk.id);
    const targetPage = ((chunk.grounding || {}).page ?? 0) + 1;
    setPageNumber(targetPage);
  };

  // Field clicked in EHRValidationPanel → look up its grounded chunk references
  // in extraction_metadata, jump the PDF + Parsed View to the first one.
  // Fallback: naive token-match (only used when this field has no metadata,
  // e.g. on a doc processed before migration 004 / without LandingAI grounding).
  const handleFieldFocus = (fieldPath) => {
    if (!chunks.length) return;

    // 1. Resolve the field's references via the flattened metadata map.
    const leafMeta = lookupFieldMetadata(extractionMetadata, fieldPath);
    const refs = leafMeta?.references || [];
    let match = null;
    if (refs.length > 0) {
      // Use the FIRST grounded chunk; the panel will show the rest as a count.
      match = chunks.find(c => c.id === refs[0]);
    }

    // 2. Fallback to heuristic token match.
    if (!match) {
      const token = (fieldPath || '').split(/[._\[\]]/).pop()?.toLowerCase();
      if (token && token.length >= 3) {
        match = chunks.find(c => (c.markdown || c.content || '').toLowerCase().includes(token));
      }
    }

    if (!match) return;
    setSelectedChunkId(match.id);
    setPageNumber(((match.grounding || {}).page ?? 0) + 1);
    // Don't switch tabs — the PDF highlight on the left is the value-add and
    // is always visible. Forcing Parsed View kicks the reviewer out of the
    // Validate tab they were trying to edit in. If they're already on Parsed
    // View, scroll the matched chunk into view; otherwise the highlight on
    // the PDF is sufficient.
    if (activeTab === 'parsed') {
      requestAnimationFrame(() => {
        const node = chunkRefs.current[match.id];
        if (node) node.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
  };

  // Approval flow: try /approve plain. If the backend returns 409 with
  // candidates, open the PatientMatchModal so the reviewer can confirm
  // which existing patient (or whether to create new). The follow-up
  // call passes the explicit override.
  const submitApprove = async (overrides = {}) => {
    setBusy(true);
    try {
      await axios.post(
        `${BACKEND_URL}/api/digitisation/validation/${documentId}/approve`,
        overrides,
      );
      setMatchModal({ open: false, candidates: [], demographics: null });
      navigate('/digitisation/validation');
      return true;
    } catch (err) {
      const detail = err?.response?.data?.detail;
      // 409 + needs_confirmation → surface the modal instead of an alert
      if (err?.response?.status === 409 && detail?.needs_confirmation) {
        setMatchModal({
          open:         true,
          candidates:   detail.candidates || [],
          demographics: detail.demographics || null,
        });
        return false;
      }
      alert(typeof detail === 'string' ? detail : (detail?.message || err.message));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async () => {
    if (!window.confirm('Approve this document? Extracted records will be marked validated.')) return;
    await submitApprove({});
  };

  const handleConfirmMatch = (patient_id) =>
    submitApprove({ confirmed_patient_id: patient_id });

  const handleCreateNew = () =>
    submitApprove({ create_new_patient: true });

  const handleReject = async () => {
    const reason = window.prompt('Reason for rejection (≥10 chars):');
    if (!reason || reason.trim().length < 10) {
      alert('Reason must be at least 10 characters.');
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/digitisation/validation/${documentId}/reject`, { reason });
      navigate('/digitisation/validation');
    } catch (err) {
      alert(err.response?.data?.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="max-w-[1500px] mx-auto py-xl text-center text-on-surface-variant">Loading document…</div>;
  if (error) return (
    <div className="max-w-[1500px] mx-auto py-xl text-center">
      <p className="text-error font-body-md text-body-md">{error}</p>
      <Link to="/digitisation/validation" className="inline-block mt-md text-primary hover:underline font-body-sm">← Back to queue</Link>
    </div>
  );

  const filename = docMeta?.filename || '—';
  const docType  = docMeta?.doc_type;
  const status   = (docMeta?.status || '').toLowerCase();
  const statusPill = {
    parsed:             { bg: 'bg-tertiary-fixed',     text: 'text-on-tertiary-fixed-variant', label: 'PARSED' },
    extracted:          { bg: 'bg-primary-fixed',      text: 'text-on-primary-fixed-variant',  label: 'EXTRACTED' },
    pending_validation: { bg: 'bg-primary-fixed',      text: 'text-on-primary-fixed-variant',  label: 'PENDING' },
    validated:          { bg: 'bg-secondary-container', text: 'text-on-secondary-container',   label: 'VALIDATED' },
    approved:           { bg: 'bg-secondary-container', text: 'text-on-secondary-container',   label: 'APPROVED' },
    rejected:           { bg: 'bg-error-container',     text: 'text-on-error-container',       label: 'REJECTED' },
  }[status] || { bg: 'bg-surface-variant', text: 'text-on-surface-variant', label: status.toUpperCase() };

  const onPageRenderSuccess = (page) => setPageSize({ width: page.width, height: page.height });
  const pageChunks = chunks.filter(c => ((c.grounding || {}).page ?? 0) + 1 === pageNumber);

  return (
    <div className="max-w-[1600px] mx-auto space-y-md">
      {/* M3 header */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-md bg-surface-container-lowest border border-outline-variant rounded-xl p-md">
        <div className="flex items-center gap-md">
          <Link to="/digitisation/validation" className="w-10 h-10 rounded-lg bg-surface-container-high text-on-surface-variant hover:bg-surface-variant flex items-center justify-center transition-colors" aria-label="Back to queue">
            <MIcon name="arrow_back" className="!text-[20px]" />
          </Link>
          <div className="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center">
            <MIcon name="picture_as_pdf" className="!text-[22px]" />
          </div>
          <div>
            <h1 className="font-h2 text-h2 text-on-surface">{filename}</h1>
            <div className="flex items-center gap-base mt-1 flex-wrap">
              <span className="font-data-tabular font-body-sm text-body-sm text-on-surface-variant">
                DOC-{documentId.slice(0, 8).toUpperCase()}
              </span>
              <span className={`inline-block px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase ${statusPill.bg} ${statusPill.text}`}>
                {statusPill.label}
              </span>
              {docType && (
                <span className="bg-secondary-container px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase text-on-secondary-container">
                  {docType}
                </span>
              )}
              <span className="font-body-sm text-body-sm text-on-surface-variant">
                {chunks.length} chunks · {numPages || '?'} pages
              </span>
            </div>
          </div>
        </div>
        <div className="flex gap-sm">
          <button
            onClick={() => { setHistoryOpen(true); refreshHistory(); }}
            className="inline-flex items-center gap-base px-md py-sm border border-outline-variant text-on-surface-variant rounded-lg font-body-sm font-bold hover:bg-surface-container transition-colors"
            title="View edit history + toggle AI baseline overlay"
          >
            <MIcon name="history" className="!text-[18px]" />
            History
            {history.length > 0 && (
              <span className="ml-1 inline-block min-w-[18px] h-[18px] px-1 bg-primary text-on-primary rounded-full text-[10px] font-bold leading-[18px] text-center">
                {history.length}
              </span>
            )}
          </button>
          <button onClick={handleReject} disabled={busy}
            className="inline-flex items-center gap-base px-lg py-sm border border-error text-error rounded-lg font-body-sm font-bold hover:bg-error-container/40 transition-colors disabled:opacity-50">
            <MIcon name="block" className="!text-[18px]" />
            Reject
          </button>
          <button onClick={handleApprove} disabled={busy}
            className="inline-flex items-center gap-base px-lg py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 transition-opacity disabled:opacity-50">
            <MIcon name="check_circle" className="!text-[18px]" filled />
            Approve & Save
          </button>
        </div>
      </section>

      {/* Split panel with resizable divider */}
      <div
        ref={containerRef}
        className="flex bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden"
        style={{ height: 'calc(100vh - 200px)', minHeight: '600px' }}
      >
        {/* Left — PDF viewer */}
        <div style={{ width: `${leftWidth}%` }} className="flex flex-col">
          <div className="px-md py-sm border-b border-outline-variant flex items-center justify-between bg-surface-container shrink-0">
            <h3 className="font-h3 text-h3 text-on-surface">Source Document</h3>
            <div className="flex items-center gap-base">
              <button onClick={() => setPdfScale(s => Math.max(0.5, +(s - 0.1).toFixed(1)))}
                className="w-8 h-8 rounded-lg hover:bg-surface-variant flex items-center justify-center text-on-surface-variant" aria-label="Zoom out">
                <MIcon name="zoom_out" className="!text-[18px]" />
              </button>
              <span className="font-data-tabular font-body-sm text-body-sm text-on-surface-variant min-w-[44px] text-center">{Math.round(pdfScale * 100)}%</span>
              <button onClick={() => setPdfScale(s => Math.min(2.5, +(s + 0.1).toFixed(1)))}
                className="w-8 h-8 rounded-lg hover:bg-surface-variant flex items-center justify-center text-on-surface-variant" aria-label="Zoom in">
                <MIcon name="zoom_in" className="!text-[18px]" />
              </button>
              <span className="w-px h-5 bg-outline-variant mx-1" />
              <button onClick={() => setPageNumber(p => Math.max(1, p - 1))} disabled={pageNumber <= 1}
                className="w-8 h-8 rounded-lg hover:bg-surface-variant flex items-center justify-center text-on-surface-variant disabled:opacity-40" aria-label="Previous page">
                <MIcon name="chevron_left" className="!text-[20px]" />
              </button>
              <span className="font-data-tabular font-body-sm text-body-sm text-on-surface-variant min-w-[60px] text-center">{pageNumber} / {numPages || '?'}</span>
              <button onClick={() => setPageNumber(p => Math.min(numPages || p, p + 1))} disabled={!numPages || pageNumber >= numPages}
                className="w-8 h-8 rounded-lg hover:bg-surface-variant flex items-center justify-center text-on-surface-variant disabled:opacity-40" aria-label="Next page">
                <MIcon name="chevron_right" className="!text-[20px]" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-auto p-md bg-surface flex justify-center">
            {pdfUrl ? (
              <Document
                file={pdfUrl}
                onLoadSuccess={({ numPages }) => setNumPages(numPages)}
                loading={<div className="text-on-surface-variant py-xl">Loading PDF…</div>}
                error={<div className="text-error py-xl">Failed to render PDF.</div>}
              >
                <div className="relative inline-block shadow-md">
                  <Page
                    pageNumber={pageNumber}
                    scale={pdfScale}
                    renderAnnotationLayer={false}
                    renderTextLayer={false}
                    onRenderSuccess={onPageRenderSuccess}
                  />
                  {pageSize.width > 0 && pageChunks.map((chunk) => {
                    const box = chunk.grounding?.box;
                    if (!box) return null;
                    const left   = box.left * pageSize.width;
                    const top    = box.top * pageSize.height;
                    const width  = (box.right - box.left) * pageSize.width;
                    const height = (box.bottom - box.top) * pageSize.height;
                    const isSelected = selectedChunkId === chunk.id;
                    const isHovered  = hoveredChunkId === chunk.id;
                    return (
                      <button
                        key={chunk.id}
                        onClick={() => handleBoxClick(chunk)}
                        onMouseEnter={() => setHoveredChunkId(chunk.id)}
                        onMouseLeave={() => setHoveredChunkId(null)}
                        className="absolute cursor-pointer"
                        style={{
                          left, top, width, height,
                          background:  isSelected ? 'rgba(0, 71, 141, 0.20)' : isHovered ? 'rgba(0, 106, 99, 0.15)' : 'transparent',
                          border:      isSelected ? '2px solid #00478d' : isHovered ? '2px solid #006a63' : '1px dashed rgba(66, 71, 82, 0.25)',
                          borderRadius: 2,
                          transition: 'background 0.15s, border 0.15s',
                        }}
                        aria-label={`Chunk ${chunk.id}`}
                      />
                    );
                  })}
                </div>
              </Document>
            ) : (
              <div className="flex flex-col items-center justify-center text-on-surface-variant py-xl">
                <MIcon name="folder_off" className="!text-[40px] mb-md" />
                <p className="font-body-md text-body-md">Source PDF unavailable.</p>
              </div>
            )}
          </div>
        </div>

        {/* Resizable divider */}
        <div
          className={`gt-divider ${isDragging ? 'active' : ''}`}
          onMouseDown={onDividerMouseDown}
          aria-label="Drag to resize"
        />

        {/* Right — Parsed View / Validate & Save tabs */}
        <div style={{ width: `${100 - leftWidth}%` }} className="flex flex-col">
          {/* Tab strip */}
          <div className="gt-tab-strip">
            <button
              className={`gt-tab-btn ${activeTab === 'parsed' ? 'active' : ''}`}
              onClick={() => setActiveTab('parsed')}
            >
              <MIcon name="visibility" className="!text-[16px]" />
              Parsed View
            </button>
            <button
              className={`gt-tab-btn ${activeTab === 'validate' ? 'active' : ''}`}
              onClick={() => setActiveTab('validate')}
            >
              <MIcon name="edit_note" className="!text-[16px]" />
              Validate & Save
            </button>
            <span className="ml-auto text-[11px] text-on-surface-variant px-2">
              {chunks.length} chunks · click to highlight on PDF
            </span>
          </div>

          {/* Tab content */}
          {activeTab === 'parsed' ? (
            <div className="gt-overview-panel">
              <div className="gt-overview-header">
                <h3>📄 Document Overview</h3>
                <p className="subtitle">
                  {chunks.length} section{chunks.length !== 1 ? 's' : ''} · click any chunk to highlight on the PDF
                </p>
              </div>
              <div className="gt-overview-content" ref={overviewScrollRef}>
                {chunks.length === 0 ? (
                  <p className="text-center text-on-surface-variant italic py-md">No chunks parsed.</p>
                ) : chunks.map((chunk) => {
                  const isSelected = selectedChunkId === chunk.id;
                  const isHovered  = hoveredChunkId === chunk.id;
                  const page = ((chunk.grounding || {}).page ?? 0) + 1;
                  return (
                    <div
                      key={chunk.id}
                      ref={(node) => { chunkRefs.current[chunk.id] = node; }}
                      className={`gt-chunk-card ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''}`}
                      onClick={() => handleChunkClick(chunk)}
                      onMouseEnter={() => setHoveredChunkId(chunk.id)}
                      onMouseLeave={() => setHoveredChunkId(null)}
                    >
                      <div className="gt-chunk-header">
                        <span className="gt-chunk-page">Page {page}</span>
                        <span className="gt-chunk-type">{chunk.type || 'text'}</span>
                      </div>
                      <div
                        className={`gt-chunk-content ${chunk.type !== 'table' ? 'truncated' : ''}`}
                        dangerouslySetInnerHTML={{ __html: cleanChunkText(chunk.markdown || chunk.content) }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-auto">
              <FieldMetadataProvider
                extractionMetadata={extractionMetadata}
                originalExtractions={aiBaseline}
                showOriginal={showAiBaseline}
              >
                <EHRValidationPanel
                  docId={documentId}
                  chunks={chunks}
                  onFieldFocus={handleFieldFocus}
                  onSaveSuccess={() => { refreshHistory(); }}
                  isRecord={false}
                />
              </FieldMetadataProvider>
            </div>
          )}
        </div>
      </div>

      <ValidationHistoryDrawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        history={history}
        loading={historyLoading}
        hasOriginal={aiBaseline != null}
        showOriginal={showAiBaseline}
        onToggleOriginal={() => setShowAiBaseline(v => !v)}
      />

      <PatientMatchModal
        open={matchModal.open}
        busy={busy}
        candidates={matchModal.candidates}
        demographics={matchModal.demographics}
        onUseExisting={handleConfirmMatch}
        onCreateNew={handleCreateNew}
        onCancel={() => setMatchModal({ open: false, candidates: [], demographics: null })}
      />
    </div>
  );
};

export default DigitisationValidationDetail;
