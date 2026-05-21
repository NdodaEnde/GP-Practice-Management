/**
 * RiskScoreBadge.jsx
 * Displays an ML risk score as a colored badge with optional detail expansion.
 *
 * Props:
 *   score          {number}  - 0.0 to 1.0
 *   label          {string}  - "low" | "moderate" | "high" | "very_high"
 *   modelName      {string}  - Display name e.g. "Diabetes Risk"
 *   confidence     {number}  - Model confidence (0-1)
 *   factors        {array}   - Contributing factors [{name, value, description}]
 *   disclaimer     {string}  - AI disclaimer text
 *   onExplain      {fn}      - Optional callback for "Explain" click
 *   compact        {bool}    - Compact mode (inline badge only)
 */

import React, { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, Brain, Info } from 'lucide-react';
import './RiskScoreBadge.css';

const RISK_COLORS = {
  low: '#059669',
  moderate: '#D97706',
  high: '#DC2626',
  very_high: '#991B1B',
};

const RISK_BG = {
  low: '#ECFDF5',
  moderate: '#FFFBEB',
  high: '#FEF2F2',
  very_high: '#FEF2F2',
};

const RISK_LABELS = {
  low: 'Low Risk',
  moderate: 'Moderate Risk',
  high: 'High Risk',
  very_high: 'Very High Risk',
};

export default function RiskScoreBadge({
  score,
  label,
  modelName,
  confidence,
  factors = [],
  disclaimer,
  onExplain,
  compact = false,
}) {
  const [expanded, setExpanded] = useState(false);
  const color = RISK_COLORS[label] || '#6B7280';
  const bg = RISK_BG[label] || '#F3F4F6';
  const displayLabel = RISK_LABELS[label] || label;
  const pct = Math.round(score * 100);

  if (compact) {
    return (
      <span
        className="risk-badge-compact"
        style={{ color, backgroundColor: bg, borderColor: color }}
        title={`${modelName}: ${displayLabel} (${pct}%)`}
      >
        <Brain size={10} />
        {displayLabel}
      </span>
    );
  }

  return (
    <div className="risk-badge-card" style={{ borderLeftColor: color }}>
      <div className="risk-badge-header" onClick={() => setExpanded(!expanded)}>
        <div className="risk-badge-title">
          <Brain size={14} style={{ color }} />
          <span className="risk-badge-model">{modelName}</span>
          <span className="risk-badge-ai-tag">AI-assisted</span>
        </div>
        <div className="risk-badge-score-row">
          <div className="risk-badge-meter">
            <div
              className="risk-badge-meter-fill"
              style={{ width: `${pct}%`, backgroundColor: color }}
            />
          </div>
          <span className="risk-badge-label" style={{ color, backgroundColor: bg }}>
            {displayLabel} ({pct}%)
          </span>
          {factors.length > 0 && (
            expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />
          )}
        </div>
      </div>

      {expanded && (
        <div className="risk-badge-details">
          {factors.length > 0 && (
            <div className="risk-badge-factors">
              <span className="risk-badge-factors-title">Contributing Factors:</span>
              <ul>
                {factors.map((f, i) => (
                  <li key={i}>
                    <strong>{f.name}</strong>: {typeof f.value === 'number' ? f.value : String(f.value)}
                    {f.description && <span className="risk-factor-desc"> — {f.description}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {confidence && (
            <div className="risk-badge-confidence">
              Model confidence: {Math.round(confidence * 100)}%
            </div>
          )}
          <div className="risk-badge-disclaimer">
            <Info size={10} />
            {disclaimer || 'AI-assisted risk assessment. Clinical correlation required.'}
          </div>
        </div>
      )}
    </div>
  );
}
