import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  Mail,
  ScanLine,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// Tier model (locked 2026-05-18): only the ENTRY tier — kept named
// "Essential" — is sellable now. It IS the digitisation wedge (the
// `module_digitisation` product: digitise paper into structured data,
// keep your existing system — no EHR). Founder price is FLAT PER
// PRACTICE/month: R3,500 locked for practices signing before
// 2026-08-31 (enforced server-side by
// practice_entitlements.is_founder_pricing / founder_protection_until,
// NOT by this page); R4,000 list thereafter.
// Professional (full GP-practice/EHR) and Intelligence (the
// proactive-insights tier) are NOT yet sellable — shown as
// "Coming soon", no price.
// NOTE: seeds/products_and_capabilities.sql still documents the
// Digitisation list price as R4,500 — reconcile that seed/strategy doc
// to R4,000 so billing, the Paystack plan, and this page agree.
const DIGITISATION_FOUNDER_PRICE = 'R3,500';
const DIGITISATION_LIST_PRICE = 'R4,000';
const DIGITISATION_FOUNDER_DEADLINE = '31 August 2026';

const tiers = [
  {
    name: 'Essential',
    badge: 'Founder Plan',
    tagline: 'Turn years of paper patient files into accurate, searchable digital records.',
    priceLabel: DIGITISATION_FOUNDER_PRICE,
    priceUnit: '/practice/month',
    founder: {
      deadline: DIGITISATION_FOUNDER_DEADLINE,
      afterDate: '1 September 2026',
      afterPrice: DIGITISATION_LIST_PRICE,
      afterUnit: '/practice/month',
    },
    note: 'Flat per practice — not per doctor. No setup fee.',
    cta: 'Start a Pilot',
    ctaTone: 'primary',
    target: '/healthcare',
    features: [
      'Bring any scanned or paper patient file into the platform',
      'Patient details, diagnoses, medications & vitals captured for you',
      'Every record checked and confirmed before it is saved',
      'Find any patient’s history in seconds',
      'Works with the practice system you already use',
      'Track progress and turnaround at a glance',
      'POPIA-compliant — your data stays yours',
      'No lock-in — keep the system you already have',
    ],
  },
  {
    name: 'Professional',
    badge: 'Coming soon',
    tagline: 'Run your whole practice in one place.',
    priceLabel: 'Coming soon',
    priceUnit: '',
    note: 'Not yet available — on the roadmap.',
    cta: 'Coming soon',
    ctaTone: 'border',
    target: '/healthcare',
    features: [
      'Everything in Essential',
      'Complete patient records at your fingertips',
      'Front desk, queue and vitals — organised',
      'AI Scribe — notes written for you',
      'Scripts & sick notes in a click',
      'Less admin, more patient time',
    ],
  },
  {
    name: 'Intelligence',
    badge: 'Coming soon',
    tagline: 'Your practice’s data, working for you — surfaces what would otherwise be missed.',
    priceLabel: 'Coming soon',
    priceUnit: '',
    note: 'Not yet available — on the roadmap.',
    cta: 'Coming soon',
    ctaTone: 'border',
    target: '/healthcare',
    features: [
      'Everything in Professional',
      'Proactive prompts for follow-ups and gaps in care',
      'A clear daily picture of what needs attention',
      'Practice-wide insights and trends',
      'Smarter over time',
    ],
  },
];

const PublicHeader = () => {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-7xl mx-auto h-16 px-4 md:px-8 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-900 flex items-center justify-center shadow-sm">
            <ScanLine className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold text-blue-900 tracking-tight">SurgiScan</span>
        </Link>
        <Link
          to="/"
          className="hidden md:inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" />
          All Industries
        </Link>
        <div className="flex items-center gap-3">
          <Link to="/healthcare" className="hidden md:block text-sm font-medium text-slate-600 hover:text-slate-900">
            Healthcare
          </Link>
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
  );
};

const PublicFooter = () => (
  <footer className="bg-slate-100 border-t border-slate-200 py-10">
    <div className="max-w-7xl mx-auto px-4 md:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-blue-900 flex items-center justify-center">
          <ScanLine className="w-4 h-4 text-white" />
        </div>
        <span className="text-sm font-bold text-blue-900">SurgiScan</span>
      </div>
      <p className="text-xs text-slate-500">
        © {new Date().getFullYear()} SurgiScan. POPIA-compliant. Built in South Africa.
      </p>
    </div>
  </footer>
);

