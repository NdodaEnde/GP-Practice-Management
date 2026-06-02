import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Bell,
  Bolt,
  ChevronRight,
  HeartPulse,
  Mountain,
  Package,
  Scale,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Truck,
  Wallet,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const verticals = [
  {
    slug: 'healthcare',
    name: 'Healthcare',
    tagline: 'Patient-first intelligence',
    cta: 'Explore Clinical',
    icon: HeartPulse,
    accent: 'text-blue-900 bg-blue-50 border-blue-100 hover:border-blue-900',
    ctaTone: 'text-blue-900',
    available: true,
  },
  {
    slug: 'logistics',
    name: 'Logistics',
    tagline: 'Next-gen supply chain',
    cta: 'View Pipelines',
    icon: Truck,
    accent: 'text-teal-700 bg-teal-50 border-teal-100 hover:border-teal-700',
    ctaTone: 'text-teal-700',
    available: false,
  },
  {
    slug: 'legal',
    name: 'Legal',
    tagline: 'Immutable compliance',
    cta: 'Review Statutes',
    icon: Scale,
    accent: 'text-indigo-800 bg-indigo-50 border-indigo-100 hover:border-indigo-800',
    ctaTone: 'text-indigo-800',
    available: false,
  },
  {
    slug: 'finance',
    name: 'Finance',
    tagline: 'Wealth-grade security',
    cta: 'Audit Assets',
    icon: Wallet,
    accent: 'text-sky-800 bg-sky-50 border-sky-100 hover:border-sky-800',
    ctaTone: 'text-sky-800',
    available: false,
  },
  {
    slug: 'mining',
    name: 'Mining',
    tagline: 'Capital-transition intelligence',
    cta: 'Open Copilot',
    icon: Mountain,
    accent: 'text-amber-700 bg-amber-50 border-amber-100 hover:border-amber-700',
    ctaTone: 'text-amber-700',
    available: true,
  },
];

const corePillars = [
  {
    icon: ScanLine,
    title: 'OCR Ingestion',
    body: '99%+ accuracy on handwritten and legacy typeface conversion.',
  },
  {
    icon: Sparkles,
    title: 'AI Parsing',
    body: 'Contextual mapping of unstructured documents into clean structured fields.',
  },
  {
    icon: Activity,
    title: 'Predictive Analytics',
    body: 'Identify trends before they manifest into operational bottlenecks.',
  },
];

