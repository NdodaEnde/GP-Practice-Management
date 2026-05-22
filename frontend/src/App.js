import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Dashboard from './pages/Dashboard';
import MorningBriefing from './pages/MorningBriefing';
import PatientRegistry from './pages/PatientRegistry';
import PatientEHR from './pages/PatientEHR';
import NewEncounter from './pages/NewEncounter';
import AIScribe from './pages/AIScribe';
import PatientPrescriptions from './pages/PatientPrescriptions';
import ValidationInterface from './pages/ValidationInterface';
import ReceptionCheckIn from './pages/ReceptionCheckIn';
import QueueDisplay from './pages/QueueDisplay';
import WorkstationDashboard from './pages/WorkstationDashboard';
import VitalsStation from './pages/VitalsStation';
import Billing from './pages/Billing';
import Analytics from './pages/Analytics';
import ICD10TestPage from './pages/ICD10TestPage';
import NAPPITestPage from './pages/NAPPITestPage';
import LabTestPage from './pages/LabTestPage';
import BillingTestPage from './pages/BillingTestPage';
import FinancialDashboard from './pages/FinancialDashboard';
import ClaimsManagement from './pages/ClaimsManagement';
import PaymentSuccess from './pages/PaymentSuccess';
import PaymentCancelled from './pages/PaymentCancelled';
import ExtractionConfiguration from './pages/ExtractionConfiguration';
import DigitisationDashboard from './pages/DigitisationDashboard';
import DigitisationStub from './pages/DigitisationStub';
import DocumentsPipeline from './pages/DocumentsPipeline';
import DigitisationValidationQueue from './pages/DigitisationValidationQueue';
import DigitisationValidationDetail from './pages/DigitisationValidationDetail';
import DigitisationArchive from './pages/DigitisationArchive';
import DigitisationExportCentre from './pages/DigitisationExportCentre';
import DigitisationFHIRConnectionWizard from './pages/DigitisationFHIRConnectionWizard';
import DigitisationOperationalInsights from './pages/DigitisationOperationalInsights';
import DigitisationSearch from './pages/DigitisationSearch';
import __PreviewDigitisation from './pages/__PreviewDigitisation';

