import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';

// Material Symbols Outlined icon — wraps a span with the right CSS class.
// Variation axes are set globally in src/index.css.
const MIcon = ({ name, className = '' }) => (
  <span className={`material-symbols-outlined ${className}`} aria-hidden="true">
    {name}
  </span>
);

const Layout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, hasCapability, switchWorkspace } = useAuth();

  // Multi-practice support (TRACEABILITY §11). Fetched on mount; used by
  // the workspace switcher dropdown when the user belongs to >1 workspace.
  const [workspaces, setWorkspaces] = useState([]);
  const [switching, setSwitching]   = useState(false);
  const [showSwitcher, setShowSwitcher] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/auth/workspaces`);
        if (!cancelled) setWorkspaces(res.data?.workspaces || []);
      } catch (e) {
        // 401 if not signed in; legacy single-workspace users don't need
        // the switcher anyway, so silently fall back.
      }
    })();
    return () => { cancelled = true; };
  }, [user?.workspace_id]);

  const onSwitch = async (workspace_id) => {
    if (!workspace_id || workspace_id === user?.workspace_id) {
      setShowSwitcher(false);
      return;
    }
    setSwitching(true);
    const r = await switchWorkspace(workspace_id);
    setSwitching(false);
    if (r.success) {
      // Hard reload — every page-level data fetch was workspace-scoped, and
      // a soft refresh would still display stale lists until each component
      // re-mounted. Cleanest UX: full reload, lands on the same route.
      window.location.reload();
    } else {
      alert(r.error || 'Could not switch workspace');
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Type C = digitisation-only workspace (no EHR). Doctors who already have
  // their own EHR and just need archive digitisation + export. They get a
  // 6-section nav scoped to the digitisation pipeline.
  const isTypeCWorkspace =
    !hasCapability('patient_ehr_basic') && hasCapability('digitisation_upload');

  const typeCNav = [
    { name: 'Dashboard',            path: '/digitisation',            icon: 'dashboard',         capability: 'digitisation_upload' },
    { name: 'Documents',            path: '/digitisation/documents',  icon: 'description',       capability: 'digitisation_upload' },
    { name: 'Validation Queue',     path: '/digitisation/validation', icon: 'fact_check',        capability: 'digitisation_validation' },
    { name: 'Archive',              path: '/digitisation/archive',    icon: 'inventory_2',       capability: 'digitisation_upload' },
    { name: 'Search',               path: '/digitisation/search',     icon: 'search',            capability: 'digitisation_validation' },
    { name: 'Export Centre',        path: '/digitisation/export',     icon: 'send',              capability: 'digitisation_export_basic' },
    { name: 'Operational Insights', path: '/digitisation/insights',   icon: 'monitoring',        capability: 'digitisation_operational_analytics' },
  ];

  // Healthcare nav for Type A/B doctors who run their practice on SurgiScan.
  // Each entry declares the capability it requires; missing entitlements hide
  // the link (frontend defence — backend require_capability is authoritative).
  const healthcareNav = [
    { name: 'Dashboard',            path: '/dashboard',         icon: 'dashboard',         capability: 'patient_ehr_basic' },
    { name: 'Reception Check-In',   path: '/reception',         icon: 'how_to_reg',        capability: 'reception_checkin' },
    { name: 'Vitals Station',       path: '/vitals',            icon: 'monitor_heart',     capability: 'vitals_station' },
    { name: 'Patients',             path: '/patients',          icon: 'group',             capability: 'patient_ehr_basic' },
    { name: 'Digitization Module',  path: '/digitization',      icon: 'folder_managed',    capability: 'digitisation_upload' },
    { name: 'Document Upload',      path: '/document-upload',   icon: 'cloud_upload',      capability: 'digitisation_upload' },
    { name: 'Validation Queue',     path: '/validation-queue',  icon: 'fact_check',        capability: 'digitisation_validation' },
    { name: 'Document Archive',     path: '/digitization-archive', icon: 'inventory_2',    capability: 'digitisation_upload' },
    { name: 'Digitised Documents',  path: '/gp/documents',      icon: 'description',       capability: 'digitisation_upload' },
    { name: 'Extraction Config',    path: '/extraction-config', icon: 'tune',              capability: 'digitisation_upload' },
    { name: 'Billing',              path: '/billing',           icon: 'payments',          capability: 'billing_invoicing' },
    { name: 'Financial Dashboard',  path: '/financial-dashboard', icon: 'trending_up',     capability: 'billing_invoicing' },
    { name: 'Claims Management',    path: '/claims-management', icon: 'shield',            capability: 'billing_invoicing' },
    { name: 'Clinical Analytics',   path: '/analytics',         icon: 'analytics',         capability: 'analytics_cohorts' },
  ];

  const adminNav = user?.role === 'admin' ? [
    { name: 'User Management',      path: '/user-management',      icon: 'manage_accounts' },
    { name: 'Workspace Management', path: '/workspace-management', icon: 'corporate_fare' },
  ] : [];

  // Dev/test pages — admin-only QA fixtures for the Healthcare app. Hidden in
  // Type C workspaces since they exercise EHR-side endpoints the practice
  // didn't buy and are confusing in a Digitisation-only context.
  const devNav = user?.role === 'admin' && !isTypeCWorkspace ? [
    { name: 'ICD-10 Test',     path: '/icd10-test',         icon: 'biotech' },
    { name: 'NAPPI Test',      path: '/nappi-test',         icon: 'medication' },
    { name: 'Lab Test',        path: '/lab-test',           icon: 'experiment' },
    { name: 'Immunizations',   path: '/immunizations-test', icon: 'vaccines' },
    { name: 'Billing Test',    path: '/billing-test',       icon: 'receipt_long' },
  ] : [];

  const baseNav = isTypeCWorkspace ? typeCNav : healthcareNav;
  const navigation = [
    ...baseNav.filter(item => !item.capability || hasCapability(item.capability)),
    ...adminNav,
    ...devNav,
  ];

  const subtitle = isTypeCWorkspace ? 'Digitisation Workspace' : (user?.workspace_name || 'Healthcare');

  const isActive = (path) => location.pathname.startsWith(path);

  return (
    <div className="min-h-screen bg-surface">
      {/* Sidebar */}
      <aside className="fixed top-0 left-0 z-40 w-64 h-screen bg-surface-container-lowest border-r border-outline-variant">
        <div className="h-full px-md py-lg overflow-y-auto flex flex-col">
          {/* Logo */}
          <div className="flex items-center gap-sm mb-xl px-base">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <MIcon name="document_scanner" className="text-on-primary !text-[22px]" />
            </div>
            <div>
              <h1 className="font-h2 text-h2 text-primary">SurgiScan</h1>
              <p className="font-body-sm text-body-sm text-on-surface-variant">{subtitle}</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="space-y-base flex-1">
            {navigation.map((item) => {
              const active = isActive(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                  className={`flex items-center gap-sm px-md py-sm rounded-xl font-body-md text-body-md font-semibold transition-colors ${
                    active
                      ? 'bg-primary text-on-primary'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  <MIcon name={item.icon} className="!text-[20px]" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>

          {/* User profile + workspace info */}
          <div className="mt-auto pt-md border-t border-outline-variant space-y-sm">
            {user && (
              <div className="px-md py-sm bg-surface-container-low rounded-xl">
                <div className="flex items-center gap-base mb-base">
                  <div className="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center">
                    <MIcon name="person" className="text-primary !text-[18px]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-body-sm text-body-sm font-semibold text-on-surface truncate">
                      {user.first_name} {user.last_name}
                    </p>
                    <p className="font-body-sm text-body-sm text-on-surface-variant capitalize">{user.role}</p>
                  </div>
                </div>
                <Button
                  onClick={handleLogout}
                  variant="outline"
                  size="sm"
                  className="w-full gap-base text-body-sm border-outline-variant text-on-surface-variant hover:bg-surface-container"
                >
                  <MIcon name="logout" className="!text-[16px]" />
                  Logout
                </Button>
              </div>
            )}
            <div className="px-md py-sm bg-surface-container-low rounded-xl relative">
              <p className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-1">Active Workspace</p>
              {workspaces.length > 1 ? (
                <button
                  onClick={() => setShowSwitcher(s => !s)}
                  disabled={switching}
                  className="w-full flex items-center justify-between gap-base text-left disabled:opacity-50"
                >
                  <span className="font-body-sm text-body-sm font-semibold text-on-surface truncate">
                    {user?.workspace_name || 'Demo GP Practice'}
                  </span>
                  <MIcon name={switching ? 'progress_activity' : 'unfold_more'} className={`!text-[18px] text-on-surface-variant ${switching ? 'animate-spin' : ''}`} />
                </button>
              ) : (
                <p className="font-body-sm text-body-sm font-semibold text-on-surface">{user?.workspace_name || 'Demo GP Practice'}</p>
              )}
              {workspaces.length > 1 && (
                <p className="font-label-caps text-[10px] uppercase text-on-surface-variant mt-1">
                  {workspaces.length} practices · click to switch
                </p>
              )}

              {showSwitcher && (
                <div
                  className="absolute bottom-full left-0 right-0 mb-base bg-surface-container-lowest border border-outline-variant rounded-xl shadow-xl overflow-hidden z-50"
                  role="listbox"
                >
                  {workspaces.map(ws => {
                    const active = ws.workspace_id === user?.workspace_id;
                    return (
                      <button
                        key={ws.workspace_id}
                        role="option"
                        aria-selected={active}
                        onClick={() => onSwitch(ws.workspace_id)}
                        disabled={switching || active}
                        className={`w-full px-md py-sm text-left flex items-center gap-base hover:bg-surface-container ${active ? 'bg-primary-fixed/40 cursor-default' : ''}`}
                      >
                        <MIcon name={active ? 'check_circle' : 'business'} className={`!text-[18px] ${active ? 'text-primary' : 'text-on-surface-variant'}`} />
                        <div className="flex-1 min-w-0">
                          <p className="font-body-sm text-body-sm font-semibold text-on-surface truncate">{ws.name}</p>
                          <p className="font-label-caps text-[10px] uppercase text-on-surface-variant">
                            {ws.role}{ws.is_primary ? ' · primary' : ''}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="ml-64">
        <main className="p-lg">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
