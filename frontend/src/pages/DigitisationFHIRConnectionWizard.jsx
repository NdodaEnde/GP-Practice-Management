import React, { useEffect, useMemo, useState } from 'react';
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

const STEPS = [
  { id: 1, title: 'Connection Details',  shortName: 'STEP 01' },
  { id: 2, title: 'Authentication',       shortName: 'STEP 02' },
  { id: 3, title: 'Resource Mapping',     shortName: 'STEP 03' },
  { id: 4, title: 'Test & Save',          shortName: 'STEP 04' },
];

const ENV_OPTIONS = [
  { value: 'sandbox',    icon: 'science', label: 'Sandbox' },
  { value: 'staging',    icon: 'rule',    label: 'Staging' },
  { value: 'production', icon: 'bolt',    label: 'Production' },
];

const AUTH_METHOD_OPTIONS = [
  { value: 'none',                      label: 'No authentication',           note: 'Public test endpoints (e.g. HAPI public sandbox).' },
  { value: 'bearer',                    label: 'Bearer token',                note: 'Long-lived token included in Authorization header.' },
  { value: 'basic',                     label: 'HTTP Basic',                  note: 'Phase C — credential storage in Vault.', disabled: true },
  { value: 'oauth2_client_credentials', label: 'OAuth2 client credentials',   note: 'Phase C — token exchange flow.', disabled: true },
  { value: 'smart_on_fhir',             label: 'SMART on FHIR',               note: 'Phase C — full SMART app launch.',  disabled: true },
];

const AUTH_METHOD_LABEL = AUTH_METHOD_OPTIONS.reduce((acc, o) => ({ ...acc, [o.value]: o.label }), {});

const RESOURCE_OPTIONS = [
  { key: 'patient',     label: 'Patient',           note: 'Demographics + identifiers (always included).', locked: true  },
  { key: 'allergies',   label: 'Allergies',         note: 'AllergyIntolerance per known allergy.',          locked: false },
  { key: 'diagnoses',   label: 'Diagnoses',         note: 'Condition per ICD-10 entry.',                    locked: false },
  { key: 'medications', label: 'Medications',       note: 'MedicationStatement per drug.',                  locked: false },
  { key: 'vitals',      label: 'Vitals',            note: 'Observation per measurement (LOINC-coded).',     locked: false },
  { key: 'encounters',  label: 'Encounters',        note: 'Encounter per consultation note.',                locked: false },
];

const DEFAULT_RESOURCE_FLAGS = RESOURCE_OPTIONS.reduce((acc, o) => ({ ...acc, [o.key]: true }), {});