// TEMPORARY: auto-login helper for the demo admin (workspace with real docs).
// DEV-ONLY auto-login/preview components. Registered as routes ONLY when
// process.env.REACT_APP_ENABLE_DEV_LOGIN === 'true' (set locally for the
// headless verification harness); the check is inlined at the route block so
// the production build (flag unset) dead-code-eliminates them from the bundle.
const AdminAutoLogin = () => {
  React.useEffect(() => {
    const url = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';
    const params = new URLSearchParams(window.location.search);
    const next = params.get('next') || '/dashboard';
    fetch(`${url}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'admin@surgiscan.com', password: 'password123' }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (!d.access_token) { document.title = 'autologin failed'; return; }
        localStorage.setItem('access_token', d.access_token);
        localStorage.setItem('refresh_token', d.refresh_token);
        window.location.replace(next);
      });
  }, []);
  return null;
};

// TEMPORARY: auto-login helper for headless verification. Delete after Phase B.
const TypeCAutoLogin = () => {
  React.useEffect(() => {
    const url = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8002';
    const params = new URLSearchParams(window.location.search);
    const next = params.get('next') || '/digitisation';
    fetch(`${url}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'typec@surgiscan.com', password: 'password123' }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (!d.access_token) { document.title = 'autologin failed'; return; }
        localStorage.setItem('access_token', d.access_token);
        localStorage.setItem('refresh_token', d.refresh_token);
        window.location.replace(next);
      });
  }, []);
  return null;
};
import UserManagement from './pages/UserManagement';
import WorkspaceManagement from './pages/WorkspaceManagement';
import Login from './pages/Login';
import IndustryGateway from './pages/IndustryGateway';
import VerticalLanding from './pages/VerticalLanding';
import Pricing from './pages/Pricing';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import '@/App.css';

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public marketing routes (no Layout sidebar) */}
            <Route path="/" element={<IndustryGateway />} />
            <Route path="/healthcare" element={<VerticalLanding vertical="healthcare" />} />
            <Route path="/mining" element={<VerticalLanding vertical="mining" />} />
            <Route path="/logistics" element={<VerticalLanding vertical="logistics" />} />
            <Route path="/legal" element={<VerticalLanding vertical="legal" />} />
            <Route path="/finance" element={<VerticalLanding vertical="finance" />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/login" element={<Login />} />

            {/* DEV-ONLY auto-login / preview routes. These POST hardcoded creds and
                store real tokens, so they are an auth-bypass surface and must NEVER
                ship in a production bundle. Gated behind a build-time flag that is
                unset in production (set REACT_APP_ENABLE_DEV_LOGIN=true locally for
                the headless verification harness). */}
            {process.env.REACT_APP_ENABLE_DEV_LOGIN === 'true' && (
              <>
                <Route path="/__preview/digitisation" element={<__PreviewDigitisation />} />
                <Route path="/__typec-autologin" element={<TypeCAutoLogin />} />
                <Route path="/__admin-autologin" element={<AdminAutoLogin />} />
              </>
            )}

            {/* Authenticated app routes (wrapped in Layout, gated by ProtectedRoute) */}
            <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="briefing" element={<MorningBriefing />} />
            <Route path="patients" element={<PatientRegistry />} />
            <Route path="patients/:patientId" element={<PatientEHR />} />
            <Route path="patients/:patientId/prescriptions" element={<PatientPrescriptions />} />
            <Route path="patients/:patientId/ai-scribe" element={<AIScribe />} />
            <Route path="encounters/new/:patientId" element={<NewEncounter />} />
            <Route path="validation/:encounterId" element={<ValidationInterface />} />
            <Route path="reception" element={<ReceptionCheckIn />} />
            <Route path="vitals" element={<VitalsStation />} />
            <Route path="queue/display" element={<QueueDisplay />} />
            <Route path="queue/workstation" element={<WorkstationDashboard />} />
            <Route path="billing" element={<Billing />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="icd10-test" element={<ICD10TestPage />} />
            <Route path="nappi-test" element={<NAPPITestPage />} />
            <Route path="lab-test" element={<LabTestPage />} />
            <Route path="billing-test" element={<BillingTestPage />} />
            <Route path="financial-dashboard" element={<FinancialDashboard />} />
            <Route path="claims-management" element={<ClaimsManagement />} />
            <Route path="extraction-config" element={<ExtractionConfiguration />} />

            {/* Type C Digitisation Workspace (no EHR; capability-gated nav) */}
            <Route path="digitisation" element={<DigitisationDashboard />} />
            <Route path="digitisation/documents" element={<DocumentsPipeline />} />
            <Route path="digitisation/validation" element={<DigitisationValidationQueue />} />
            <Route path="digitisation/validation/:documentId" element={<DigitisationValidationDetail />} />
            <Route path="digitisation/archive"  element={<DigitisationArchive />} />
            <Route path="digitisation/export"          element={<DigitisationExportCentre />} />
            <Route path="digitisation/export/connect"  element={<DigitisationFHIRConnectionWizard />} />
            <Route path="digitisation/insights"        element={<DigitisationOperationalInsights />} />
            <Route path="digitisation/search"          element={<DigitisationSearch />} />

            <Route path="user-management" element={<UserManagement />} />
            <Route path="workspace-management" element={<WorkspaceManagement />} />
          </Route>
          
          {/* Payment routes (outside Layout for clean pages) */}
          <Route path="payment/success" element={<PaymentSuccess />} />
          <Route path="payment/cancelled" element={<PaymentCancelled />} />

          {/* Catch-all → Industry Gateway */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </div>
  );
}

export default App;