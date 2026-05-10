import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';
const API_BASE = `${BACKEND_URL}/api/digitisation/fhir/connections`;

const MIcon = ({ name, className = '', filled = false }) => (
  <span
    className={`material-symbols-outlined ${className}`}
    style={filled ? { fontVariationSettings: "'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24" } : undefined}
    aria-hidden="true"
  >
    {name}
  </span>
);

// Wizard steps. Phase A only implements step 1 (Connection Details);
// steps 2-4 render an explainer card so users know what's coming.
const STEPS = [
  { id: 1, title: 'Connection Details',  shortName: 'STEP 01', subtitle: 'Name, FHIR URL, environment' },
  { id: 2, title: 'Authentication',       shortName: 'STEP 02', subtitle: 'Phase B' },
  { id: 3, title: 'Resource Mapping',     shortName: 'STEP 03', subtitle: 'Phase B' },
  { id: 4, title: 'Test & Save',          shortName: 'STEP 04', subtitle: 'Phase B' },
];

const ENV_OPTIONS = [
  { value: 'sandbox',    icon: 'science', label: 'Sandbox' },
  { value: 'staging',    icon: 'rule',    label: 'Staging' },
  { value: 'production', icon: 'bolt',    label: 'Production' },
];

const AUTH_METHOD_LABEL = {
  none:                       'No authentication',
  basic:                      'HTTP Basic',
  bearer:                     'Bearer token',
  oauth2_client_credentials:  'OAuth2 (client credentials)',
  smart_on_fhir:              'SMART on FHIR',
};

