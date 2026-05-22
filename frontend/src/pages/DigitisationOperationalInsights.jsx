import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';

const MIcon = ({ name, className = '', filled = false }) => (
  <span
    className={`material-symbols-outlined ${className}`}
    style={filled ? { fontVariationSettings: "'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24" } : undefined}
    aria-hidden="true"
  >
    {name}
  </span>
);

// Simple bucket-by-day for the last N days. Returns [{day, count}].
const bucketByDay = (docs, days = 14) => {
  const result = [];
  const now = new Date();
  const start = new Date(now); start.setHours(0, 0, 0, 0); start.setDate(now.getDate() - (days - 1));
  for (let i = 0; i < days; i++) {
    const d = new Date(start); d.setDate(start.getDate() + i);
    result.push({ day: d, count: 0 });
  }
  docs.forEach(doc => {
    const ts = doc.created_at || doc.upload_date;
    if (!ts) return;
    const t = new Date(ts);
    const idx = result.findIndex(r => r.day.toDateString() === t.toDateString());
    if (idx >= 0) result[idx].count += 1;
  });
  return result;
};

// SVG line chart — small enough to not need a charting library.
const LineChart = ({ buckets, color = '#00478d', height = 120 }) => {
  if (!buckets.length) return null;
  const w = 400;
  const max = Math.max(1, ...buckets.map(b => b.count));
  const stepX = w / Math.max(1, buckets.length - 1);
  const points = buckets.map((b, i) => `${i * stepX},${height - (b.count / max) * (height - 20) - 4}`).join(' ');
  const area = `0,${height} ${points} ${(buckets.length - 1) * stepX},${height}`;

  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="none">
      <polygon points={area} fill={color} fillOpacity="0.08" />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      {buckets.map((b, i) => (
        <circle key={i} cx={i * stepX} cy={height - (b.count / max) * (height - 20) - 4} r="2.5" fill={color} />
      ))}
    </svg>
  );
};

