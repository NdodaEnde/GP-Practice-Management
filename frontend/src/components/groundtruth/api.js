/**
 * Local API adapter for the lifted groundtruth components.
 *
 * The groundtruth panel hits endpoints like /api/extract, /api/validate,
 * /api/icd10/validate, /api/nappi/lookup, /api/ml/* — none of which exist
 * on this backend with that exact shape. This adapter intercepts those
 * calls and routes them to our /api/digitisation/* equivalents (or returns
 * graceful defaults for the ones we haven't built yet).
 *
 * As we add real ICD-10 / NAPPI / ML endpoints, replace the stub
 * implementations here — the panel itself stays unchanged.
 */
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';

const adapter = axios.create({ baseURL: '' });

// Attach our JWT to every request (lives in localStorage from our auth flow).
adapter.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

const stubs = {
  // POST /api/extract?doc_id=… → reuse our GET /api/digitisation/validation/{id}
  // and reshape the response so the panel sees res.data.extracted_data.
  extract: async (config) => {
    const docId = config.params?.doc_id;
    if (!docId) throw new Error('doc_id missing');
    const res = await axios.get(`${BACKEND_URL}/api/digitisation/validation/${docId}`, {
      headers: { Authorization: config.headers.Authorization },
    });
    const ext = res.data.extractions || {};
    // Adapt the simple {demographics, vitals, chronic_summary} shape into the
    // rich GPPatientRecordExtraction shape the panel expects, when needed.
    const adapted = adaptExtractionsShape(ext);
    return {
      data: {
        success: true,
        extracted_data: adapted,
        chunks: res.data.chunks || [],
      },
      status: 200,
    };
  },

  // POST /api/validate?doc_id=… body=editedData → save to gp_validation_sessions
  validate: async (config) => {
    const docId = config.params?.doc_id;
    const body  = config.data;
    if (!docId) throw new Error('doc_id missing');
    const res = await axios.post(
      `${BACKEND_URL}/api/digitisation/validation/${docId}/save`,
      { extractions: body },
      { headers: { Authorization: config.headers.Authorization } },
    );
    return { data: { success: true, ...res.data }, status: 200 };
  },

  // GET /api/icd10/validate?code=X → real lookup against Supabase icd10_codes (41,008 rows)
  icd10Validate: async (config) => {
    const code = config.params?.code;
    if (!code) return { data: { valid: false, hipaa_valid: false, code, description: '' }, status: 200 };
    try {
      const res = await axios.get(`${BACKEND_URL}/api/digitisation/icd10/validate`, {
        params:  { code },
        headers: { Authorization: config.headers.Authorization },
      });
      return { data: res.data, status: 200 };
    } catch (err) {
      // Network / 5xx — fail closed (mark invalid) so the panel surfaces it instead of silently passing.
      return {
        data: { valid: false, hipaa_valid: false, code, description: 'Lookup unavailable' },
        status: 200,
      };
    }
  },

  // GET /api/icd10/search?q=X → fuzzy search against Supabase icd10_codes
  icd10Search: async (config) => {
    const q = config.params?.q;
    if (!q || q.length < 2) return { data: { results: [] }, status: 200 };
    try {
      const res = await axios.get(`${BACKEND_URL}/api/digitisation/icd10/search`, {
        params:  { q, limit: config.params?.limit || 20, only_billable: config.params?.only_billable !== false },
        headers: { Authorization: config.headers.Authorization },
      });
      return { data: res.data, status: 200 };
    } catch (err) {
      return { data: { results: [] }, status: 200 };
    }
  },

  // GET /api/nappi/lookup?drug_name=X → real lookup against Supabase nappi_codes (1,637 rows)
  nappiLookup: async (config) => {
    const drug_name = config.params?.drug_name;
    if (!drug_name) return { data: { found: false, nappi_code: null }, status: 200 };
    try {
      const res = await axios.get(`${BACKEND_URL}/api/digitisation/nappi/lookup`, {
        params:  { drug_name, strength: config.params?.strength },
        headers: { Authorization: config.headers.Authorization },
      });
      return { data: res.data, status: 200 };
    } catch (err) {
      // Fail-closed — treat as not-found so reviewer doesn't see a false-green NAPPI badge.
      return { data: { found: false, nappi_code: null }, status: 200 };
    }
  },

  // GET /api/nappi/search?q=X → free-text drug search
  nappiSearch: async (config) => {
    const q = config.params?.q;
    if (!q || q.length < 2) return { data: { results: [] }, status: 200 };
    try {
      const res = await axios.get(`${BACKEND_URL}/api/digitisation/nappi/search`, {
        params:  { q, limit: config.params?.limit || 20 },
        headers: { Authorization: config.headers.Authorization },
      });
      return { data: res.data, status: 200 };
    } catch (err) {
      return { data: { results: [] }, status: 200 };
    }
  },

  // POST /api/ml/risk/batch → empty risks until the ML service is wired
  mlRiskBatch: async () => ({
    data: { risks: [], success: true },
    status: 200,
  }),

  // GET /api/ml/imaging/xray/status → not available
  xrayStatus: async () => ({
    data: { available: false, models_loaded: [] },
    status: 200,
  }),

  // POST /api/ml/imaging/xray/analyze → not available
  xrayAnalyze: async () => {
    throw new Error('X-ray AI is not yet available on this backend.');
  },
};

