import React from 'react';
import { Link } from 'react-router-dom';
import { Mountain, FileText, Gavel, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

/**
 * MiningGateway — landing page for the Mining industry gateway.
 *
 * Two modules in Mining (per capability_gateways_vs_industry_matrix.html):
 *   • Corporate / Financial-Disclosure  — first build, live below
 *   • Occupational-Health & Litigation records — different buyer, parked
 *
 * Today only the Financial-Disclosure card is enabled. The Occupational-
 * Health card is shown as "planned" so the gateway shape matches the matrix
 * — collapsing the two modules into one "Exxaro product" is exactly the
 * confusion spec §1.2 warns against.
 */

const modules = [
  {
    slug: 'financial-disclosure',
    name: 'Corporate / Financial-Disclosure Intelligence',
    tagline: "Capital-transition story from Exxaro's public reports",
    icon: FileText,
    buyer: 'Finance / IR',
    state: 'live',
    cta: 'Open Copilot',
    route: '/mining/financial-disclosure',
  },
  {
    slug: 'occupational-health',
    name: 'Occupational-Health & Litigation Records',
    tagline: 'Employment + medical records for lung-disease litigation defence',
    icon: Gavel,
    buyer: 'Legal / Compliance',
    state: 'planned',
    cta: 'Not yet built',
    route: null,
  },
];

export default function MiningGateway() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-stone-100 p-2 border border-stone-200">
            <Mountain className="h-5 w-5 text-stone-700" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Mining Gateway</h1>
            <p className="text-sm text-slate-500">
              First customer: Exxaro Resources. Each module is a separate capability with its own buyer —
              they share the platform substrate, not the use case.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {modules.map((m) => {
          const Icon = m.icon;
          const isLive = m.state === 'live';
          const card = (
            <Card
              className={`transition border ${
                isLive
                  ? 'border-slate-200 hover:border-indigo-300 hover:shadow-sm cursor-pointer'
                  : 'border-dashed border-slate-200 opacity-70'
              }`}
            >
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="rounded-md bg-stone-50 p-2 border border-stone-100">
                      <Icon className="h-5 w-5 text-stone-700" />
                    </div>
                    <div>
                      <CardTitle className="text-base text-slate-900">{m.name}</CardTitle>
                      <p className="text-xs text-slate-500 mt-1">{m.tagline}</p>
                    </div>
                  </div>
                  <StatusBadge state={m.state} />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="text-xs text-slate-500">Buyer: <span className="text-slate-700">{m.buyer}</span></div>
                  <div className={`text-sm font-medium flex items-center gap-1 ${isLive ? 'text-indigo-700' : 'text-slate-400'}`}>
                    {m.cta}
                    {isLive && <ArrowRight className="h-4 w-4" />}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
          return m.route ? (
            <Link key={m.slug} to={m.route} className="block">{card}</Link>
          ) : (
            <div key={m.slug}>{card}</div>
          );
        })}
      </div>
    </div>
  );
}

function StatusBadge({ state }) {
  if (state === 'live') {
    return (
      <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-800 text-[10px] uppercase tracking-wide">
        Live
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="border-slate-300 bg-slate-50 text-slate-500 text-[10px] uppercase tracking-wide">
      Planned
    </Badge>
  );
}
