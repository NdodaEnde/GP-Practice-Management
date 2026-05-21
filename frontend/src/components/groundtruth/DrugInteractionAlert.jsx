/**
 * DrugInteractionAlert.jsx
 * Displays drug-drug interaction warnings from the ML API.
 *
 * Props:
 *   interactions   {array}   - [{drug_a, drug_b, severity, effect, recommendation}]
 *   loading        {bool}    - Loading state
 *   disclaimer     {string}  - Disclaimer text
 */

import React, { useState } from 'react';
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, Shield } from 'lucide-react';
import './DrugInteractionAlert.css';

const SEVERITY_CONFIG = {
  major: { color: '#DC2626', bg: '#FEF2F2', icon: AlertTriangle, label: 'Major' },
  moderate: { color: '#D97706', bg: '#FFFBEB', icon: AlertCircle, label: 'Moderate' },
  minor: { color: '#059669', bg: '#ECFDF5', icon: Info, label: 'Minor' },
};

export default function DrugInteractionAlert({ interactions = [], loading = false, disclaimer }) {
  const [expandedIdx, setExpandedIdx] = useState(null);

  if (loading) {
    return (
      <div className="dia-container dia-loading">
        <Shield size={14} className="spinning-tiny" />
        Checking drug interactions...
      </div>
    );
  }

  if (interactions.length === 0) {
    return (
      <div className="dia-container dia-clear">
        <Shield size={14} color="#059669" />
        <span>No known drug interactions detected</span>
        <span className="dia-ai-tag">AI-assisted</span>
      </div>
    );
  }

  const majorCount = interactions.filter(i => i.severity === 'major').length;

  return (
    <div className="dia-container">
      <div className="dia-header">
        <AlertTriangle size={14} color="#DC2626" />
        <span className="dia-header-text">
          {interactions.length} interaction{interactions.length > 1 ? 's' : ''} found
          {majorCount > 0 && <span className="dia-major-count"> ({majorCount} major)</span>}
        </span>
        <span className="dia-ai-tag">AI-assisted</span>
      </div>

      <div className="dia-list">
        {interactions.map((interaction, idx) => {
          const config = SEVERITY_CONFIG[interaction.severity] || SEVERITY_CONFIG.minor;
          const Icon = config.icon;
          const isExpanded = expandedIdx === idx;

          return (
            <div
              key={idx}
              className="dia-item"
              style={{ borderLeftColor: config.color }}
            >
              <div
                className="dia-item-header"
                onClick={() => setExpandedIdx(isExpanded ? null : idx)}
              >
                <Icon size={12} color={config.color} />
                <span className="dia-drugs">
                  {interaction.drug_a} + {interaction.drug_b}
                </span>
                <span
                  className="dia-severity"
                  style={{ color: config.color, backgroundColor: config.bg }}
                >
                  {config.label}
                </span>
                {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </div>

              {isExpanded && (
                <div className="dia-item-details">
                  <div className="dia-effect">
                    <strong>Effect:</strong> {interaction.effect}
                  </div>
                  <div className="dia-recommendation">
                    <strong>Recommendation:</strong> {interaction.recommendation}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="dia-disclaimer">
        <Info size={10} />
        {disclaimer || 'Based on known interaction database. Verify with current formulary.'}
      </div>
    </div>
  );
}