const DigitisationFHIRConnectionWizard = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [connections, setConnections] = useState([]);
  const [listLoading, setListLoading] = useState(true);

  // Step 1 form state
  const [name, setName]               = useState('');
  const [fhirUrl, setFhirUrl]         = useState('');
  const [environment, setEnvironment] = useState('sandbox');
  const [isDefault, setIsDefault]     = useState(false);
  const [saving, setSaving]           = useState(false);
  const [err, setErr]                 = useState(null);

  const loadConnections = async () => {
    setListLoading(true);
    try {
      const res = await axios.get(API_BASE);
      setConnections(res.data.connections || []);
    } catch (e) {
      console.error('FHIR connections load failed', e);
    } finally {
      setListLoading(false);
    }
  };

  useEffect(() => { loadConnections(); }, []);

  const reset = () => {
    setName(''); setFhirUrl(''); setEnvironment('sandbox'); setIsDefault(false);
    setErr(null);
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      await axios.post(API_BASE, {
        name,
        fhir_url:    fhirUrl,
        environment,
        is_default:  isDefault,
        auth_method: 'none', // Phase A
      });
      await loadConnections();
      reset();
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message || 'Failed to save connection');
    } finally {
      setSaving(false);
    }
  };

  const setDefault = async (id) => {
    try {
      await axios.patch(`${API_BASE}/${id}`, { is_default: true });
      await loadConnections();
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this connection?')) return;
    try {
      await axios.delete(`${API_BASE}/${id}`);
      await loadConnections();
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    }
  };

  return (
    <div className="max-w-[1200px] mx-auto space-y-lg">
      {/* Header */}
      <section className="flex items-end justify-between gap-md flex-wrap">
        <div>
          <h1 className="font-h1 text-h1 text-on-surface">FHIR Connection Wizard</h1>
          <p className="font-body-md text-body-md text-on-surface-variant mt-xs">
            Configure where validated records get pushed when you trigger an export.
          </p>
        </div>
        <Link
          to="/digitisation/export"
          className="inline-flex items-center gap-base px-md py-sm bg-surface-container-lowest border border-outline text-on-surface rounded-lg font-body-sm font-bold hover:bg-surface-container transition-colors"
        >
          <MIcon name="arrow_back" className="!text-[18px]" />
          Back to Export Centre
        </Link>
      </section>

      {/* Phase-A banner */}
      <div className="bg-tertiary-fixed text-on-tertiary-fixed-variant rounded-lg px-md py-sm font-body-sm">
        <div className="flex items-start gap-sm">
          <MIcon name="info" className="!text-[18px] mt-0.5" />
          <p>
            <strong>Phase A:</strong> connection metadata only — name, URL, and environment
            are saved and used by the Export Centre. Real authentication, resource mapping,
            and connection testing land in Phase B.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-lg">
        {/* Step rail */}
        <aside className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex flex-col gap-lg h-fit">
          <div>
            <h2 className="font-h3 text-h3 text-primary mb-xs">FHIR Setup</h2>
            <p className="font-body-sm text-on-surface-variant">Configure your healthcare data interoperability bridge.</p>
          </div>
          <div className="flex flex-col gap-lg">
            {STEPS.map((s) => {
              const active = s.id === step;
              const enabled = s.id === 1;
              return (
                <button
                  key={s.id}
                  onClick={() => enabled && setStep(s.id)}
                  disabled={!enabled}
                  className={`flex items-center gap-md text-left ${enabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}`}
                >
                  <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold ${
                    active ? 'border-primary text-primary font-bold' : 'border-outline-variant text-on-surface-variant'
                  }`}>{s.id}</div>
                  <div className="flex flex-col">
                    <span className={`font-label-caps text-label-caps ${active ? 'text-primary' : 'text-outline'}`}>{s.shortName}</span>
                    <span className={`font-body-sm ${active ? 'text-on-surface font-semibold' : 'text-on-surface-variant'}`}>
                      {s.title}
                    </span>
                    {!enabled && <span className="text-[10px] uppercase text-outline mt-0.5">{s.subtitle}</span>}
                  </div>
                </button>
              );
            })}
          </div>
          <div className="pt-lg border-t border-outline-variant flex items-start gap-sm">
            <MIcon name="verified_user" className="text-secondary !text-[16px]" filled />
            <div>
              <p className="font-label-caps text-[10px] uppercase text-secondary">Compliance Guaranteed</p>
              <p className="text-[11px] text-on-surface-variant leading-tight">
                TLS encryption end-to-end. Compliant with POPIA and HIPAA when paired with a properly authenticated Phase B endpoint.
              </p>
            </div>
          </div>
        </aside>

        {/* Step content */}
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex flex-col gap-lg">
          {step === 1 && (
            <>
              <h2 className="font-h2 text-h2 text-on-surface">Connection Details</h2>

              <div className="flex flex-col gap-md">
                <label className="flex flex-col gap-xs">
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Connection Name</span>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., TrakCare Cape Town Clinic"
                    className="px-md py-sm rounded-lg border border-outline focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all font-body-md"
                  />
                </label>

                <label className="flex flex-col gap-xs">
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">FHIR Server URL</span>
                  <div className="relative">
                    <span className="absolute left-md top-1/2 -translate-y-1/2 text-outline">
                      <MIcon name="link" className="!text-[20px]" />
                    </span>
                    <input
                      type="url"
                      value={fhirUrl}
                      onChange={(e) => setFhirUrl(e.target.value)}
                      placeholder="https://endpoint.health/fhir"
                      className="w-full pl-xl pr-md py-sm rounded-lg border border-outline focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all font-body-md"
                    />
                  </div>
                </label>

                <div className="flex flex-col gap-xs">
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Environment</span>
                  <div className="grid grid-cols-3 gap-sm">
                    {ENV_OPTIONS.map((opt) => {
                      const active = environment === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setEnvironment(opt.value)}
                          className={`p-sm rounded-lg flex flex-col items-center gap-xs transition-colors ${
                            active
                              ? 'border-2 border-primary bg-primary-fixed/30'
                              : 'border border-outline-variant hover:border-primary'
                          }`}
                        >
                          <MIcon name={opt.icon} className={`!text-[22px] ${active ? 'text-primary' : 'text-outline'}`} />
                          <span className={`font-label-caps text-[10px] ${active ? 'text-primary' : 'text-outline'}`}>{opt.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <label className="flex items-center gap-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isDefault}
                    onChange={(e) => setIsDefault(e.target.checked)}
                    className="w-4 h-4 accent-primary"
                  />
                  <span className="font-body-sm text-on-surface">Make this the default connection for this workspace</span>
                </label>
              </div>

              {err && (
                <div className="bg-error-container text-on-error-container px-md py-sm rounded-lg font-body-sm">
                  {err}
                </div>
              )}

              <div className="flex justify-between items-center pt-md border-t border-outline-variant">
                <button
                  onClick={() => navigate('/digitisation/export')}
                  className="px-lg py-sm font-body-md font-semibold text-outline hover:text-on-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={save}
                  disabled={saving || !name.trim() || !fhirUrl.trim()}
                  className="px-lg py-sm bg-primary text-on-primary rounded-lg font-body-md font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-sm"
                >
                  {saving ? 'Saving…' : 'Save connection'}
                  <MIcon name={saving ? 'progress_activity' : 'check'} className={`!text-[18px] ${saving ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </>
          )}

          {step !== 1 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center gap-md py-xl">
              <MIcon name="construction" className="text-outline !text-[48px]" />
              <h3 className="font-h3 text-h3 text-on-surface">{STEPS.find(s => s.id === step)?.title}</h3>
              <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
                Phase B work — not yet implemented. The schema supports it; the UI flow lands once Phase B's auth + bundle worker ships.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Saved connections list */}
      <section className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden">
        <div className="px-lg py-md border-b border-outline-variant flex items-center justify-between">
          <h3 className="font-h3 text-h3 text-on-surface">Saved Connections</h3>
          <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">{connections.length} total</span>
        </div>
        <table className="w-full text-left border-collapse">
          <thead className="bg-surface-container-low">
            <tr>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Name</th>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">FHIR URL</th>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Env</th>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Auth</th>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Default</th>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {listLoading && (
              <tr><td colSpan={6} className="px-lg py-xl text-center text-on-surface-variant">Loading connections…</td></tr>
            )}
            {!listLoading && connections.length === 0 && (
              <tr>
                <td colSpan={6} className="px-lg py-xl text-center font-body-md text-on-surface-variant">
                  No FHIR connections saved yet. Use Step 1 above to add one.
                </td>
              </tr>
            )}
            {!listLoading && connections.map((c) => (
              <tr key={c.id} className="hover:bg-surface-container-low transition-colors">
                <td className="px-lg py-md font-body-md font-medium text-on-surface">{c.name}</td>
                <td className="px-lg py-md font-data-tabular font-body-sm text-on-surface-variant truncate max-w-[280px]" title={c.fhir_url}>
                  {c.fhir_url}
                </td>
                <td className="px-lg py-md">
                  <span className="bg-surface-container-high px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase text-on-surface-variant">
                    {c.environment}
                  </span>
                </td>
                <td className="px-lg py-md font-body-sm text-on-surface-variant">{AUTH_METHOD_LABEL[c.auth_method] || c.auth_method}</td>
                <td className="px-lg py-md">
                  {c.is_default ? (
                    <span className="inline-flex items-center gap-1 text-secondary font-label-caps text-label-caps uppercase">
                      <MIcon name="check_circle" className="!text-[16px]" filled />
                      Default
                    </span>
                  ) : (
                    <button onClick={() => setDefault(c.id)} className="text-primary font-body-sm font-semibold hover:underline">
                      Set default
                    </button>
                  )}
                </td>
                <td className="px-lg py-md text-right">
                  <button
                    onClick={() => remove(c.id)}
                    className="text-error font-body-sm font-semibold hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
};

export default DigitisationFHIRConnectionWizard;