const TierCard = ({ tier }) => {
  const navigate = useNavigate();
  const isPrimary = tier.ctaTone === 'primary';
  return (
    <div
      className={`rounded-2xl p-7 flex flex-col h-full ${
        tier.highlighted
          ? 'bg-blue-900 text-white shadow-lg ring-1 ring-blue-900'
          : 'bg-white border border-slate-200'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <h3 className={`text-xl font-bold ${tier.highlighted ? 'text-white' : 'text-slate-900'}`}>
          {tier.name}
        </h3>
        {tier.badge && (
          <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-400 text-amber-950 px-2 py-0.5 rounded-full">
            {tier.badge}
          </span>
        )}
      </div>
      <p className={`text-sm mb-5 ${tier.highlighted ? 'text-blue-100' : 'text-slate-600'}`}>
        {tier.tagline}
      </p>
      <div className="mb-5">
        <span className={`text-3xl font-extrabold ${tier.highlighted ? 'text-white' : 'text-slate-900'}`}>
          {tier.priceLabel}
        </span>
        <span className={`text-sm ${tier.highlighted ? 'text-blue-100' : 'text-slate-500'}`}>
          {' '}
          {tier.priceUnit}
        </span>
      </div>
      {tier.founder && (
        <div className="mb-5 rounded-xl border-2 border-amber-400 bg-amber-50 px-4 py-3">
          <p className="text-sm font-extrabold uppercase tracking-wider text-amber-700">
            ★ Founder Plan
          </p>
          <p className="mt-1 text-sm text-amber-900">
            Sign up before{' '}
            <span className="font-bold">{tier.founder.deadline}</span> and lock{' '}
            <span className="font-extrabold">{tier.priceLabel}</span>
            {tier.priceUnit}.
          </p>
          <p className="mt-1 text-sm text-amber-900">
            From <span className="font-bold">{tier.founder.afterDate}</span> the
            price is{' '}
            <span className="font-extrabold">{tier.founder.afterPrice}</span>
            {tier.founder.afterUnit}.
          </p>
        </div>
      )}
      <p className={`text-xs mb-6 ${tier.highlighted ? 'text-blue-200' : 'text-slate-500'}`}>
        {tier.note}
      </p>
      <Button
        onClick={() => navigate(tier.target)}
        className={
          isPrimary
            ? 'bg-white text-blue-900 hover:bg-slate-100 font-semibold'
            : tier.highlighted
            ? 'bg-blue-800 text-white hover:bg-blue-700 border border-blue-700'
            : 'bg-blue-900 text-white hover:bg-blue-800'
        }
      >
        {tier.cta}
        <ArrowRight className="w-4 h-4 ml-1" />
      </Button>
      <ul className="mt-7 space-y-2.5">
        {tier.features.map((f) => (
          <li
            key={f}
            className={`flex items-start gap-2 text-sm ${
              tier.highlighted ? 'text-blue-50' : 'text-slate-700'
            }`}
          >
            <Check
              className={`w-4 h-4 mt-0.5 shrink-0 ${
                tier.highlighted ? 'text-amber-300' : 'text-blue-900'
              }`}
            />
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

const Pricing = () => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <PublicHeader />

      <main className="max-w-7xl mx-auto px-4 md:px-8 pt-12 md:pt-20 pb-24">
        {/* Hero */}
        <section className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-bold text-blue-900 uppercase tracking-widest">
            Pricing
          </span>
          <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 mt-3 mb-5 leading-tight">
            Straightforward pricing.
            <br />
            Start with Digitisation.
          </h1>
          <p className="text-base md:text-lg text-slate-600">
            One flat monthly price per practice. Founder pricing is locked if you sign up
            before 31 August 2026. More tiers coming soon.
          </p>
        </section>

        {/* Tier cards */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-20">
          {tiers.map((t) => (
            <TierCard key={t.name} tier={t} />
          ))}
        </section>

        {/* Other verticals → contact sales */}
        <section className="bg-blue-900 text-white rounded-2xl p-8 md:p-12 mb-20">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
            <div>
              <Sparkles className="w-8 h-8 text-amber-300 mb-3" />
              <h2 className="text-2xl md:text-3xl font-extrabold mb-3">
                Building for Mining, Logistics, Legal, or Finance?
              </h2>
              <p className="text-blue-100 mb-2">
                Phase 2 verticals are sales-led. We onboard pilots one by one to keep extraction
                quality at SurgiScan standard.
              </p>
              <p className="text-blue-200 text-sm">
                Schema customisation, jurisdictional rules, compliance gates, audit trail — all
                handled by our solutions team during the pilot.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3 md:justify-end">
              <Button
                size="lg"
                onClick={() => (window.location.href = 'mailto:sales@surgiscan.co.za?subject=Pilot inquiry')}
                className="bg-white text-blue-900 hover:bg-slate-100 font-semibold gap-2"
              >
                <Mail className="w-4 h-4" />
                Contact Sales
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={() => navigate('/')}
                className="border-blue-700 text-white hover:bg-blue-800"
              >
                See all industries
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </section>

        {/* FAQ-style note */}
        <section className="text-center max-w-2xl mx-auto">
          <p className="text-sm text-slate-600">
            One flat monthly price per practice — no per-doctor fees, no setup fee. Founder
            pricing is locked for practices that sign up before 31 August 2026. POPIA
            compliance, data isolation, and full audit logging are included.
          </p>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
};

export default Pricing;
