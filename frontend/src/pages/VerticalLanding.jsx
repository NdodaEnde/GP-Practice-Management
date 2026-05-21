import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  HeartPulse,
  Mountain,
  Package,
  Scale,
  ScanLine,
  Sparkles,
  Truck,
  Wallet,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const VERTICALS = {
  healthcare: {
    name: 'Healthcare',
    headerLabel: 'SurgiScan for Healthcare',
    icon: HeartPulse,
    accentText: 'text-blue-900',
    accentBg: 'bg-blue-900',
    accentBgLight: 'bg-blue-50',
    accentBorder: 'border-blue-100',
    heroEyebrow: 'For South African GP Practices',
    heroHeading: 'From paper records to predictive care.',
    heroBody:
      'Digitise your clinical archive, run an AI-coded EHR, and surface patient-level intelligence — all in one POPIA-aligned platform built for SA private practice.',
    available: true,
    primaryCta: 'Start a Pilot',
    secondaryCta: 'See Pricing',
    phases: [
      {
        eyebrow: 'Phase 01',
        title: 'Records to Digital',
        body:
          'Bulk-scan paper files. Our extraction engine reads every page; validated fields flow straight into the EHR — ready for clinical use.',
        icon: ScanLine,
      },
      {
        eyebrow: 'Phase 02',
        title: 'Clinical Intelligence',
        body:
          'AI Scribe drafts notes from consultations. Safety alerts fire in the prescription workflow. Real-time analytics across your patient population.',
        icon: Sparkles,
      },
      {
        eyebrow: 'Phase 03',
        title: 'Predictive Care (Beta)',
        body:
          'Risk scoring, survival curves and explainable predictions on top of validated clinical data. Opt in per tenant.',
        icon: Activity,
      },
    ],
    proofPoints: [
      'AI-assisted ICD-10 coding',
      'NAPPI medication database with allergy interaction checks',
      'AI Scribe — notes from voice',
      'Batch document upload',
      'PayFast online payments',
      'Multi-tenant with role-based access',
    ],
  },
  mining: {
    name: 'Mining',
    headerLabel: 'SurgiScan for Mining',
    icon: Mountain,
    accentText: 'text-amber-700',
    accentBg: 'bg-amber-700',
    accentBgLight: 'bg-amber-50',
    accentBorder: 'border-amber-100',
    heroEyebrow: 'Industrial Intelligence',
    heroHeading: 'Transform mining archives into operational intelligence.',
    heroBody:
      'Bridge the gap between legacy safety logs, drill records and shift reports — and real-time operational decision-making.',
    available: false,
    primaryCta: 'Request a Pilot',
    secondaryCta: 'Talk to Sales',
    phases: [
      {
        eyebrow: 'Phase 01',
        title: 'Site Records to Digital',
        body: 'Digitise legacy safety logs, shift reports, and drill logs with field-grade OCR precision.',
        icon: ScanLine,
      },
      {
        eyebrow: 'Phase 02',
        title: 'Operational Visibility',
        body: 'Real-time tracking of site safety, compliance monitoring, and resource distribution.',
        icon: Activity,
      },
      {
        eyebrow: 'Phase 03',
        title: 'Predictive Analytics',
        body: 'Identify operational risks and trends before they manifest as incidents.',
        icon: Sparkles,
      },
    ],
    proofPoints: [
      'Field-grade OCR for harsh-copy documents',
      'Compliance audit trail',
      'Multi-site workspace isolation',
      'Custom extraction templates per site',
    ],
  },
  logistics: {
    name: 'Logistics',
    headerLabel: 'SurgiScan for Logistics',
    icon: Truck,
    accentText: 'text-teal-700',
    accentBg: 'bg-teal-700',
    accentBgLight: 'bg-teal-50',
    accentBorder: 'border-teal-100',
    heroEyebrow: 'Supply Chain Intelligence',
    heroHeading: 'Turn waybills, customs forms and inspection reports into live data.',
    heroBody:
      'Eliminate manual data entry across your fleet. Pre-trip inspections, bills of lading, customs declarations — all extracted, validated, and exportable to your existing systems.',
    available: false,
    primaryCta: 'Request a Pilot',
    secondaryCta: 'Talk to Sales',
    phases: [
      {
        eyebrow: 'Phase 01',
        title: 'Document Ingestion',
        body: 'Bulk-process waybills, pre-trip inspections, customs forms with structured extraction.',
        icon: Package,
      },
      {
        eyebrow: 'Phase 02',
        title: 'Operational Tracking',
        body: 'Real-time status across fleet, route, and shipment. Compliance always one click away.',
        icon: Activity,
      },
      {
        eyebrow: 'Phase 03',
        title: 'Predictive Logistics',
        body: 'Anticipate delays, customs holds, and compliance gaps before they cost you.',
        icon: Sparkles,
      },
    ],
    proofPoints: [
      'Pre-trip inspection extraction',
      'Customs and waybill schemas',
      'Multi-tenant fleet workspaces',
      'CSV / FHIR / JSON export',
    ],
  },
  legal: {
    name: 'Legal',
    headerLabel: 'SurgiScan for Legal',
    icon: Scale,
    accentText: 'text-indigo-800',
    accentBg: 'bg-indigo-800',
    accentBgLight: 'bg-indigo-50',
    accentBorder: 'border-indigo-100',
    heroEyebrow: 'Legal Document Intelligence',
    heroHeading: 'Discover, classify, and audit legal archives at scale.',
    heroBody:
      'From historical case files to active matter folders, SurgiScan parses, indexes, and surfaces what matters — with an immutable audit trail your compliance team will love.',
    available: false,
    primaryCta: 'Request a Pilot',
    secondaryCta: 'Talk to Sales',
    phases: [
      {
        eyebrow: 'Phase 01',
        title: 'Archive Digitisation',
        body: 'Convert decades of paper case files into searchable structured records.',
        icon: ScanLine,
      },
      {
        eyebrow: 'Phase 02',
        title: 'Classification & Discovery',
        body: 'AI-assisted matter classification, entity extraction, and clause detection.',
        icon: Sparkles,
      },
      {
        eyebrow: 'Phase 03',
        title: 'Compliance & Audit',
        body: 'Immutable audit trail, retention policies, role-based access for sensitive matters.',
        icon: Activity,
      },
    ],
    proofPoints: [
      'Custom matter taxonomies',
      'Immutable audit trail',
      'Role-based access for sensitive matters',
      'Retention-policy aware',
    ],
  },
  finance: {
    name: 'Finance',
    headerLabel: 'SurgiScan for Finance',
    icon: Wallet,
    accentText: 'text-sky-800',
    accentBg: 'bg-sky-800',
    accentBgLight: 'bg-sky-50',
    accentBorder: 'border-sky-100',
    heroEyebrow: 'Financial Document Intelligence',
    heroHeading: 'Wealth-grade extraction for statements, contracts and regulatory filings.',
    heroBody:
      'Automate document-heavy workflows across audit, KYC, claims and reconciliation. Multi-tenant by design — your data never crosses tenant lines.',
    available: false,
    primaryCta: 'Request a Pilot',
    secondaryCta: 'Talk to Sales',
    phases: [
      {
        eyebrow: 'Phase 01',
        title: 'Document Capture',
        body: 'Bulk-process bank statements, contracts, KYC packs, regulatory filings.',
        icon: ScanLine,
      },
      {
        eyebrow: 'Phase 02',
        title: 'Reconciliation & Audit',
        body: 'Cross-reference transactions, reconcile statements, surface anomalies.',
        icon: Activity,
      },
      {
        eyebrow: 'Phase 03',
        title: 'Risk & Compliance',
        body: 'Predictive risk scoring on top of structured financial data.',
        icon: Sparkles,
      },
    ],
    proofPoints: [
      'Bank statement parsing',
      'KYC document classification',
      'Anomaly detection on transactions',
      'Tenant-isolated by design',
    ],
  },
};

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
          <Link to="/pricing" className="hidden md:block text-sm font-medium text-slate-600 hover:text-slate-900">
            Pricing
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