// Donut for page-credit usage. Percent 0-100.
const Donut = ({ percent, label, sub, primary = '#00478d', track = '#e1e3e4' }) => {
  const pct = Math.max(0, Math.min(100, percent || 0));
  const r = 56, c = 2 * Math.PI * r, dash = (pct / 100) * c;
  return (
    <svg viewBox="0 0 140 140" className="w-32 h-32">
      <circle cx="70" cy="70" r={r} fill="none" stroke={track} strokeWidth="14" />
      <circle
        cx="70" cy="70" r={r}
        fill="none"
        stroke={primary}
        strokeWidth="14"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${c}`}
        transform="rotate(-90 70 70)"
      />
      <text x="70" y="68" textAnchor="middle" fontSize="22" fontWeight="800" fill="#191c1d" fontFamily="Manrope">
        {pct}%
      </text>
      <text x="70" y="86" textAnchor="middle" fontSize="11" fill="#424752" fontFamily="Public Sans" letterSpacing="1">
        {label}
      </text>
    </svg>
  );
};

const DigitisationOperationalInsights = () => {
  const [docs, setDocs]                 = useState([]);
  const [credits, setCredits]           = useState({ used: 0, total: 1500, percent: 0 });
  const [industryType, setIndustryType] = useState('healthcare');
  const [loading, setLoading]           = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [dashRes, docsRes] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/digitisation/dashboard`),
          axios.get(`${BACKEND_URL}/api/digitisation/documents?limit=200`),
        ]);
        if (cancelled) return;
        const d = dashRes.data || {};
        setCredits(d.page_credits || credits);
        setIndustryType(d.industry_type || 'healthcare');
        setDocs(docsRes.data.documents || []);
      } catch (err) {
        console.error('OperationalInsights load failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const totalProcessed = docs.length;
  const validatedCount = useMemo(
    () => docs.filter(d => ['validated', 'approved'].includes((d.status || '').toLowerCase())).length,
    [docs]
  );
  const failureCount = useMemo(
    () => docs.filter(d => ['rejected', 'failed', 'parsing_failed'].includes((d.status || '').toLowerCase())).length,
    [docs]
  );
  const successRate = totalProcessed
    ? Math.round((validatedCount / totalProcessed) * 1000) / 10
    : null;

  const dailyVolume = useMemo(() => bucketByDay(docs, 14), [docs]);
  const dailyValidated = useMemo(
    () => bucketByDay(docs.filter(d => ['validated', 'approved'].includes((d.status || '').toLowerCase())), 14),
    [docs]
  );

  // Real processing breakdown — every document is validated, failed, or still
  // in the pipeline. All three are computed from the loaded documents (no
  // fabricated "OCR confidence" / "uptime").
  const pct = (n) => (totalProcessed ? Math.round((n / totalProcessed) * 1000) / 10 : 0);
  const inProgressCount = Math.max(0, totalProcessed - validatedCount - failureCount);
  const avgPages = useMemo(() => {
    const withPages = docs.filter(d => d.pages_count != null);
    if (!withPages.length) return null;
    return Math.round((withPages.reduce((s, d) => s + (d.pages_count || 0), 0) / withPages.length) * 10) / 10;
  }, [docs]);
  const breakdown = [
    { label: 'Validated',   value: pct(validatedCount),  hint: 'reviewed & confirmed',                 bar: 'bg-secondary' },
    { label: 'In progress', value: pct(inProgressCount), hint: 'uploaded, parsing, or awaiting review', bar: 'bg-primary' },
    { label: 'Failed',      value: pct(failureCount),    hint: 'parse error or rejected',               bar: 'bg-error' },
  ];

  return (
    <div className="max-w-[1280px] mx-auto space-y-xl">
      {/* Header */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-md">
        <div>
          <h1 className="font-h1 text-h1 text-on-surface">Operational Insights</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant mt-xs">
            Throughput and quality metrics for your digitisation pipeline.
          </p>
        </div>
        <span className="inline-flex items-center gap-base px-md py-sm bg-surface-container-high text-on-surface-variant rounded-lg font-label-caps text-label-caps uppercase">
          <MIcon name="calendar_month" className="!text-[18px]" />
          Last 14 days
        </span>
      </section>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-md">
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm">
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Total Documents</span>
            <MIcon name="bolt" className="text-secondary !text-[22px]" />
          </div>
          <p className="font-h1 text-h1 text-on-surface">{loading ? '…' : totalProcessed}</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">processed this cycle</p>
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm">
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Validated</span>
            <MIcon name="verified" className="text-primary !text-[22px]" />
          </div>
          <p className="font-h1 text-h1 text-on-surface">
            {loading ? '…' : (successRate ?? '—')}{successRate != null && '%'}
          </p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">of all documents</p>
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm">
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Failed</span>
            <MIcon name="report" className="text-error !text-[22px]" />
          </div>
          <p className="font-h1 text-h1 text-on-surface">{loading ? '…' : failureCount}</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">parse / reject</p>
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm">
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">Industry</span>
            <MIcon name="domain" className="text-on-surface-variant !text-[22px]" />
          </div>
          <p className="font-h1 text-h1 text-on-surface capitalize">{industryType.replace(/_/g, ' ')}</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">extraction profile</p>
        </div>
      </div>

      {/* Volume + accuracy chart + Page-credit donut */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <div className="lg:col-span-2 bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
          <div className="flex items-center justify-between mb-md">
            <h3 className="font-h3 text-h3 text-on-surface">Throughput vs Quality Trend</h3>
            <div className="flex items-center gap-md">
              <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-primary">
                <span className="w-3 h-3 rounded-full bg-primary" />
                Volume
              </span>
              <span className="inline-flex items-center gap-base font-label-caps text-label-caps uppercase text-secondary">
                <span className="w-3 h-3 rounded-full bg-secondary" />
                Validated
              </span>
            </div>
          </div>
          <div className="grid grid-rows-2 gap-md">
            <LineChart buckets={dailyVolume} color="#00478d" />
            <LineChart buckets={dailyValidated} color="#006a63" />
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-sm">
            Daily document volume vs validation success over the last 14 days.
          </p>
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg flex flex-col items-center text-center gap-md">
          <h3 className="font-h3 text-h3 text-on-surface self-start">Credit Ecosystem</h3>
          <Donut percent={credits.percent || 0} label="USED" />
          <p className="font-body-md text-body-md text-on-surface">
            <span className="font-bold">{credits.used?.toLocaleString() ?? 0}</span>
            <span className="text-on-surface-variant"> / {credits.total?.toLocaleString() ?? 0} pages</span>
          </p>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-auto">
            Flat monthly fair-use allowance — resets at month-end (Africa/Johannesburg).
            Uploads are never blocked.
          </p>
        </div>
      </div>

      {/* Processing breakdown — real distribution of every document's state */}
      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center justify-between mb-md">
          <h3 className="font-h3 text-h3 text-on-surface">Processing Breakdown</h3>
          <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
            {totalProcessed} document{totalProcessed === 1 ? '' : 's'}
            {avgPages != null && <span className="ml-md">· {avgPages} pages/doc avg</span>}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-lg">
          {breakdown.map((m) => (
            <div key={m.label} className="bg-surface-container-low border border-outline-variant rounded-lg p-md">
              <div className="flex items-center justify-between mb-sm">
                <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">{m.label}</span>
                <span className="font-data-tabular font-body-md text-body-md font-bold text-on-surface">{loading ? '…' : `${m.value}%`}</span>
              </div>
              <div className="h-2 w-full bg-surface-container-high rounded-full overflow-hidden">
                <div className={`${m.bar} h-full`} style={{ width: `${m.value}%` }} />
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant mt-base">{m.hint}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DigitisationOperationalInsights;
