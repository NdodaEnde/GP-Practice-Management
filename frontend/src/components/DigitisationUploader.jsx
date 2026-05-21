import React, { useCallback, useEffect, useRef, useState } from 'react';
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

const ALLOWED_EXTS = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'];
const MAX_BYTES = 50 * 1024 * 1024;

const acceptFile = (file) => {
  const lower = (file.name || '').toLowerCase();
  return ALLOWED_EXTS.some(ext => lower.endsWith(ext));
};

const formatBytes = (bytes) => {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`;
};

// Map server status → friendly label + colour
const friendly = {
  queued_for_processing: { label: 'Queued',     color: 'text-on-surface-variant', icon: 'schedule' },
  uploading:             { label: 'Uploading',  color: 'text-primary',            icon: 'cloud_upload' },
  parsing:               { label: 'Parsing',    color: 'text-primary',            icon: 'autorenew' },
  parsed:                { label: 'Parsed',     color: 'text-secondary',          icon: 'check_circle', filled: true },
  extracting:            { label: 'Extracting', color: 'text-primary',            icon: 'autorenew' },
  extracted:             { label: 'Extracted',  color: 'text-secondary',          icon: 'check_circle', filled: true },
  pending_validation:    { label: 'Ready to Validate', color: 'text-secondary',   icon: 'check_circle', filled: true },
  validated:             { label: 'Validated',  color: 'text-secondary',          icon: 'verified',     filled: true },
  rejected:              { label: 'Rejected',   color: 'text-error',              icon: 'cancel',       filled: true },
  failed:                { label: 'Failed',     color: 'text-error',              icon: 'error',        filled: true },
  error:                 { label: 'Failed',     color: 'text-error',              icon: 'error',        filled: true },
};

const isTerminal = (s) => ['parsed', 'extracted', 'pending_validation', 'validated', 'rejected', 'failed', 'error'].includes((s || '').toLowerCase());

/**
 * Drag-and-drop multi-file uploader with per-file status polling.
 * Wires to /api/digitisation/upload (POST) and /api/digitisation/documents/{id} (GET).
 *
 * Props:
 *   onComplete  — called when all files reach a terminal status
 *   onClose     — close button handler (renders an X if provided)
 */
const DigitisationUploader = ({ onComplete, onClose }) => {
  const [files, setFiles] = useState([]); // [{localId, file, status, doc_id, error}]
  const [busy, setBusy]   = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [rejected, setRejected] = useState([]); // [{name, reason}] — files we couldn't accept
  const fileInputRef   = useRef(null);
  const folderInputRef = useRef(null);
  const pollersRef     = useRef({}); // localId → interval handle

  // Stop any running pollers on unmount
  useEffect(() => () => {
    Object.values(pollersRef.current).forEach(handle => clearInterval(handle));
    pollersRef.current = {};
  }, []);

  const addFiles = useCallback((rawList) => {
    const accepted = [];
    const rejects = [];
    // Tell the user WHY a file was skipped instead of silently dropping it. (L4)
    Array.from(rawList || []).forEach(f => {
      if (!acceptFile(f)) {
        rejects.push({ name: f.name, reason: 'unsupported type' });
      } else if (f.size > MAX_BYTES) {
        rejects.push({ name: f.name, reason: `too large (max ${Math.round(MAX_BYTES / 1024 / 1024)}MB)` });
      } else {
        accepted.push({
          localId: `${f.name}-${f.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          file: f,
          name: f.name,
          size: f.size,
          status: 'pending',
          doc_id: null,
          error: null,
        });
      }
    });
    setRejected(rejects);
    if (accepted.length === 0) return;
    setFiles(prev => [...prev, ...accepted]);
  }, []);

  const onFileInput = (e) => addFiles(e.target.files);
  const onFolderInput = (e) => addFiles(e.target.files);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };
  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);

  const removeFile = (localId) => {
    if (pollersRef.current[localId]) {
      clearInterval(pollersRef.current[localId]);
      delete pollersRef.current[localId];
    }
    setFiles(prev => prev.filter(f => f.localId !== localId));
  };

  const clearDone = () => {
    setFiles(prev => prev.filter(f => !isTerminal(f.status)));
  };

  // Begin polling status for a doc until it reaches a terminal state.
  const startPolling = (localId, doc_id) => {
    const tick = async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/digitisation/documents/${doc_id}`);
        const remoteStatus = (res.data?.document?.status || '').toLowerCase();
        setFiles(prev => prev.map(f =>
          f.localId === localId
            ? { ...f, status: remoteStatus, doc_id, error: res.data?.document?.error_message || null }
            : f
        ));
        if (isTerminal(remoteStatus)) {
          clearInterval(pollersRef.current[localId]);
          delete pollersRef.current[localId];
        }
      } catch (err) {
        // Don't kill the poller on transient errors — let the user retry/cancel.
        console.warn('poll error', doc_id, err.message);
      }
    };
    // First tick immediately, then every 4s.
    tick();
    pollersRef.current[localId] = setInterval(tick, 4000);
  };

  const uploadOne = async (entry) => {
    setFiles(prev => prev.map(f => f.localId === entry.localId ? { ...f, status: 'uploading' } : f));
    try {
      const fd = new FormData();
      fd.append('file', entry.file, entry.name);
      const res = await axios.post(`${BACKEND_URL}/api/digitisation/upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const { document_id, status: serverStatus } = res.data;
      setFiles(prev => prev.map(f =>
        f.localId === entry.localId ? { ...f, status: serverStatus, doc_id: document_id } : f
      ));
      startPolling(entry.localId, document_id);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Upload failed';
      setFiles(prev => prev.map(f =>
        f.localId === entry.localId ? { ...f, status: 'error', error: msg } : f
      ));
    }
  };

  const startAll = async () => {
    if (busy) return;
    setBusy(true);
    const pending = files.filter(f => f.status === 'pending');
    // Parallel upload — each becomes its own polling stream.
    await Promise.all(pending.map(uploadOne));
    setBusy(false);
    if (onComplete) onComplete();
  };

  const pendingCount = files.filter(f => f.status === 'pending').length;
  const allTerminal  = files.length > 0 && files.every(f => isTerminal(f.status));

  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-xl">
      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`m-md border-2 border-dashed rounded-xl p-xl flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${
          dragOver ? 'border-primary bg-primary-fixed/30' : 'border-outline-variant hover:border-primary'
        }`}
      >
        <div className="w-16 h-16 bg-primary-fixed text-primary rounded-full flex items-center justify-center mb-md">
          <MIcon name="cloud_upload" className="!text-[40px]" />
        </div>
        <h3 className="font-h3 text-h3 text-on-surface mb-xs">Upload Records</h3>
        <p className="font-body-md text-body-md text-on-surface-variant mb-md max-w-sm">
          Drag & drop PDFs, images, or scans, or click to browse.<br />
          Max {MAX_BYTES / (1024 * 1024)} MB per file.
        </p>
        <div className="flex gap-sm">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
            className="inline-flex items-center gap-base px-md py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 transition-opacity"
          >
            <MIcon name="upload_file" className="!text-[18px]" />
            Browse Files
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); folderInputRef.current?.click(); }}
            className="inline-flex items-center gap-base px-md py-sm bg-surface-container-high text-on-surface-variant rounded-lg font-body-sm font-bold hover:bg-surface-variant transition-colors"
          >
            <MIcon name="folder" className="!text-[18px]" />
            Browse Folder
          </button>
          {onClose && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="inline-flex items-center gap-base px-md py-sm border border-outline-variant text-on-surface-variant rounded-lg font-body-sm font-bold hover:bg-surface-container transition-colors"
            >
              <MIcon name="close" className="!text-[18px]" />
              Close
            </button>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_EXTS.join(',')}
          multiple
          className="hidden"
          onChange={onFileInput}
          onClick={(e) => { e.target.value = null; }}
        />
        <input
          ref={folderInputRef}
          type="file"
          webkitdirectory=""
          directory=""
          multiple
          className="hidden"
          onChange={onFolderInput}
          onClick={(e) => { e.target.value = null; }}
        />
      </div>

      {/* Rejected files — surfaced so the user knows why they were skipped (L4) */}
      {rejected.length > 0 && (
        <div className="px-md py-sm bg-error-container/40 border-t border-error/40">
          <p className="font-body-sm text-body-sm text-error font-semibold mb-1">
            {rejected.length} file{rejected.length === 1 ? '' : 's'} skipped
          </p>
          <ul className="font-body-sm text-body-sm text-on-surface-variant space-y-0.5">
            {rejected.map((r, i) => (
              <li key={`${r.name}-${i}`} className="truncate">{r.name} — {r.reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* File list */}
      {files.length > 0 && (
        <div className="border-t border-outline-variant">
          <div className="px-md py-sm bg-surface-container-low flex items-center justify-between">
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
              {files.length} file{files.length === 1 ? '' : 's'}
              {pendingCount > 0 && ` — ${pendingCount} pending`}
            </span>
            <div className="flex gap-base">
              {pendingCount > 0 && (
                <button
                  onClick={startAll}
                  disabled={busy}
                  className="inline-flex items-center gap-base px-md py-1.5 bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  <MIcon name="play_arrow" className="!text-[18px]" />
                  {busy ? 'Uploading…' : `Upload ${pendingCount}`}
                </button>
              )}
              {allTerminal && (
                <button
                  onClick={clearDone}
                  className="inline-flex items-center gap-base px-md py-1.5 bg-surface-container-high text-on-surface-variant rounded-lg font-body-sm font-bold hover:bg-surface-variant transition-colors"
                >
                  Clear Done
                </button>
              )}
            </div>
          </div>
          <ul className="divide-y divide-outline-variant">
            {files.map((f) => {
              const meta = friendly[(f.status || '').toLowerCase()] || { label: f.status || 'Pending', color: 'text-on-surface-variant', icon: 'description' };
              return (
                <li key={f.localId} className="px-md py-sm flex items-center gap-md">
                  <div className="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center">
                    <MIcon name="picture_as_pdf" className="!text-[22px]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-body-md text-body-md text-on-surface truncate">{f.name}</p>
                    <p className="font-body-sm text-body-sm text-on-surface-variant">
                      {formatBytes(f.size)}
                      {f.error && <span className="ml-base text-error"> · {f.error}</span>}
                    </p>
                  </div>
                  <div className={`inline-flex items-center gap-base font-label-caps text-label-caps uppercase ${meta.color}`}>
                    <MIcon name={meta.icon} className="!text-[18px]" filled={meta.filled} />
                    {meta.label}
                  </div>
                  <button
                    onClick={() => removeFile(f.localId)}
                    className="p-1 rounded-full hover:bg-surface-container text-on-surface-variant"
                    aria-label="Remove"
                  >
                    <MIcon name="close" className="!text-[18px]" />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
};

export default DigitisationUploader;
