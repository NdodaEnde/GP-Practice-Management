/**
 * PatientMatchModal — confirms which patient an approval should promote
 * the validated extractions onto. Shows up between clicking Approve and
 * the actual /approve commit when the backend's matcher finds 1+
 * candidates. Reviewer picks an existing patient OR creates a new one.
 *
 * Backend contract: receives candidates from /preview-match (or from a
 * 409 from /approve). Calls /approve with confirmed_patient_id or
 * create_new_patient=true.
 */

import React, { useState } from 'react';

const formatDob = (dob) => {
  if (!dob) return '—';
  // patients.dob is TEXT — could be ISO or any format. Print as-is.
  return String(dob).slice(0, 10);
};

const KIND_LABEL = {
  id_number: { label: 'SA ID match', color: '#15803d', desc: 'Same SA ID number — high confidence.' },
  name_dob:  { label: 'Name + DOB',  color: '#a16207', desc: 'Same surname + DOB — verify before confirming (twins, family).' },
};

export default function PatientMatchModal({
  open,
  busy,
  candidates,
  demographics,        // { full_names, surname, id_number, date_of_birth }
  onUseExisting,       // (patient_id) => void
  onCreateNew,         // () => void
  onCancel,            // () => void
}) {
  const [selectedId, setSelectedId] = useState(null);

  if (!open) return null;

  const submit = () => {
    if (selectedId === '__new__') {
      onCreateNew();
    } else if (selectedId) {
      onUseExisting(selectedId);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60,
        padding: 16,
      }}
    >
      <div
        style={{
          width: '100%', maxWidth: 720, background: 'white', borderRadius: 12,
          boxShadow: '0 20px 50px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column',
          maxHeight: '90vh',
        }}
      >
        <header style={{ padding: '16px 20px', borderBottom: '1px solid #e5e7eb' }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#111827' }}>
            Which patient is this for?
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#4b5563' }}>
            We found existing patients matching this document. Pick the right one before approving.
          </p>
        </header>

        {/* Source demographics */}
        <div style={{
          padding: '12px 20px', background: '#fff7ed', borderBottom: '1px solid #fed7aa', fontSize: 13,
        }}>
          <div style={{ fontWeight: 600, color: '#9a3412', marginBottom: 4 }}>Document says</div>
          <div style={{ color: '#374151', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px' }}>
            <div><span style={{ color: '#6b7280' }}>Name:</span> {demographics?.full_names || '—'} {demographics?.surname || ''}</div>
            <div><span style={{ color: '#6b7280' }}>DOB:</span> {formatDob(demographics?.date_of_birth)}</div>
            <div style={{ gridColumn: '1 / -1' }}>
              <span style={{ color: '#6b7280' }}>SA ID:</span>{' '}
              <span style={{ fontFamily: 'monospace' }}>{demographics?.id_number || '—'}</span>
            </div>
          </div>
        </div>

        {/* Candidates */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(candidates || []).map((c) => {
              const meta = KIND_LABEL[c.match_kind] || { label: 'MATCH', color: '#6b7280', desc: '' };
              const selected = selectedId === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  style={{
                    textAlign: 'left',
                    padding: 12,
                    border: `2px solid ${selected ? meta.color : '#e5e7eb'}`,
                    borderRadius: 8,
                    background: selected ? '#f0fdf4' : 'white',
                    cursor: 'pointer',
                    transition: 'border 120ms',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 15, fontWeight: 600, color: '#111827' }}>
                        {[c.first_name, c.last_name].filter(Boolean).join(' ') || '(unnamed)'}
                      </div>
                      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                        DOB {formatDob(c.dob)}{c.id_number ? ` · SA ID ${c.id_number}` : ''}
                      </div>
                      {c.medical_aid && (
                        <div style={{ fontSize: 12, color: '#6b7280' }}>
                          {c.medical_aid}
                        </div>
                      )}
                    </div>
                    <span style={{
                      fontSize: 10, fontWeight: 700, letterSpacing: '0.04em',
                      color: meta.color, padding: '3px 7px',
                      background: 'white', border: `1px solid ${meta.color}`,
                      borderRadius: 4, whiteSpace: 'nowrap',
                    }}>{meta.label}</span>
                  </div>
                  <div style={{ fontSize: 11, color: meta.color, marginTop: 6, fontStyle: 'italic' }}>
                    {meta.desc}
                  </div>
                </button>
              );
            })}

            {/* Create-new option always last */}
            <button
              onClick={() => setSelectedId('__new__')}
              style={{
                textAlign: 'left',
                padding: 12,
                border: `2px dashed ${selectedId === '__new__' ? '#0ea5e9' : '#cbd5e1'}`,
                borderRadius: 8,
                background: selectedId === '__new__' ? '#f0f9ff' : '#f8fafc',
                cursor: 'pointer',
                transition: 'border 120ms',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 600, color: '#0c4a6e' }}>
                None of these — create a new patient
              </div>
              <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>
                A fresh patient record will be created with the demographics above.
              </div>
            </button>
          </div>
        </div>

        <footer style={{
          padding: '12px 20px', borderTop: '1px solid #e5e7eb',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12,
        }}>
          <button
            onClick={onCancel}
            disabled={busy}
            style={{
              padding: '8px 16px', fontSize: 13, fontWeight: 500, color: '#374151',
              background: 'transparent', border: 'none', cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1,
            }}
          >Cancel</button>
          <button
            onClick={submit}
            disabled={!selectedId || busy}
            style={{
              padding: '8px 18px', fontSize: 13, fontWeight: 600, color: 'white',
              background: '#0d9488', border: 'none', borderRadius: 6,
              cursor: (!selectedId || busy) ? 'not-allowed' : 'pointer',
              opacity: (!selectedId || busy) ? 0.5 : 1,
            }}
          >
            {busy ? 'Approving…' : (selectedId === '__new__' ? 'Create new + Approve' : 'Use selected + Approve')}
          </button>
        </footer>
      </div>
    </div>
  );
}
