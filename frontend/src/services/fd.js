import axios from 'axios';

// Mining Gateway / Financial-Disclosure API client.
// Same axios pattern as services/api.js — JWT pulled from localStorage on every request.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const FD_BASE = `${BACKEND_URL}/api/fd`;

const fd = axios.create({
  baseURL: FD_BASE,
  headers: { 'Content-Type': 'application/json' },
});

fd.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const fdAPI = {
  // Catalogue + Copilot
  prompts: () => fd.get('/prompts'),
  query: ({ queryId, question, params } = {}) =>
    fd.post('/query', {
      query_id: queryId ?? null,
      question: question ?? null,
      params: params ?? {},
    }),

  // Documents
  uploadDocument: ({ file, docId, docType, fiscalYear, title }) => {
    const fd_form = new FormData();
    fd_form.append('file', file);
    fd_form.append('doc_id', docId);
    fd_form.append('doc_type', docType);
    fd_form.append('fiscal_year', String(fiscalYear));
    fd_form.append('title', title);
    return fd.post('/documents', fd_form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  listDocuments: ({ fiscalYear, docType } = {}) =>
    fd.get('/documents', { params: { fiscal_year: fiscalYear, doc_type: docType } }),
  documentStatus: (docId) => fd.get(`/documents/${docId}`),

  // Needs-review queue
  listNeedsReview: ({ resolved = false } = {}) =>
    fd.get('/needs_review', { params: { resolved } }),
  mergeNeedsReview: (reviewId, { canonicalId, addToRegistry = true }) =>
    fd.post(`/needs_review/${reviewId}/merge`, {
      canonical_id: canonicalId,
      add_to_registry: addToRegistry,
    }),
};

export default fdAPI;
