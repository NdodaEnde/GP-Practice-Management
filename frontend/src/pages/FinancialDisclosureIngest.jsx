import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileText, CheckCircle2, AlertCircle, AlertTriangle, Clock,
  TrendingUp, ArrowRight, Info,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import fdAPI from '@/services/fd';

/**
 * FinancialDisclosureIngest — Demo-3 surface for spec §7.5.
 *
 * Three responsibilities:
 *   1. Accept a PDF + metadata, POST to /api/fd/documents, then poll
 *      /api/fd/documents/{doc_id} until ingest_status is terminal.
 *   2. Render the §7.5 health-check banner when the trip-wire fires
 *      (extraction_latency > 30s OR entity_resolution_confidence < 0.85).
 *      Banner is visible, not silent — the user sees the explicit
 *      fail-over message rather than the cached state appearing for free.
 *   3. After ingest, optionally fetch Q-DELTA against the prior fiscal
 *      year and render the new / changed / withdrawn facts with chips.
 */

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cached_fallback']);
// Spec §7.5 health-check thresholds.
const LATENCY_TRIP_SECONDS = 30;
const CONFIDENCE_TRIP = 0.85;

export default function FinancialDisclosureIngest() {
  const navigate = useNavigate();

  // Upload form
  const [file, setFile] = useState(null);
  const [docId, setDocId] = useState('');
  const [docType, setDocType] = useState('integrated');
  const [fiscalYear, setFiscalYear] = useState(2024);
  const [title, setTitle] = useState('');

  // Ingest state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);          // last POST response
  const [docStatus, setDocStatus] = useState(null);    // polled status row
  const [delta, setDelta] = useState(null);            // Q-DELTA result

  // Suggest a doc_id from the filename when one isn't typed.
  useEffect(() => {
    if (!docId && file?.name) {
      const stem = file.name.replace(/\.[^.]+$/, '').toUpperCase().replace(/[^A-Z0-9-]+/g, '-');
      setDocId(stem);
      if (!title) setTitle(file.name.replace(/\.[^.]+$/, ''));
    }
  }, [file]);

  // Poll while the ingest is still running.
  useEffect(() => {
    if (!result?.doc_id) return;
    if (docStatus && TERMINAL_STATUSES.has(docStatus.ingest_status)) return;
    const id = setInterval(async () => {
      try {
        const res = await fdAPI.documentStatus(result.doc_id);
        setDocStatus(res.data);
      } catch (e) {
        // 404 right after upload is possible; quietly keep polling.
      }
    }, 2000);
    return () => clearInterval(id);
  }, [result, docStatus]);

  // Once the ingest is done, fetch Q-DELTA against the prior year.
  useEffect(() => {
    if (!docStatus || docStatus.ingest_status !== 'completed') return;
    if (!docStatus.fiscal_year || docStatus.fiscal_year <= 2020) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fdAPI.query({
          queryId: 'Q_DELTA',
          params: { prev: docStatus.fiscal_year - 1, curr: docStatus.fiscal_year },
        });
        if (!cancelled) setDelta(res.data);
      } catch (e) {
        if (!cancelled) setDelta({ error: e?.response?.data?.detail || e.message });
      }
    })();
    return () => { cancelled = true; };
  }, [docStatus]);

  const handleUpload = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setDocStatus(null);
    setDelta(null);
    if (!file || !docId || !title) {
      setError('Please attach a PDF, set the doc_id, and set the title.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fdAPI.uploadDocument({
        file, docId, docType, fiscalYear: Number(fiscalYear), title,
      });
      setResult(res.data);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Upload failed';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  // §7.5 health-check trip-wires.
  const latency = docStatus?.extraction_latency_seconds ?? null;
  const conf = docStatus?.entity_resolution_confidence ?? null;
  const latencyTripped = latency != null && latency > LATENCY_TRIP_SECONDS;
  const confTripped = conf != null && conf < CONFIDENCE_TRIP;
  const tripped = latencyTripped || confTripped;

  return (
    <div className="container mx-auto px-4 py-6 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-indigo-700" />
            <h1 className="text-2xl font-semibold text-slate-900">Live ingest — Demo 3</h1>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Upload an Exxaro report PDF. The pipeline parses → extracts → resolves entities →
            writes provenance-tagged facts to the graph, then surfaces what changed since the
            prior reporting year.
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate('/mining/financial-disclosure')}>
          ← Back to Copilot
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Left: upload form */}
        <div className="col-span-12 lg:col-span-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Upload a report</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <Label htmlFor="fd-file">PDF</Label>
                  <Input
                    id="fd-file"
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                  {file && (
                    <p className="text-xs text-slate-500 mt-1">
                      {file.name} ({(file.size / 1024 / 1024).toFixed(1)} MB)
                    </p>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="fd-doc-id">doc_id</Label>
                    <Input id="fd-doc-id" value={docId} onChange={(e) => setDocId(e.target.value)}
                           placeholder="EXXARO-IR-2024" />
                  </div>
                  <div>
                    <Label htmlFor="fd-fy">fiscal year</Label>
                    <Input id="fd-fy" type="number" min="1990" max="2100"
                           value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="fd-type">doc type</Label>
                    <select id="fd-type" className="w-full h-9 border border-slate-300 rounded-md px-2 text-sm"
                            value={docType} onChange={(e) => setDocType(e.target.value)}>
                      <option value="integrated">integrated</option>
                      <option value="sustainability">sustainability</option>
                      <option value="investor">investor</option>
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="fd-title">title</Label>
                    <Input id="fd-title" value={title} onChange={(e) => setTitle(e.target.value)}
                           placeholder="Integrated Report 2024" />
                  </div>
                </div>
                <Button type="submit" disabled={submitting || !file}>
                  {submitting ? 'Uploading…' : 'Upload & ingest'}
                </Button>
                {error && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 flex items-start gap-2">
                    <AlertCircle className="h-4 w-4 mt-0.5" /> {error}
                  </div>
                )}
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right: live status, health-check, delta */}
        <div className="col-span-12 lg:col-span-7 space-y-3">
          {result && <IngestSummaryCard result={result} status={docStatus} tripped={tripped} />}
          {tripped && (
            <HealthCheckBanner latency={latency} conf={conf}
                               latencyTripped={latencyTripped} confTripped={confTripped} />
          )}
          {delta && !delta.error && <DeltaCard delta={delta} />}
          {delta?.error && (
            <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              Q-DELTA failed: {delta.error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function IngestSummaryCard({ result, status, tripped }) {
  const isTerminal = status && TERMINAL_STATUSES.has(status.ingest_status);
  const Icon = !status ? Clock : status.ingest_status === 'completed' ? CheckCircle2
             : status.ingest_status === 'failed' ? AlertCircle : Clock;
  const tone = !status ? 'text-slate-500' : status.ingest_status === 'completed' ? 'text-emerald-700'
             : status.ingest_status === 'failed' ? 'text-red-700' : 'text-amber-700';
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Icon className={`h-4 w-4 ${tone}`} />
          Ingest — {result.doc_id}
          {status && (
            <Badge variant="outline" className="ml-auto text-[10px] uppercase tracking-wide">
              {status.ingest_status}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!isTerminal && status && (
          <p className="text-sm text-slate-600 flex items-center gap-2">
            <Clock className="h-3 w-3" /> Currently {status.ingest_status}…
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Elapsed (s)" value={status?.extraction_latency_seconds ?? result.elapsed_seconds ?? '—'} />
          <Metric label="Resolution conf." value={fmt(result.entity_resolution_confidence ?? status?.entity_resolution_confidence)} />
          <Metric label="Quarantined" value={result.quarantined ?? 0} />
          <Metric label="Rejected" value={(result.rejected || []).length} />
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {Object.entries(result.nodes_written || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-slate-100 py-0.5">
              <span className="text-slate-500">{k}</span><span className="font-mono">{v}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {Object.entries(result.edges_written || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-slate-100 py-0.5">
              <span className="text-slate-500">{k}</span><span className="font-mono">{v}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function HealthCheckBanner({ latency, conf, latencyTripped, confTripped }) {
  // Spec §7.5 wording — explicit fail-over message, never silent.
  const parts = [];
  if (latencyTripped) parts.push(`extraction took ${Number(latency).toFixed(1)}s (threshold ${LATENCY_TRIP_SECONDS}s)`);
  if (confTripped)    parts.push(`entity resolution confidence ${Number(conf).toFixed(2)} (threshold ${CONFIDENCE_TRIP})`);
  return (
    <Card className="border-amber-300 bg-amber-50">
      <CardContent className="py-3 flex items-start gap-2 text-amber-900">
        <AlertTriangle className="h-4 w-4 mt-0.5" />
        <div className="text-sm">
          <div className="font-medium">Showing a degraded view for reliability.</div>
          <div className="text-xs mt-1">
            Health-check tripped: {parts.join(' · ')}. Telling you up-front beats a silent fallback —
            the underlying data is still graph-resident; the trip-wire is the warning, not a failure.
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function DeltaCard({ delta }) {
  const rows = delta.rows || [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-indigo-700" />
          {delta.title || 'What changed?'}
        </CardTitle>
        {delta.notes && <p className="text-xs text-slate-500 mt-1">{delta.notes}</p>}
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.length === 0 && (
          <p className="text-xs text-slate-500">No deltas to surface for this period.</p>
        )}
        {rows.map((r, i) => (
          <div key={i} className="rounded-md border border-slate-200 px-3 py-2 text-sm bg-white flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-slate-900 truncate">{r.label}</div>
              <div className="text-xs text-slate-600 font-mono mt-0.5 truncate">{r.value_display}</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {r.extras?.change_type && (
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  {r.extras.change_type}
                </Badge>
              )}
              {r.chip && <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">{r.chip.label}</Badge>}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-md bg-slate-50 border border-slate-100 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-base font-semibold text-slate-900">{value ?? '—'}</div>
    </div>
  );
}

function fmt(n) {
  if (n == null) return '—';
  if (typeof n === 'number') return n.toFixed(2);
  return n;
}
