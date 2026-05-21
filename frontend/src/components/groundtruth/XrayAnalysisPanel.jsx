import React, { useState, useCallback } from 'react';
import api from './api';
import { Upload, Loader, AlertTriangle, CheckCircle, Image, Brain } from 'lucide-react';
import './XrayAnalysisPanel.css';

const API_BASE = '/api';

const SEVERITY = {
  high:   { color: '#DC2626', bg: '#FEF2F2', label: 'High' },
  medium: { color: '#EA580C', bg: '#FFF7ED', label: 'Moderate' },
  low:    { color: '#16A34A', bg: '#F0FDF4', label: 'Low' },
};

function getSeverity(prob) {
  if (prob >= 0.5) return SEVERITY.high;
  if (prob >= 0.2) return SEVERITY.medium;
  return SEVERITY.low;
}

export default function XrayAnalysisPanel() {
  const [file, setFile]         = useState(null);
  const [preview, setPreview]   = useState(null);
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState('');
  const [statusMsg, setStatus]  = useState(null);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0] || e.target?.files?.[0];
    if (!f) return;
    if (!f.type.startsWith('image/')) {
      setError('Please upload a PNG or JPEG image');
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
    setError('');
  }, []);

  async function analyze() {
    if (!file) return;
    setLoading(true);
    setError('');
    setResult(null);

    try {
      // Check model status first
      setStatus('Checking model availability...');
      const statusRes = await api.get(`${API_BASE}/ml/imaging/xray/status`);
      if (!statusRes.data.available) {
        setError(statusRes.data.error || 'X-ray model not available');
        setLoading(false);
        setStatus(null);
        return;
      }

      // Upload and analyze
      setStatus('Analyzing X-ray...');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('generate_heatmap', 'true');
      formData.append('top_n', '5');

      const res = await api.post(`${API_BASE}/ml/imaging/xray/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: { generate_heatmap: true, top_n: 5 },
      });

      setResult(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Analysis failed';
      setError(msg);
    } finally {
      setLoading(false);
      setStatus(null);
    }
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError('');
  }

  return (
    <div className="xray-panel">
      <div className="xray-panel-header">
        <Brain size={16} />
        <span>Chest X-ray Analysis</span>
        <span className="xray-model-tag">DenseNet121</span>
      </div>

      {/* Upload zone */}
      {!file && (
        <div
          className="xray-dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
        >
          <Upload size={28} color="#9CA3AF" />
          <p>Drop chest X-ray image here</p>
          <span>PNG or JPEG format</span>
          <label className="xray-browse-btn">
            Browse Files
            <input type="file" accept="image/*" onChange={onDrop} hidden />
          </label>
        </div>
      )}

      {/* Preview + actions */}
      {file && !result && (
        <div className="xray-preview-zone">
          <div className="xray-preview-img">
            <img src={preview} alt="X-ray preview" />
          </div>
          <div className="xray-preview-info">
            <span className="xray-filename">{file.name}</span>
            <span className="xray-filesize">{(file.size / 1024).toFixed(0)} KB</span>
          </div>
          <div className="xray-preview-actions">
            <button className="xray-btn-analyze" onClick={analyze} disabled={loading}>
              {loading ? <><Loader size={14} className="xray-spin" /> {statusMsg}</> : <><Image size={14} /> Analyze X-ray</>}
            </button>
            <button className="xray-btn-reset" onClick={reset} disabled={loading}>Change Image</button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="xray-error">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="xray-results">

          {/* Images row: original + heatmap */}
          <div className="xray-images-row">
            <div className="xray-img-card">
              <div className="xray-img-label">Original</div>
              <img src={preview} alt="Original X-ray" />
            </div>
            {result.heatmap && (
              <div className="xray-img-card">
                <div className="xray-img-label">GradCAM — {result.heatmap_pathology}</div>
                <img src={`data:image/png;base64,${result.heatmap}`} alt="GradCAM heatmap" />
              </div>
            )}
          </div>

          {/* Findings */}
          <div className="xray-findings">
            <h4>Top Findings</h4>
            {(result.top_findings || []).map((f) => {
              const sev = getSeverity(f.probability);
              const pct = (f.probability * 100).toFixed(1);
              return (
                <div key={f.pathology} className="xray-finding-row">
                  <span className="xray-finding-name">{f.pathology.replace('_', ' ')}</span>
                  <div className="xray-finding-bar-track">
                    <div className="xray-finding-bar" style={{ width: `${pct}%`, background: sev.color }} />
                  </div>
                  <span className="xray-finding-pct" style={{ color: sev.color }}>{pct}%</span>
                </div>
              );
            })}
          </div>

          {/* All 14 pathologies */}
          <details className="xray-all-details">
            <summary>All 14 Pathologies</summary>
            <div className="xray-all-grid">
              {Object.entries(result.all_predictions || {})
                .sort(([, a], [, b]) => b - a)
                .map(([label, prob]) => {
                  const sev = getSeverity(prob);
                  return (
                    <div key={label} className="xray-all-item">
                      <span className="xray-all-dot" style={{ background: sev.color }} />
                      <span className="xray-all-name">{label.replace('_', ' ')}</span>
                      <span className="xray-all-prob" style={{ color: sev.color }}>{(prob * 100).toFixed(1)}%</span>
                    </div>
                  );
                })}
            </div>
          </details>

          {/* Disclaimer */}
          <div className="xray-disclaimer">
            {result.disclaimer}
          </div>

          <button className="xray-btn-reset" onClick={reset} style={{ marginTop: 12 }}>Analyze Another Image</button>
        </div>
      )}
    </div>
  );
}
