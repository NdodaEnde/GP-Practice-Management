import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import PatientRegistry from './pages/PatientRegistry';
import PatientEHR from './pages/PatientEHR';
import NewEncounter from './pages/NewEncounter';
import ValidationInterface from './pages/ValidationInterface';
import DocumentDigitization from './pages/DocumentDigitization';
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
            <Route path="patients" element={<PatientRegistry />} />
            <Route path="patients/:patientId" element={<PatientEHR />} />
            <Route path="encounters/new/:patientId" element={<NewEncounter />} />
            <Route path="validation/:encounterId" element={<ValidationInterface />} />
            <Route path="billing" element={<Billing />} />
            <Route path="analytics" element={<Analytics />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;