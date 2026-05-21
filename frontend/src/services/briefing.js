// briefing — HTTP client for the Phase-3 query layer's materialised
// morning-briefing rows. Thin: it calls the two endpoints PR D shipped
// and returns the raw envelope; all source-resolution / shape logic
// lives in briefingRowView.js (pure, contract-tested).
//
// AUTH: the shared `api` axios instance (services/api.js) has NO request
// interceptor — AuthContext registers its interceptor on the GLOBAL
// axios, which axios.create() instances do not inherit. Rather than
// mutate shared infra in a thin PR, we attach the bearer token
// per-call, EXACTLY the established pattern AuthContext itself uses for
// its own direct calls (AuthContext.jsx:34, :93, :152:
// `Authorization: Bearer ${localStorage.getItem('access_token')}`).
// /api/query/* is capability-gated (require_capability('clinical_query'))
// so the token is mandatory here.

import api from './api';

function authHeaders() {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const briefingAPI = {
  // GET /api/query/briefing — materialised rows for the caller's
  // workspace (workspace is taken from the JWT server-side, never sent).
  getBriefing: ({ kind, asOfDate } = {}) => {
    const params = {};
    if (kind) params.kind = kind;
    if (asOfDate) params.as_of_date = asOfDate;
    return api.get('/query/briefing', { params, headers: authHeaders() });
  },

  // POST /api/query/briefing/refresh — materialise the registered
  // standing queries for the caller's workspace (the autonomous tick
  // ships disabled; this is the proven manual path).
  refreshBriefing: () =>
    api.post('/query/briefing/refresh', null, { headers: authHeaders() }),
};

export default briefingAPI;
