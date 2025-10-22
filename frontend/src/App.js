import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import PatientRegistry from './pages/PatientRegistry';
import PatientEHR from './pages/PatientEHR';
import NewEncounter from './pages/NewEncounter';
import AIScribe from './pages/AIScribe';
import PatientPrescriptions from './pages/PatientPrescriptions';
import ValidationInterface from './pages/ValidationInterface';
import DocumentDigitization from './pages/DocumentDigitization';
import GPPatientDigitization from './pages/GPPatientDigitization';
import DigitisedDocuments from './pages/DigitisedDocuments';
import DocumentValidation from './pages/DocumentValidation';
import DocumentArchive from './pages/DocumentArchive';
import ReceptionCheckIn from './pages/ReceptionCheckIn';
import QueueDisplay from './pages/QueueDisplay';
import WorkstationDashboard from './pages/WorkstationDashboard';
import VitalsStation from './pages/VitalsStation';
import Billing from './pages/Billing';
import Analytics from './pages/Analytics';
import Layout from './components/Layout';
import '@/App.css';

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="digitize" element={<DocumentDigitization />} />
            <Route path="gp-digitize" element={<GPPatientDigitization />} />
            <Route path="gp/documents" element={<DigitisedDocuments />} />
            <Route path="gp/documents/:documentId/validate" element={<DocumentValidation />} />
            <Route path="patients" element={<PatientRegistry />} />
            <Route path="patients/:patientId" element={<PatientEHR />} />
            <Route path="patients/:patientId/documents" element={<DocumentArchive />} />
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
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;