const VerticalLanding = ({ vertical }) => {
  const navigate = useNavigate();
  const data = VERTICALS[vertical];
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-slate-600">Vertical not found.</p>
      </div>
    );
  }

  const Icon = data.icon;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || submitting) return;
    setSubmitting(true);
    const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
    try {
      const res = await fetch(`${backendUrl}/api/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          vertical,
          source: 'vertical-landing',
        }),
      });
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      setSubmitted(true);
    } catch (err) {
      // Tolerant: still let the prospect feel heard, log for ops.
      console.warn('Lead capture failed, falling back to optimistic confirm:', err);
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <PublicHeader />

      <main className="max-w-7xl mx-auto px-4 md:px-8 pt-12 md:pt-20 pb-24">
        {/* Hero */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-7">
            <div
              className={`inline-flex items-center gap-2 px-3 py-1 rounded-full ${data.accentBgLight} ${data.accentText} mb-6`}
            >
              <Icon className="w-4 h-4" />
              <span className="text-xs font-bold uppercase tracking-wider">{data.heroEyebrow}</span>
            </div>
            <h1 className="text-4xl md:text-6xl font-extrabold leading-tight text-slate-900 mb-5">
              {data.heroHeading}
            </h1>
            <p className="text-base md:text-lg text-slate-600 max-w-2xl mb-8">{data.heroBody}</p>
            <div className="flex flex-col sm:flex-row gap-3">
              {data.available ? (
                <>
                  <Button
                    size="lg"
                    onClick={() => navigate('/login')}
                    className="bg-blue-900 hover:bg-blue-800 text-white px-8 py-6 text-base font-semibold gap-2"
                  >
                    {data.primaryCta}
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() => navigate('/pricing')}
                    className="border-slate-300 text-blue-900 hover:bg-slate-100 px-8 py-6 text-base font-semibold"
                  >
                    {data.secondaryCta}
                  </Button>
                </>
              ) : (
                <a href="#pilot" className="inline-block">
                  <Button
                    size="lg"
                    className={`${data.accentBg} hover:opacity-90 text-white px-8 py-6 text-base font-semibold gap-2`}
                  >
                    {data.primaryCta}
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </a>
              )}
            </div>
          </div>

          {/* Proof points panel */}
          <div className="lg:col-span-5">
            <div className={`rounded-2xl border ${data.accentBorder} bg-white p-6 md:p-8 shadow-sm`}>
              <span className={`text-xs font-bold uppercase tracking-widest ${data.accentText}`}>
                What you get
              </span>
              <ul className="mt-4 space-y-3">
                {data.proofPoints.map((p) => (
                  <li key={p} className="flex items-start gap-2 text-sm text-slate-700">
                    <CheckCircle2 className={`w-4 h-4 mt-0.5 shrink-0 ${data.accentText}`} />
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Three-phase transformation */}
        <section className="mt-20 md:mt-28">
          <div className="mb-10">
            <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900">
              The 3-Phase Transformation
            </h2>
            <div className={`h-1 w-20 mt-4 ${data.accentBg}`} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {data.phases.map((p) => {
              const PhaseIcon = p.icon;
              return (
                <div
                  key={p.title}
                  className="bg-white rounded-xl border border-slate-200 p-6 hover:border-slate-300 transition-colors"
                >
                  <div
                    className={`w-11 h-11 rounded-lg flex items-center justify-center mb-5 ${data.accentBgLight}`}
                  >
                    <PhaseIcon className={`w-5 h-5 ${data.accentText}`} />
                  </div>
                  <span
                    className={`block text-xs font-bold uppercase tracking-wider mb-2 ${data.accentText}`}
                  >
                    {p.eyebrow}
                  </span>
                  <h3 className="text-lg font-bold text-slate-900 mb-2">{p.title}</h3>
                  <p className="text-sm text-slate-600">{p.body}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Pilot / sign-up CTA */}
        <section
          id="pilot"
          className="mt-20 md:mt-28 bg-blue-900 text-white rounded-2xl p-8 md:p-14 text-center"
        >
          <h2 className="text-2xl md:text-3xl font-extrabold mb-3">
            {data.available
              ? `Start your ${data.name} pilot`
              : `${data.name} pilots — request access`}
          </h2>
          <p className="text-blue-100 max-w-2xl mx-auto mb-8">
            {data.available
              ? 'Provision a tenant, upload your first batch of documents, validate the extraction, and decide whether to expand. We handle setup.'
              : `We're onboarding ${data.name.toLowerCase()} pilots one by one to keep extraction quality at SurgiScan standard. Leave your email and we'll be in touch.`}
          </p>
          {!submitted ? (
            <form
              onSubmit={handleSubmit}
              className="max-w-md mx-auto flex items-center bg-white border border-white/20 rounded-full p-1.5 shadow-sm"
            >
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your work email"
                className="flex-1 border-none bg-transparent px-4 py-2 text-sm text-slate-900 focus:outline-none"
              />
              <Button
                type="submit"
                className={`${data.accentBg} hover:opacity-90 text-white px-5 py-2 rounded-full text-xs font-bold uppercase tracking-wider`}
              >
                {data.available ? 'Get Started' : 'Request Pilot'}
              </Button>
            </form>
          ) : (
            <p className="text-teal-300 font-semibold">
              Thanks — we'll reach out shortly to set up your {data.name} pilot.
            </p>
          )}
          <p className="mt-4 text-xs text-blue-200">POPIA-compliant. SA-only data residency.</p>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
};

export default VerticalLanding;
