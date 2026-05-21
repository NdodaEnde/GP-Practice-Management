import React from 'react';
import { Link } from 'react-router-dom';
import { Lock, ArrowRight, Mail, ScanLine } from 'lucide-react';
import { Button } from '@/components/ui/button';

/**
 * CapabilityUpsell — rendered when a route or section is gated behind a
 * capability the current practice doesn't have.
 *
 * The à la carte product model from v2 strategy means we know exactly which
 * Module the doctor would buy to unlock any given capability. This map drives
 * the upsell copy so it's specific and actionable rather than generic.
 *
 * If a new capability is added that doesn't appear here, falls back to a
 * generic "Contact sales" CTA — but the right move is to ADD the entry.
 *
 * Source of truth for capability → product mapping:
 *   /Users/luzuko/GP-Practice-Management/backend/seeds/products_and_capabilities.sql
 */

const CAPABILITY_TO_MODULE = {
  // Practice Platform — Professional capabilities
  ai_scribe:               { module: 'Practice Platform — Professional', tier: 'professional' },
  telehealth:              { module: 'Practice Platform — Professional', tier: 'professional' },
  queue_display:           { module: 'Practice Platform — Professional', tier: 'professional' },
  vitals_station:          { module: 'Practice Platform — Professional', tier: 'professional' },
  workflow_dashboards:     { module: 'Practice Platform — Professional', tier: 'professional' },

  // Module 01 Digitisation
  digitisation_upload:        { module: 'Intelligence Layer — Digitisation', tier: 'module' },
  digitisation_validation:    { module: 'Intelligence Layer — Digitisation', tier: 'module' },
  digitisation_auto_populate: { module: 'Intelligence Layer — Digitisation', tier: 'module' },
  digitisation_export_basic:  { module: 'Intelligence Layer — Digitisation', tier: 'module' },
  digitisation_export_fhir:   { module: 'Intelligence Layer — Digitisation', tier: 'module' },

  // Module 02 Analytics
  analytics_cohorts:        { module: 'Intelligence Layer — Advanced Clinical Analytics', tier: 'module' },
  analytics_claims_aging:   { module: 'Intelligence Layer — Advanced Clinical Analytics', tier: 'module' },
  analytics_productivity:   { module: 'Intelligence Layer — Advanced Clinical Analytics', tier: 'module' },
  analytics_drug_spend:     { module: 'Intelligence Layer — Advanced Clinical Analytics', tier: 'module' },
  analytics_semantic_search:{ module: 'Intelligence Layer — Advanced Clinical Analytics', tier: 'module' },
  analytics_dashboards:     { module: 'Intelligence Layer — Advanced Clinical Analytics', tier: 'module' },

  // Module 03 Clinical AI Beta
  clinical_ai_diagnostic:    { module: 'Intelligence Layer — Clinical AI (Beta)', tier: 'beta' },
  clinical_ai_safety_monitor:{ module: 'Intelligence Layer — Clinical AI (Beta)', tier: 'beta' },
  clinical_ai_risk_scoring:  { module: 'Intelligence Layer — Clinical AI (Beta)', tier: 'beta' },
  clinical_ai_imaging:       { module: 'Intelligence Layer — Clinical AI (Beta)', tier: 'beta' },
  clinical_ai_population:    { module: 'Intelligence Layer — Clinical AI (Beta)', tier: 'beta' },
  clinical_ai_audit_signed:  { module: 'Intelligence Layer — Clinical AI (Beta)', tier: 'beta' },
};

const TIER_BLURBS = {
  professional: 'Available with Practice Platform Professional. Adds AI Scribe, telehealth, queue/vitals stations, and workflow dashboards on top of Essential.',
  module:       'Sold à la carte — works on top of any Practice Platform tier or alongside your existing EHR.',
  beta:         'Currently invite-only Beta. Available to a small set of design-partner practices in exchange for case studies and feedback.',
};

const TIER_CTA = {
  professional: { label: 'Talk to Sales — Upgrade to Professional', subject: 'Upgrade to Practice Platform Professional' },
  module:       { label: 'Talk to Sales — Add this Module',         subject: 'Add Intelligence Layer Module' },
  beta:         { label: 'Apply to Beta — Talk to us',               subject: 'Clinical AI Beta application' },
};

const CapabilityUpsell = ({ capability }) => {
  const meta = CAPABILITY_TO_MODULE[capability];
  const moduleName = meta?.module || 'an additional module';
  const blurb = meta ? TIER_BLURBS[meta.tier] : 'This feature requires an additional product on your SurgiScan plan.';
  const ctaConfig = meta ? TIER_CTA[meta.tier] : { label: 'Contact Sales', subject: `Capability inquiry — ${capability}` };
  const mailto = `mailto:sales@surgiscan.co.za?subject=${encodeURIComponent(ctaConfig.subject)}`;

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="max-w-xl w-full bg-white border border-slate-200 rounded-2xl p-8 md:p-10 shadow-sm">
        <div className="flex items-start gap-4 mb-6">
          <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center shrink-0">
            <Lock className="w-6 h-6 text-blue-900" />
          </div>
          <div>
            <p className="text-xs font-bold text-blue-900 uppercase tracking-widest mb-1">
              Locked feature
            </p>
            <h1 className="text-2xl font-bold text-slate-900 leading-tight">
              This feature is part of {moduleName}.
            </h1>
          </div>
        </div>

        <p className="text-base text-slate-600 mb-6">{blurb}</p>

        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-8">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
            Capability
          </p>
          <code className="text-sm text-slate-800 font-mono">{capability}</code>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <Button
            asChild
            className="bg-blue-900 hover:bg-blue-800 text-white gap-2"
          >
            <a href={mailto}>
              <Mail className="w-4 h-4" />
              {ctaConfig.label}
              <ArrowRight className="w-4 h-4" />
            </a>
          </Button>
          <Button asChild variant="outline" className="border-slate-300">
            <Link to="/pricing">See full pricing</Link>
          </Button>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-200 flex items-center gap-2 text-xs text-slate-500">
          <ScanLine className="w-4 h-4 text-blue-900" />
          <span>SurgiScan — capability gating active. POPIA-compliant.</span>
        </div>
      </div>
    </div>
  );
};

export default CapabilityUpsell;