const DigitisationFHIRConnectionWizard = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [connections, setConnections] = useState([]);
  const [listLoading, setListLoading] = useState(true);

  // Wizard form state — collected across steps, committed at Step 04.
  const [name, setName]                         = useState('');
  const [fhirUrl, setFhirUrl]                   = useState('');
  const [environment, setEnvironment]           = useState('sandbox');
  const [authMethod, setAuthMethod]             = useState('none');
  const [bearerToken, setBearerToken]           = useState('');
  const [resourceFlags, setResourceFlags]       = useState(DEFAULT_RESOURCE_FLAGS);
  const [isDefault, setIsDefault]               = useState(false);

  // Test & Save state
  const [savedConnId, setSavedConnId]           = useState(null);
  const [testing, setTesting]                   = useState(false);
  const [testResult, setTestResult]             = useState(null);   // { ok, error, tested_at, metadata_url }
  const [saving, setSaving]                     = useState(false);
  const [err, setErr]                           = useState(null);

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
    setName(''); setFhirUrl(''); setEnvironment('sandbox');
    setAuthMethod('none'); setBearerToken('');
    setResourceFlags(DEFAULT_RESOURCE_FLAGS);
    setIsDefault(false); setSavedConnId(null); setTestResult(null);
    setErr(null); setStep(1);
  };

  // Step 1 → 2 → 3 → 4 navigation gates
  const step1Valid = name.trim() && /^https?:\/\//i.test(fhirUrl.trim());
  const step2Valid = authMethod === 'none' || (authMethod === 'bearer' && bearerToken.trim());
  const step3Valid = true;

  const goNext = () => {
    if (step === 1 && !step1Valid) { setErr('Connection name and a valid http(s) URL are required.'); return; }
    if (step === 2 && !step2Valid) { setErr('Bearer token is required for that auth method.'); return; }
    setErr(null);
    setStep((s) => Math.min(s + 1, 4));
  };
  const goBack = () => { setErr(null); setStep((s) => Math.max(s - 1, 1)); };

  // Persist the connection. Called on entering Step 4 the first time so the
  // user has a row they can test. Subsequent saves PATCH the same row.
  const persistConnection = async () => {
    setSaving(true); setErr(null);
    try {
      const metadata = {
        resource_mapping: resourceFlags,
        ...(authMethod === 'bearer' && bearerToken
          ? { credentials: { token: bearerToken } }
          : {}),
      };
      const body = {
        name:         name.trim(),
        fhir_url:     fhirUrl.trim(),
        environment,
        auth_method:  authMethod,
        is_default:   isDefault,
        metadata,
      };
      let conn;
      if (savedConnId) {
        const res = await axios.patch(`${API_BASE}/${savedConnId}`, body);
        conn = res.data.connection;
      } else {
        const res = await axios.post(API_BASE, body);
        conn = res.data.connection;
        setSavedConnId(conn.id);
      }
      await loadConnections();
      return conn;
    } catch (e) {
      const detail = e?.response?.data?.detail || e.message;
      setErr(detail);
      throw e;
    } finally {
      setSaving(false);
    }
  };

  const runTest = async () => {
    if (!savedConnId) {
      try {
        await persistConnection();
      } catch { return; }
    }
    setTesting(true); setTestResult(null);
    try {
      const res = await axios.post(`${API_BASE}/${savedConnId}/test`);
      setTestResult(res.data);
    } catch (e) {
      setTestResult({ ok: false, error: e?.response?.data?.detail || e.message });
    } finally {
      setTesting(false);
      await loadConnections();
    }
  };

  // Used on the saved-connections list (one-click re-test)
  const reTest = async (id) => {
    try {
      await axios.post(`${API_BASE}/${id}/test`);
      await loadConnections();
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    }
  };

  const setDefault = async (id) => {
    try {
      await axios.patch(`${API_BASE}/${id}`, { is_default: true });
      await loadConnections();
    } catch (e) { setErr(e?.response?.data?.detail || e.message); }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this connection?')) return;
    try {
      await axios.delete(`${API_BASE}/${id}`);
      await loadConnections();
    } catch (e) { setErr(e?.response?.data?.detail || e.message); }
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
              const reached = s.id <= step;
              return (
                <button
                  key={s.id}
                  onClick={() => reached && setStep(s.id)}
                  disabled={!reached}
                  className={`flex items-center gap-md text-left ${reached ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}`}
                >
                  <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold ${
                    active ? 'border-primary text-primary' : reached ? 'border-secondary text-secondary' : 'border-outline-variant text-outline'
                  }`}>{reached && !active ? <MIcon name="check" className="!text-[16px]" /> : s.id}</div>
                  <div className="flex flex-col">
                    <span className={`font-label-caps text-label-caps ${active ? 'text-primary' : reached ? 'text-secondary' : 'text-outline'}`}>{s.shortName}</span>
                    <span className={`font-body-sm ${active ? 'text-on-surface font-semibold' : 'text-on-surface-variant'}`}>{s.title}</span>
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
                TLS encryption end-to-end. POPIA + HIPAA compatible when paired with a properly authenticated endpoint.
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
                  <span className="font-body-sm text-on-surface-variant">No trailing slash. The wizard will probe <code>{(fhirUrl || 'YOUR_URL').replace(/\/+$/, '')}/metadata</code> when you reach Step 04.</span>
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
                            active ? 'border-2 border-primary bg-primary-fixed/30' : 'border border-outline-variant hover:border-primary'
                          }`}
                        >
                          <MIcon name={opt.icon} className={`!text-[22px] ${active ? 'text-primary' : 'text-outline'}`} />
                          <span className={`font-label-caps text-[10px] ${active ? 'text-primary' : 'text-outline'}`}>{opt.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="font-h2 text-h2 text-on-surface">Authentication</h2>
              <p className="font-body-md text-on-surface-variant">Pick how SurgiScan authenticates to <code>{fhirUrl}</code> when pushing data or running connection tests.</p>

              <div className="flex flex-col gap-sm">
                {AUTH_METHOD_OPTIONS.map((opt) => {
                  const active = authMethod === opt.value;
                  return (
                    <label
                      key={opt.value}
                      className={`p-md rounded-lg border-2 cursor-pointer flex items-start gap-md transition-colors ${
                        opt.disabled ? 'opacity-50 cursor-not-allowed border-outline-variant' :
                        active ? 'border-primary bg-primary-fixed/20' : 'border-outline-variant hover:border-primary'
                      }`}
                    >
                      <input
                        type="radio"
                        name="auth_method"
                        disabled={opt.disabled}
                        checked={active}
                        onChange={() => setAuthMethod(opt.value)}
                        className="mt-1 accent-primary"
                      />
                      <div className="flex-1">
                        <p className={`font-body-md font-semibold ${active ? 'text-primary' : 'text-on-surface'}`}>{opt.label}</p>
                        <p className="font-body-sm text-on-surface-variant">{opt.note}</p>
                      </div>
                      {opt.disabled && (
                        <span className="font-label-caps text-[10px] uppercase text-tertiary self-center">Phase C</span>
                      )}
                    </label>
                  );
                })}
              </div>

              {authMethod === 'bearer' && (
                <label className="flex flex-col gap-xs">
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Bearer Token</span>
                  <input
                    type="password"
                    value={bearerToken}
                    onChange={(e) => setBearerToken(e.target.value)}
                    placeholder="Paste the long-lived token here"
                    className="px-md py-sm rounded-lg border border-outline focus:border-primary focus:ring-1 focus:ring-primary outline-none font-body-md font-data-tabular"
                  />
                  <span className="font-body-sm text-tertiary">⚠ Phase B: stored in plain JSONB. Phase C will move secrets to Supabase Vault.</span>
                </label>
              )}
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="font-h2 text-h2 text-on-surface">Resource Mapping</h2>
              <p className="font-body-md text-on-surface-variant">Choose which FHIR resources to include in every export bundle generated for this connection.</p>

              <div className="flex flex-col gap-sm">
                {RESOURCE_OPTIONS.map((opt) => {
                  const checked = resourceFlags[opt.key];
                  return (
                    <label
                      key={opt.key}
                      className={`p-md rounded-lg border-2 flex items-start gap-md cursor-pointer transition-colors ${
                        opt.locked ? 'border-outline-variant cursor-not-allowed' :
                        checked ? 'border-primary bg-primary-fixed/20' : 'border-outline-variant hover:border-primary'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={opt.locked}
                        onChange={(e) => setResourceFlags((f) => ({ ...f, [opt.key]: e.target.checked }))}
                        className="mt-1 w-5 h-5 accent-primary"
                      />
                      <div className="flex-1">
                        <p className={`font-body-md font-semibold ${checked && !opt.locked ? 'text-primary' : 'text-on-surface'}`}>
                          {opt.label}
                          {opt.locked && <span className="ml-sm font-label-caps text-[10px] uppercase text-secondary">REQUIRED</span>}
                        </p>
                        <p className="font-body-sm text-on-surface-variant">{opt.note}</p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <h2 className="font-h2 text-h2 text-on-surface">Test &amp; Save</h2>

              {/* Summary card */}
              <div className="bg-surface-container-low p-md rounded-lg border border-outline-variant space-y-sm">
                <div className="flex justify-between font-body-sm"><span className="text-on-surface-variant">Name</span><span className="font-semibold text-on-surface">{name || '—'}</span></div>
                <div className="flex justify-between font-body-sm"><span className="text-on-surface-variant">FHIR URL</span><span className="font-data-tabular text-on-surface truncate max-w-[60%]" title={fhirUrl}>{fhirUrl || '—'}</span></div>
                <div className="flex justify-between font-body-sm"><span className="text-on-surface-variant">Environment</span><span className="text-on-surface uppercase">{environment}</span></div>
                <div className="flex justify-between font-body-sm"><span className="text-on-surface-variant">Authentication</span><span className="text-on-surface">{AUTH_METHOD_LABEL[authMethod]}</span></div>
                <div className="flex justify-between font-body-sm">
                  <span className="text-on-surface-variant">Resources</span>
                  <span className="text-on-surface text-right">
                    {RESOURCE_OPTIONS.filter(r => resourceFlags[r.key]).map(r => r.label).join(', ') || '—'}
                  </span>
                </div>
              </div>

              <label className="flex items-center gap-sm cursor-pointer">
                <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} className="w-4 h-4 accent-primary" />
                <span className="font-body-sm text-on-surface">Use this as the default connection for this workspace</span>
              </label>

              {/* Test action */}
              <div className="bg-surface-container-low p-md rounded-lg border border-outline-variant flex flex-col gap-sm">
                <div className="flex items-center justify-between gap-md">
                  <div>
                    <p className="font-body-md font-semibold text-on-surface">Connection test</p>
                    <p className="font-body-sm text-on-surface-variant">Probes <code>{fhirUrl.replace(/\/+$/, '')}/metadata</code> — the FHIR CapabilityStatement endpoint.</p>
                  </div>
                  <button
                    onClick={runTest}
                    disabled={testing || saving || !step1Valid}
                    className="px-md py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-sm whitespace-nowrap"
                  >
                    <MIcon name={testing ? 'progress_activity' : 'wifi_tethering'} className={`!text-[18px] ${testing ? 'animate-spin' : ''}`} />
                    {testing ? 'Testing…' : 'Run test'}
                  </button>
                </div>
                {testResult && (
                  <div className={`px-md py-sm rounded-lg font-body-sm ${
                    testResult.ok
                      ? 'bg-secondary-container text-on-secondary-container'
                      : 'bg-error-container text-on-error-container'
                  }`}>
                    {testResult.ok
                      ? <>✅ Reachable. {testResult.metadata_url} returned a FHIR CapabilityStatement.</>
                      : <>❌ {testResult.error}</>
                    }
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-xs pt-md border-t border-outline-variant">
                <button
                  onClick={async () => { try { await persistConnection(); reset(); navigate('/digitisation/export'); } catch {} }}
                  disabled={saving || testing}
                  className="px-lg py-sm bg-primary text-on-primary rounded-lg font-body-md font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-sm"
                >
                  <MIcon name={saving ? 'progress_activity' : 'check'} className={`!text-[18px] ${saving ? 'animate-spin' : ''}`} />
                  {saving ? 'Saving…' : 'Save and finish'}
                </button>
                <button
                  onClick={reset}
                  disabled={saving || testing}
                  className="px-lg py-sm font-body-sm text-on-surface-variant hover:text-on-surface"
                >
                  Save another
                </button>
              </div>
            </>
          )}

          {err && (
            <div className="bg-error-container text-on-error-container px-md py-sm rounded-lg font-body-sm">
              {err}
            </div>
          )}

          {/* Step nav footer */}
          {step !== 4 && (
            <div className="flex justify-between items-center pt-md border-t border-outline-variant">
              <button
                onClick={() => step === 1 ? navigate('/digitisation/export') : goBack()}
                className="px-lg py-sm font-body-md font-semibold text-outline hover:text-on-surface transition-colors flex items-center gap-sm"
              >
                <MIcon name="arrow_back" className="!text-[18px]" />
                {step === 1 ? 'Cancel' : 'Back'}
              </button>
              <button
                onClick={goNext}
                disabled={(step === 1 && !step1Valid) || (step === 2 && !step2Valid)}
                className="px-lg py-sm bg-primary text-on-primary rounded-lg font-body-md font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-sm"
              >
                Next: {STEPS[step]?.title}
                <MIcon name="arrow_forward" className="!text-[18px]" />
              </button>
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
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Last test</th>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant">Default</th>
              <th className="px-lg py-md font-label-caps text-label-caps uppercase text-on-surface-variant text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {listLoading && (
              <tr><td colSpan={7} className="px-lg py-xl text-center text-on-surface-variant">Loading connections…</td></tr>
            )}
            {!listLoading && connections.length === 0 && (
              <tr>
                <td colSpan={7} className="px-lg py-xl text-center font-body-md text-on-surface-variant">
                  No FHIR connections saved yet. Step through the wizard above to add one.
                </td>
              </tr>
            )}
            {!listLoading && connections.map((c) => (
              <tr key={c.id} className="hover:bg-surface-container-low transition-colors">
                <td className="px-lg py-md font-body-md font-medium text-on-surface">{c.name}</td>
                <td className="px-lg py-md font-data-tabular font-body-sm text-on-surface-variant truncate max-w-[260px]" title={c.fhir_url}>
                  {c.fhir_url}
                </td>
                <td className="px-lg py-md">
                  <span className="bg-surface-container-high px-base py-0.5 rounded-lg font-label-caps text-label-caps uppercase text-on-surface-variant">
                    {c.environment}
                  </span>
                </td>
                <td className="px-lg py-md font-body-sm text-on-surface-variant">{AUTH_METHOD_LABEL[c.auth_method] || c.auth_method}</td>
                <td className="px-lg py-md">
                  {c.last_test_at == null ? (
                    <span className="text-outline italic font-body-sm">never</span>
                  ) : c.last_test_ok ? (
                    <span className="text-secondary font-label-caps text-label-caps uppercase inline-flex items-center gap-1">
                      <MIcon name="check_circle" className="!text-[16px]" filled />
                      Ok
                    </span>
                  ) : (
                    <span className="text-error font-label-caps text-label-caps uppercase inline-flex items-center gap-1" title={c.last_test_error || ''}>
                      <MIcon name="error" className="!text-[16px]" filled />
                      Failed
                    </span>
                  )}
                </td>
                <td className="px-lg py-md">
                  {c.is_default ? (
                    <span className="inline-flex items-center gap-1 text-secondary font-label-caps text-label-caps uppercase">
                      <MIcon name="check_circle" className="!text-[16px]" filled />
                      Default
                    </span>
                  ) : (
                    <button onClick={() => setDefault(c.id)} className="text-primary font-body-sm font-semibold hover:underline">Set default</button>
                  )}
                </td>
                <td className="px-lg py-md text-right space-x-sm">
                  <button onClick={() => reTest(c.id)} className="text-primary font-body-sm font-semibold hover:underline">Test</button>
                  <button onClick={() => remove(c.id)} className="text-error font-body-sm font-semibold hover:underline">Delete</button>
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
