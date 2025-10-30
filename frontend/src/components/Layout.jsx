import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { Activity, Users, FileText, DollarSign, ClipboardCheck, LayoutDashboard, BarChart3, Stethoscope, UserCheck, HeartPulse, Code, Package, Syringe, Receipt, TrendingUp, Shield, Settings } from 'lucide-react';

const Layout = () => {
  const location = useLocation();

  const navigation = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Reception Check-In', path: '/reception', icon: UserCheck },
    { name: 'Vitals Station', path: '/vitals', icon: HeartPulse },
    { name: 'Digitize Documents', path: '/digitize', icon: FileText },
    { name: 'GP Patient Digitization', path: '/gp-digitize', icon: Stethoscope },
    { name: 'Digitised Documents', path: '/gp/documents', icon: FileText },
    { name: 'Patients', path: '/patients', icon: Users },
    { name: 'ICD-10 Test', path: '/icd10-test', icon: Code },
    { name: 'NAPPI Test', path: '/nappi-test', icon: Package },
    { name: 'Lab Test', path: '/lab-test', icon: Activity },
    { name: 'Immunizations', path: '/immunizations-test', icon: Syringe },
    { name: 'Billing Test', path: '/billing-test', icon: Receipt },
    { name: 'Billing', path: '/billing', icon: DollarSign },
    { name: 'Financial Dashboard', path: '/financial-dashboard', icon: TrendingUp },
    { name: 'Claims Management', path: '/claims-management', icon: Shield },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  ];

  const isActive = (path) => location.pathname.startsWith(path);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Sidebar */}
      <aside className="fixed top-0 left-0 z-40 w-64 h-screen bg-white border-r border-slate-200 shadow-sm">
        <div className="h-full px-4 py-6 overflow-y-auto">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-8 px-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shadow-md">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-800">SurgiScan</h1>
              <p className="text-xs text-slate-500">GP Practice</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.name.toLowerCase().replace(' ', '-')}`}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-all duration-200 ${
                    active
                      ? 'bg-gradient-to-r from-teal-500 to-cyan-600 text-white shadow-md'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>

          {/* Workspace Info */}
          <div className="mt-auto pt-6 border-t border-slate-200">
            <div className="px-4 py-3 bg-slate-50 rounded-lg">
              <p className="text-xs font-medium text-slate-500 mb-1">Active Workspace</p>
              <p className="text-sm font-semibold text-slate-700">Demo GP Practice</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="ml-64">
        <main className="p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;