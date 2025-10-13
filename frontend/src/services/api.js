import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
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

export const documentAPI = {
  upload: (formData) => api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  listByEncounter: (encounterId) => api.get(`/documents/encounter/${encounterId}`),
  getOriginal: (documentId) => api.get(`/documents/${documentId}/original`),
};

export const validationAPI = {
  getSession: (encounterId) => api.get(`/validation/${encounterId}`),
  approve: (documentId, data) => api.post(`/validation/${documentId}/approve`, data),
};

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
};

export default api;