// Translate `/api/<path>` URLs that the panel hits into our adapter calls.
const route = async (config) => {
  const url = config.url || '';
  // Drop the optional leading /api so we can match by suffix
  const path = url.replace(/^\/api\//, '/').replace(/^\//, '');
  const method = (config.method || 'get').toLowerCase();
  if (method === 'post' && path === 'extract')        return stubs.extract(config);
  if (method === 'post' && path === 'validate')       return stubs.validate(config);
  if (method === 'get'  && path === 'icd10/validate') return stubs.icd10Validate(config);
  if (method === 'get'  && path === 'icd10/search')   return stubs.icd10Search(config);
  if (method === 'get'  && path === 'nappi/lookup')   return stubs.nappiLookup(config);
  if (method === 'get'  && path === 'nappi/search')   return stubs.nappiSearch(config);
  if (method === 'post' && path === 'ml/risk/batch')  return stubs.mlRiskBatch(config);
  if (method === 'get'  && path === 'ml/imaging/xray/status')  return stubs.xrayStatus(config);
  if (method === 'post' && path === 'ml/imaging/xray/analyze') return stubs.xrayAnalyze(config);
  // Unknown routes: surface as 404 so the panel can fall back gracefully.
  console.warn('[groundtruth/api] Unmapped route:', method.toUpperCase(), path);
  return { data: null, status: 404, statusText: 'Not Implemented' };
};

const wrappedMethod = (method) => (url, dataOrConfig, configMaybe) => {
  const isBodyMethod = ['post', 'put', 'patch'].includes(method);
  const config = isBodyMethod
    ? { ...(configMaybe || {}), url, method, data: dataOrConfig }
    : { ...(dataOrConfig || {}), url, method };
  // Run our request interceptors so the auth header is present.
  return new Promise((resolve, reject) => {
    adapter.interceptors.request.handlers.forEach(h => {
      try { h.fulfilled?.(config); } catch (_) {}
    });
    config.headers = config.headers || {};
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    route(config).then(resolve).catch(reject);
  });
};

const api = {
  get:    wrappedMethod('get'),
  post:   wrappedMethod('post'),
  put:    wrappedMethod('put'),
  delete: wrappedMethod('delete'),
};

// ---------------------------------------------------------------------------
// Shape adaptation: simple {demographics, vitals, chronic_summary} → rich
// GPPatientRecordExtraction shape (patient_demographics, vitals_history,
// clinical_history, etc). When the upstream extractor upgrades to use
// GPPatientRecordExtraction directly, this becomes a no-op.
// ---------------------------------------------------------------------------
// Coerce any value (string, array of strings, array of objects with
// .name / .label) into a plain array of strings — guards against React
// trying to render an object as text.
function toStringList(v) {
  if (v == null) return null;
  if (typeof v === 'string') return v;
  if (!Array.isArray(v)) return [String(v)];
  return v.map(item => {
    if (item == null) return '';
    if (typeof item === 'string') return item;
    if (typeof item === 'object') return item.name || item.label || item.value || JSON.stringify(item);
    return String(item);
  }).filter(Boolean);
}

// Map a row from medications_mentioned / likely_current_medications into the
// shape the EHR panel expects ({drug_name, dosage, frequency, ...}).
function normaliseMedRow(item) {
  if (!item) return {};
  if (typeof item === 'string') return { drug_name: item };
  if (typeof item !== 'object') return { drug_name: String(item) };
  return {
    drug_name:         item.medication_name || item.drug_name || item.name || item.medication || '',
    dosage:            item.dosage || item.dose || (item.dosage_info ? splitDosage(item.dosage_info).dose : ''),
    frequency:         item.frequency || (item.dosage_info ? splitDosage(item.dosage_info).freq : ''),
    duration:          item.duration || (item.dosage_info ? splitDosage(item.dosage_info).duration : ''),
    instructions:      item.instructions || item.dosage_info || item.notes || '',
    consultation_date: item.consultation_date || item.mentioned_date || item.date || '',
    status:            item.status || item.context || '',
  };
}

// Best-effort split of "1g TDS x 5/7 PRN fever/pain" into dose/freq/duration tokens.
function splitDosage(s) {
  if (!s || typeof s !== 'string') return { dose: '', freq: '', duration: '' };
  const m = s.match(/^(\S+)\s*([A-Za-z]+)?\s*(?:x\s*([\S\/]+))?/i);
  if (!m) return { dose: s, freq: '', duration: '' };
  return { dose: m[1] || '', freq: m[2] || '', duration: m[3] || '' };
}

// Map a row from conditions_mentioned / likely_chronic_conditions into the
// shape the Diagnoses tab expects.
function normaliseDxRow(item) {
  if (!item) return {};
  if (typeof item === 'string') return { description: item };
  if (typeof item !== 'object') return { description: String(item) };
  return {
    description:       item.description || item.condition || item.name || item.context || '',
    icd10_code:        item.icd10_code || item.icd_code || '',
    consultation_date: item.consultation_date || item.mentioned_date || item.date || '',
    status:            item.status || '',
    doctor:            item.doctor || item.clinician || '',
  };
}

function adaptExtractionsShape(raw) {
  if (!raw || typeof raw !== 'object') return {};
  if ('patient_demographics' in raw || 'vitals_history' in raw || 'clinical_history' in raw) {
    return raw;
  }
  const out = {};
  if (raw.demographics && typeof raw.demographics === 'object') {
    const d = raw.demographics;
    out.patient_demographics = {
      file_number:    d.file_number || d.patient_id || null,
      full_names:     d.full_names || d.first_names || d.given_names || null,
      surname:        d.surname || d.last_name || null,
      id_number:      d.id_number || null,
      date_of_birth:  d.date_of_birth || d.dob || null,
      sex:            d.sex || d.gender || null,
      email:          d.email || null,
      telephone_cell: d.telephone_cell || d.telephone || d.cell || d.contact_number || null,
      address:        d.address || d.residential_address || null,
    };
    if (d.medical_aid && typeof d.medical_aid === 'object') out.medical_aid = d.medical_aid;
  }
  if (raw.vitals && typeof raw.vitals === 'object') {
    const v = raw.vitals;
    out.vitals_history = [{
      consultation_date:     v.latest_date || v.date || null,
      bp_systolic:           v.latest_bp ? String(v.latest_bp).split('/')[0] : v.bp_systolic,
      bp_diastolic:          v.latest_bp ? String(v.latest_bp).split('/')[1] : v.bp_diastolic,
      heart_rate:            v.heart_rate || v.hr,
      temperature_c:         v.temperature_c || v.temp,
      oxygen_saturation:     v.oxygen_saturation || v.spo2,
      weight_kg:             v.weight_kg || v.weight,
      bmi:                   v.bmi,
      hba1c:                 v.hba1c,
      blood_glucose_fasting: v.blood_glucose_fasting || v.fbs,
    }];
  }
  if (raw.chronic_summary && typeof raw.chronic_summary === 'object') {
    const s = raw.chronic_summary;
    out.clinical_history = {
      known_allergies:       toStringList(s.allergies || s.known_allergies),
      chronic_conditions:    toStringList(s.likely_chronic_conditions || s.chronic_conditions),
      past_medical_history:  s.past_medical_history,
      surgical_history:      s.surgical_history,
      family_history:        s.family_history,
      social_history:        s.social_history,
    };
    // Medications — handle both strings and the rich object shape from
    // chronic_summary.medications_mentioned (which has medication_name /
    // dosage_info / context / mentioned_date / legibility per row).
    if (Array.isArray(s.medications)) {
      out.medications = s.medications.map(normaliseMedRow);
    } else if (Array.isArray(s.medications_mentioned)) {
      out.medications = s.medications_mentioned.map(normaliseMedRow);
    } else if (Array.isArray(s.likely_current_medications)) {
      out.medications = s.likely_current_medications.map(normaliseMedRow);
    }
    // Diagnoses — likewise normalise from conditions_mentioned (rich) or
    // likely_chronic_conditions (string list).
    if (Array.isArray(s.diagnoses)) {
      out.diagnoses = s.diagnoses.map(normaliseDxRow);
    } else if (Array.isArray(s.conditions_mentioned)) {
      out.diagnoses = s.conditions_mentioned.map(normaliseDxRow);
    } else if (Array.isArray(s.likely_chronic_conditions)) {
      out.diagnoses = s.likely_chronic_conditions.map(normaliseDxRow);
    }
  }
  Object.entries(raw).forEach(([k, v]) => {
    if (!['demographics', 'vitals', 'chronic_summary'].includes(k) && !(k in out)) out[k] = v;
  });
  return out;
}

export default api;
