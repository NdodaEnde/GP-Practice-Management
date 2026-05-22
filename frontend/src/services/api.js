import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach the bearer token to every request. This instance is separate from
// the global axios default that AuthContext patches, so it needs its own
// interceptor — without it the Professional pages, whose endpoints are now
// capability-gated, would all 401.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const patientAPI = {
  create: (data) => api.post('/patients', data),
  list: (search = '') => api.get('/patients', { params: { search } }),
  get: (id) => api.get(`/patients/${id}`),
  update: (id, data) => api.put(`/patients/${id}`, data),
};

export const encounterAPI = {
  create: (data) => api.post('/encounters', data),
  get: (id) => api.get(`/encounters/${id}`),
  listByPatient: (patientId) => api.get(`/encounters/patient/${patientId}`),
  update: (id, data) => api.put(`/encounters/${id}`, data),
};

// documentAPI / validationAPI removed: the manual encounter-document + encounter
// validation flow was retired. Document ingestion + validation run through the
// digitisation pipeline (/api/digitisation/*); the EHR documents tab reads a
// patient's digitised documents via GET /api/patients/{id}/documents.

export const dispenseAPI = {
  create: (data) => api.post('/dispense', data),
  listByEncounter: (encounterId) => api.get(`/dispense/encounter/${encounterId}`),
};

export const invoiceAPI = {
  create: (data) => api.post('/invoices', data),
  list: () => api.get('/invoices'),
  get: (id) => api.get(`/invoices/${id}`),
  updateStatus: (id, status) => api.put(`/invoices/${id}/status`, null, { params: { status } }),
};

export const analyticsAPI = {
  getSummary: () => api.get('/analytics/summary'),
  getOperational: () => api.get('/analytics/operational'),
  getClinical: () => api.get('/analytics/clinical'),
  getFinancial: () => api.get('/analytics/financial'),
  getMedications: (days = 90) => api.get('/analytics/medications', { params: { days } }),
};

export default api;