const IndustryGateway = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top App Bar */}
      <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-7xl mx-auto h-16 px-4 md:px-8 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-900 flex items-center justify-center shadow-sm">
              <ScanLine className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold text-blue-900 tracking-tight">SurgiScan</span>
          </Link>
          <nav className="hidden md:flex items-center gap-8">
            <a href="#core-engine" className="text-sm font-semibold text-blue-900 hover:opacity-80">
              Intelligence
            </a>
            <a href="#verticals" className="text-sm font-medium text-slate-600 hover:text-slate-900">
              Solutions
            </a>
            <Link to="/pricing" className="text-sm font-medium text-slate-600 hover:text-slate-900">
              Pricing
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <Bell className="w-5 h-5 text-blue-900 hidden md:block" />
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/login')}
              className="border-blue-900 text-blue-900 hover:bg-blue-50"
            >
              Sign In
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 md:px-8 pt-12 md:pt-20 pb-32">
        {/* Hero */}
        <section className="py-12 md:py-24 flex flex-col items-center text-center">
          <div className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-900 rounded-full mb-6">
            <Bolt className="w-4 h-4 mr-2" />
            <span className="text-xs font-bold uppercase tracking-wider">V2.0 Now Live</span>
          </div>
          <h1 className="text-4xl md:text-6xl font-extrabold leading-tight text-blue-900 max-w-4xl mb-4">
            The Document Intelligence Layer for Your Industry.
          </h1>
          <p className="text-base md:text-lg text-slate-600 max-w-2xl mb-8">
            Transform legacy archives into actionable data in seconds. Our multi-tenant engine powers
            South Africa's most critical sectors with surgical precision.
          </p>
          <div className="flex flex-col md:flex-row gap-3">
            <Button
              size="lg"
              onClick={() => navigate('/healthcare')}
              className="bg-blue-900 hover:bg-blue-800 text-white px-8 py-6 text-base font-semibold gap-2"
            >
              Deploy Intelligence
              <ArrowRight className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="border-slate-300 text-blue-900 hover:bg-slate-100 px-8 py-6 text-base font-semibold"
            >
              View Case Studies
            </Button>
          </div>
        </section>

        {/* Vertical Selection */}
        <section id="verticals" className="mb-24 md:mb-32">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
            <div>
              <span className="text-xs font-bold text-blue-900 uppercase tracking-widest">
                Sector Specific
              </span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900 mt-2">
                Choose Your Vertical
              </h2>
            </div>
            <p className="text-sm text-slate-600 max-w-sm">
              Select your industry to see how our extraction templates and intelligence models adapt
              to your data taxonomies.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {verticals.map((v) => {
              const Icon = v.icon;
              return (
                <Link
                  key={v.slug}
                  to={`/${v.slug}`}
                  data-testid={`vertical-${v.slug}`}
                  className={`group relative overflow-hidden rounded-xl border bg-white/70 backdrop-blur p-6 transition-all hover:shadow-md ${v.accent}`}
                >
                  <div
                    className={`absolute -right-4 -top-4 opacity-5 group-hover:opacity-10 transition-opacity`}
                  >
                    <Icon className="w-32 h-32" />
                  </div>
                  <div
                    className={`w-11 h-11 rounded-lg flex items-center justify-center mb-5 ${v.accent}`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 mb-1">{v.name}</h3>
                  <p className="text-sm text-slate-600 mb-6">{v.tagline}</p>
                  <div
                    className={`flex items-center gap-1 text-xs font-bold uppercase tracking-wider ${v.ctaTone}`}
                  >
                    {v.cta}
                    <ChevronRight className="w-3 h-3" />
                  </div>
                  {!v.available && (
                    <span className="absolute top-3 right-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                      Pilot
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </section>

        {/* Core Engine */}
        <section
          id="core-engine"
          className="relative overflow-hidden rounded-2xl bg-blue-900 text-white p-8 md:p-16 mb-24"
        >
          <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            <div>
              <span className="text-xs font-bold uppercase tracking-[0.2em] text-blue-200">
                The Core Engine
              </span>
              <h2 className="text-3xl md:text-5xl font-extrabold leading-tight mt-4 mb-6">
                Universal Power for Multi-Tenant Resilience
              </h2>
              <p className="text-base md:text-lg text-blue-100 mb-8 max-w-lg">
                Our underlying architecture doesn't just read data; it understands intent. Build your
                entire ecosystem on a foundation of three fundamental pillars.
              </p>
              <div className="space-y-3">
                {corePillars.map((p) => {
                  const Icon = p.icon;
                  return (
                    <div
                      key={p.title}
                      className="flex items-start gap-4 p-4 bg-white/10 rounded-lg border border-white/10"
                    >
                      <Icon className="w-5 h-5 text-teal-300 mt-0.5 shrink-0" />
                      <div>
                        <h4 className="text-sm font-bold mb-1">{p.title}</h4>
                        <p className="text-sm text-blue-100/80">{p.body}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="hidden lg:block">
              <div className="bg-white/5 p-6 rounded-xl border border-white/10 backdrop-blur-md">
                <div className="flex items-center justify-between pb-4 mb-6 border-b border-white/10">
                  <span className="text-xs font-bold uppercase tracking-wider">
                    Latest Data Stream
                  </span>
                  <div className="flex gap-1">
                    <div className="w-2 h-2 rounded-full bg-teal-300" />
                    <div className="w-2 h-2 rounded-full bg-white/20" />
                  </div>
                </div>
                <div className="space-y-3 mb-8">
                  <div className="h-2 w-full bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-teal-300 w-[70%]" />
                  </div>
                  <div className="h-2 w-full bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-teal-300 w-[45%]" />
                  </div>
                  <div className="h-2 w-full bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-teal-300 w-[90%]" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-white/10 rounded border border-white/10">
                    <span className="text-[10px] uppercase tracking-wider opacity-60 block">
                      Ingestion
                    </span>
                    <span className="text-2xl font-bold">1.2 TB/s</span>
                  </div>
                  <div className="p-3 bg-white/10 rounded border border-white/10">
                    <span className="text-[10px] uppercase tracking-wider opacity-60 block">
                      Latency
                    </span>
                    <span className="text-2xl font-bold">14 ms</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="text-center py-12 md:py-16 bg-white rounded-2xl border border-slate-200">
          <ShieldCheck className="w-10 h-10 text-blue-900 mx-auto mb-4" />
          <h2 className="text-2xl md:text-3xl font-extrabold text-slate-900 mb-3">
            Ready to digitise your operations?
          </h2>
          <p className="text-sm md:text-base text-slate-600 mb-8 max-w-xl mx-auto">
            Join healthcare providers and enterprise partners across South Africa who trust SurgiScan
            for high-fidelity document intelligence.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              navigate('/healthcare');
            }}
            className="max-w-md mx-auto flex items-center bg-white border border-slate-300 rounded-full p-1.5 shadow-sm"
          >
            <input
              type="email"
              required
              placeholder="Enter your email"
              className="flex-1 border-none bg-transparent px-4 py-2 text-sm focus:outline-none"
            />
            <Button
              type="submit"
              className="bg-blue-900 hover:bg-blue-800 text-white px-5 py-2 rounded-full text-xs font-bold uppercase tracking-wider"
            >
              Get Started
            </Button>
          </form>
          <p className="mt-4 text-xs text-slate-400">
            POPIA-compliant. Multi-tenant. Built for South African healthcare.
          </p>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-slate-100 border-t border-slate-200 py-12">
        <div className="max-w-7xl mx-auto px-4 md:px-8 grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-blue-900 flex items-center justify-center">
                <ScanLine className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-bold text-blue-900">SurgiScan</span>
            </div>
            <p className="text-xs text-slate-600">
              Document intelligence with surgical precision. Multi-tenant. POPIA-aligned.
            </p>
          </div>
          <FooterCol
            heading="Resources"
            links={[
              ['API Documentation', '#'],
              ['Security Architecture', '#'],
              ['Compliance Standards', '#'],
            ]}
          />
          <FooterCol
            heading="Platform"
            links={[
              ['Industry Gateway', '/'],
              ['Pricing', '/pricing'],
              ['Healthcare', '/healthcare'],
            ]}
          />
          <FooterCol
            heading="Support"
            links={[
              ['Status', '#'],
              ['Contact Sales', '#'],
              ['Privacy & Terms', '#'],
            ]}
          />
        </div>
        <div className="max-w-7xl mx-auto px-4 md:px-8 mt-8 pt-6 border-t border-slate-200">
          <p className="text-xs text-slate-500">© {new Date().getFullYear()} SurgiScan. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

const FooterCol = ({ heading, links }) => (
  <div>
    <h5 className="text-xs font-bold text-blue-900 uppercase tracking-widest mb-4">{heading}</h5>
    <ul className="space-y-2">
      {links.map(([label, href]) => (
        <li key={label}>
          {href.startsWith('/') ? (
            <Link to={href} className="text-sm text-slate-600 hover:text-blue-900">
              {label}
            </Link>
          ) : (
            <a href={href} className="text-sm text-slate-600 hover:text-blue-900">
              {label}
            </a>
          )}
        </li>
      ))}
    </ul>
  </div>
);

export default IndustryGateway;
