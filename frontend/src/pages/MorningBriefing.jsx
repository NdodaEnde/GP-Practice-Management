import React, { useEffect, useState, useCallback } from 'react';
import { ExternalLink, AlertTriangle, FileText, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { briefingAPI } from '@/services/briefing';
import {
  resolveBriefingItemView,
  cohortCounts,
  briefingRowData,
  BRIEFING_SOURCE_STATE,
} from '@/services/briefingRowView';

// The morning-briefing screen. It renders ONLY what the Phase-3 query
// layer already materialised; it adds no data path. Its single
// load-bearing job is to make the source-safety property VISIBLE: an
// openable source opens the real scan; an unresolvable source is an
// explicit, visible known-unknown that cannot be mistaken for a live
// link at a glance. All source resolution is delegated to the pure,
// contract-tested briefingRowView (the renderer never reaches into
// row_payload itself — single choke-point for the pinned shape).

function rowName(data) {
  const n = [data.first_name, data.last_name].filter(Boolean).join(' ');
  return n || data.patient_id || 'Patient';
}

const SourceAffordance = ({ view }) => {
  if (view.state === BRIEFING_SOURCE_STATE.OPENABLE) {
    return (
      <a
        href={view.href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:text-blue-900 hover:underline"
      >
        <ExternalLink className="h-4 w-4" />
        Open source scan
        <span className="ml-2 font-normal text-gray-500">{view.citation}</span>
      </a>
    );
  }

  if (view.state === BRIEFING_SOURCE_STATE.NO_SOURCE) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-gray-500">
        <FileText className="h-4 w-4" />
        {view.citation}
      </span>
    );
  }

  // UNRESOLVABLE — first-class, visible, NOT a link. Deliberately styled
  // as a warning so a clinician scanning a 40-row list cannot mistake it
  // for a working source at a glance (the whole point of the property).
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-sm font-medium text-amber-800"
      role="status"
      title={view.unresolvableReason || 'unresolvable'}
    >
      <AlertTriangle className="h-4 w-4" />
      Source unavailable — cannot be opened
      <span className="ml-2 font-normal text-amber-700">{view.citation}</span>
    </span>
  );
};

const MorningBriefing = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await briefingAPI.getBriefing({ kind: 'morning_briefing' });
      setItems(Array.isArray(resp.data?.items) ? resp.data.items : []);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 403) {
        setError('This workspace is not entitled to the clinical query layer.');
      } else {
        setError('Could not load the briefing. Please try again.');
      }
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await briefingAPI.refreshBriefing();
      await load();
    } catch (e) {
      setError('Refresh failed. The briefing below may be stale.');
    } finally {
      setRefreshing(false);
    }
  };

  const counts = cohortCounts(items);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Morning Briefing
          </h1>
          <p className="text-sm text-gray-500">
            Patients flagged by the registered standing queries, each with
            its source.
          </p>
        </div>
        <Button onClick={handleRefresh} disabled={refreshing} variant="outline">
          <RefreshCw
            className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`}
          />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {/* Cohort-altitude unresolvable signal. /api/query/briefing carries
          no envelope count, so this is DERIVED from the rows — the
          clinician sees the dead-link prevalence at the altitude they
          read the list, not only per-row. */}
      {counts.unresolvable > 0 && (
        <div className="flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>
            <strong>
              {counts.unresolvable} of {counts.total}
            </strong>{' '}
            briefing rows have a source that cannot be opened. These are
            shown explicitly below — they are a known unknown, not a
            working link.
          </span>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading briefing…</p>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-gray-500">
            No briefing items have been materialised for this workspace yet.
            Use <strong>Refresh</strong> to materialise the registered
            standing queries.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {counts.total} row{counts.total === 1 ? '' : 's'} · {counts.openable}{' '}
              openable · {counts.unresolvable} unresolvable · {counts.no_source}{' '}
              no source
            </CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-gray-100 p-0">
            {items.map((item) => {
              const data = briefingRowData(item);
              const view = resolveBriefingItemView(item);
              return (
                <div
                  key={item.id}
                  className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium text-gray-900">{rowName(data)}</p>
                    <p className="text-xs text-gray-500">
                      {data.dob ? `DOB ${data.dob}` : null}
                      {data.last_consultation
                        ? `${data.dob ? ' · ' : ''}Last seen ${data.last_consultation}`
                        : null}
                    </p>
                  </div>
                  <SourceAffordance view={view} />
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default MorningBriefing;
