import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';
const API = `${BACKEND_URL}/api/digitisation/search`;

const MIcon = ({ name, className = '' }) => (
  <span className={`material-symbols-outlined ${className}`} aria-hidden="true">{name}</span>
);

const SECTION_COLOR = {
  patient_demographics: 'bg-secondary-container text-on-secondary-container',
  medical_aid:          'bg-tertiary-fixed text-on-tertiary-fixed-variant',
  clinical_history:     'bg-primary-fixed text-on-primary-fixed-variant',
  vitals_history:       'bg-secondary-container text-on-secondary-container',
  diagnoses:            'bg-error-container text-on-error-container',
  medications:          'bg-tertiary-fixed text-on-tertiary-fixed-variant',
  progress_notes:       'bg-surface-container-high text-on-surface',
  investigations:       'bg-secondary-container text-on-secondary-container',
  referrals:            'bg-primary-fixed text-on-primary-fixed-variant',
};

const EXAMPLE_QUERIES = [
  'patients with high blood pressure',
  'paracetamol prescriptions',
  'urinary tract infection',
  'patients on metformin',
  'recent dyspnea or chest pain',
];

const DigitisationSearch = () => {
  const [query, setQuery]               = useState('');
  const [results, setResults]           = useState(null);
  const [loading, setLoading]           = useState(false);
  const [err, setErr]                   = useState(null);
  const [scopeAll, setScopeAll]         = useState(false);    // §11 federated
  const [accessibleCount, setAccessibleCount] = useState(1);

  // Multi-practice users get the "search all my practices" toggle. We
  // probe /api/auth/workspaces once on mount to know whether to render it.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/auth/workspaces`);
        if (!cancelled) setAccessibleCount(res.data?.count || 1);
      } catch { /* legacy single-workspace; leave at 1 */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const runSearch = useCallback(async (q) => {
    if (!q || q.trim().length < 2) return;
    setLoading(true);
    setErr(null);
    try {
      const res = await axios.get(API, {
        params: { q, limit: 50, scope: scopeAll ? 'all' : 'workspace' },
      });
      setResults(res.data);
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, [scopeAll]);

  const onSubmit = (e) => {
    e.preventDefault();
    runSearch(query);
  };

  return (
    <div className="max-w-[1100px] mx-auto space-y-lg">
      {/* Header */}
      <section>
        <h1 className="font-h1 text-h1 text-on-surface">Search</h1>
        <p className="font-body-md text-body-md text-on-surface-variant mt-xs">
          Natural-language search across every validated digitisation in this workspace —
          patient names, conditions, medications, vital signs, free-text notes.
        </p>
      </section>

      {/* Search bar */}
      <form onSubmit={onSubmit} className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md flex items-center gap-md flex-wrap">
        <MIcon name="search" className="text-primary !text-[28px]" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. patients on metformin with elevated HbA1c"
          className="flex-1 min-w-[200px] bg-transparent border-0 focus:outline-none font-body-md text-on-surface placeholder:text-on-surface-variant"
          autoFocus
        />
        {accessibleCount > 1 && (
          <label className="flex items-center gap-base px-md py-sm bg-surface-container-low rounded-lg cursor-pointer">
            <input
              type="checkbox"
              checked={scopeAll}
              onChange={(e) => setScopeAll(e.target.checked)}
              className="w-4 h-4 accent-primary"
            />
            <span className="font-body-sm text-body-sm text-on-surface">
              Search all {accessibleCount} practices
            </span>
          </label>
        )}
        <button
          type="submit"
          disabled={loading || query.trim().length < 2}
          className="px-lg py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-base"
        >
          <MIcon name={loading ? 'progress_activity' : 'arrow_forward'} className={`!text-[18px] ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {/* Examples (only shown before first search) */}
      {!results && !loading && (
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
          <p className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-md">Try one of these</p>
          <div className="flex flex-wrap gap-sm">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => { setQuery(q); runSearch(q); }}
                className="px-md py-sm bg-surface-container-high hover:bg-primary hover:text-on-primary text-on-surface-variant rounded-lg font-body-sm transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-md">
            <strong>How it works.</strong> Each approved document is split into chunks (one per
            section + per consultation) and indexed via OpenAI embeddings stored in pgvector.
            Your query gets embedded the same way and we return the closest chunks by cosine
            similarity. Results group by source document; click <em>View</em> to open the
            validation panel.
          </p>
        </div>
      )}

      {/* Error */}
      {err && (
        <div className="bg-error-container text-on-error-container px-md py-sm rounded-lg font-body-sm">
          {err}
        </div>
      )}

      {/* Results */}
      {results && (
        <section className="space-y-md">
          <div className="flex items-center justify-between">
            <h3 className="font-h3 text-h3 text-on-surface">
              {results.docs?.length || 0} document{results.docs?.length === 1 ? '' : 's'} matched
              <span className="ml-sm font-body-sm text-body-sm text-on-surface-variant font-normal">
                ({results.count} chunks)
              </span>
            </h3>
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
              query: "{results.query}"
            </span>
          </div>

          {(results.docs || []).length === 0 ? (
            <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-xl text-center">
              <MIcon name="search_off" className="text-outline !text-[48px]" />
              <p className="font-body-md text-body-md text-on-surface-variant mt-md">
                No matches. Try a different phrasing, or check whether the documents you're looking for have been approved (only approved docs are indexed).
              </p>
            </div>
          ) : (
            (results.docs || []).map((doc) => (
              <article key={doc.document_id} className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md">
                <div className="flex items-start justify-between gap-md mb-sm">
                  <div>
                    <p className="font-data-tabular font-body-sm text-on-surface-variant">
                      DOC-{doc.document_id.slice(0, 8).toUpperCase()}
                      {doc.patient_id && (
                        <span className="ml-md">
                          · Patient <span className="font-data-tabular">{doc.patient_id.slice(0, 8)}…</span>
                        </span>
                      )}
                    </p>
                    <p className="font-body-sm text-on-surface-variant">
                      Top similarity:{' '}
                      <span className="font-bold text-on-surface">
                        {Math.round(doc.top_similarity * 100)}%
                      </span>
                    </p>
                  </div>
                  <Link
                    to={`/digitisation/validation/${doc.document_id}`}
                    className="inline-flex items-center gap-base px-md py-sm bg-primary text-on-primary rounded-lg font-body-sm font-bold hover:opacity-90"
                  >
                    <MIcon name="open_in_new" className="!text-[16px]" />
                    View
                  </Link>
                </div>
                <ul className="space-y-xs">
                  {doc.snippets.slice(0, 5).map((s, i) => {
                    const pill = SECTION_COLOR[s.section] || 'bg-surface-container-high text-on-surface-variant';
                    return (
                      <li key={i} className="flex gap-sm items-start">
                        <span className={`px-base py-0.5 rounded font-label-caps text-[10px] uppercase whitespace-nowrap ${pill}`}>
                          {(s.section || 'doc').replace(/_/g, ' ')}
                        </span>
                        <span className="font-body-sm text-body-sm text-on-surface flex-1">
                          {s.text}
                        </span>
                        <span className="font-data-tabular text-body-sm text-on-surface-variant whitespace-nowrap">
                          {Math.round(s.similarity * 100)}%
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </article>
            ))
          )}
        </section>
      )}
    </div>
  );
};

export default DigitisationSearch;
