/**
 * LabAnomalyTable.jsx
 * Displays lab results with anomaly highlighting from ML API.
 *
 * Props:
 *   results        {array}   - [{test_name, value, flag, severity, message, reference_range}]
 *   loading        {bool}    - Loading state
 *   disclaimer     {string}  - Disclaimer text
 */

import React from 'react';
import { AlertTriangle, AlertCircle, CheckCircle, HelpCircle, Info, FlaskConical } from 'lucide-react';
import './LabAnomalyTable.css';

const FLAG_CONFIG = {
  critical_low: { color: '#991B1B', bg: '#FEE2E2', icon: AlertTriangle, label: 'Critical Low' },
  critical_high: { color: '#991B1B', bg: '#FEE2E2', icon: AlertTriangle, label: 'Critical High' },
  low: { color: '#D97706', bg: '#FEF3C7', icon: AlertCircle, label: 'Low' },
  high: { color: '#D97706', bg: '#FEF3C7', icon: AlertCircle, label: 'High' },
  normal: { color: '#059669', bg: '#ECFDF5', icon: CheckCircle, label: 'Normal' },
  unknown: { color: '#6B7280', bg: '#F3F4F6', icon: HelpCircle, label: 'Unknown' },
};

export default function LabAnomalyTable({ results = [], loading = false, disclaimer }) {
  if (loading) {
    return (
      <div className="lab-anomaly-loading">
        <FlaskConical size={14} className="spinning-tiny" />
        Checking lab results against reference ranges...
      </div>
    );
  }

  if (results.length === 0) return null;

  const anomalyCount = results.filter(r => r.severity === 'abnormal' || r.severity === 'critical').length;
  const criticalCount = results.filter(r => r.severity === 'critical').length;

  return (
    <div className="lab-anomaly-container">
      <div className="lab-anomaly-header">
        <FlaskConical size={14} color="#4F46E5" />
        <span className="lab-anomaly-title">
          Lab Analysis: {results.length} tests checked
          {anomalyCount > 0 && (
            <span className="lab-anomaly-count" style={{ color: criticalCount > 0 ? '#991B1B' : '#D97706' }}>
              {' '}({anomalyCount} abnormal{criticalCount > 0 ? `, ${criticalCount} critical` : ''})
            </span>
          )}
        </span>
        <span className="lab-anomaly-ai-tag">AI-assisted</span>
      </div>

      <table className="lab-anomaly-table">
        <thead>
          <tr>
            <th>Test</th>
            <th>Value</th>
            <th>Reference</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, idx) => {
            const config = FLAG_CONFIG[result.flag] || FLAG_CONFIG.unknown;
            const Icon = config.icon;
            return (
              <tr key={idx} className={`lab-row-${result.severity}`}>
                <td className="lab-test-name">{result.test_name}</td>
                <td className="lab-value" style={{ color: config.color, fontWeight: result.severity !== 'normal' ? 600 : 400 }}>
                  {result.value}
                </td>
                <td className="lab-ref">{result.reference_range}</td>
                <td>
                  <span className="lab-flag" style={{ color: config.color, backgroundColor: config.bg }}>
                    <Icon size={10} />
                    {config.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="lab-anomaly-disclaimer">
        <Info size={10} />
        {disclaimer || 'AI-assisted risk assessment. Clinical correlation required.'}
      </div>
    </div>
  );
}
