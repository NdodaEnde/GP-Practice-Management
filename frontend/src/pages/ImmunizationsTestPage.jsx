import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Syringe, Plus, AlertCircle, Calendar, Shield } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const ImmunizationsTestPage = () => {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState('');
  const [immunizations, setImmunizations] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  
  const [immunizationForm, setImmunizationForm] = useState({
    vaccine_name: '',
    vaccine_type: '',
    administration_date: new Date().toISOString().split('T')[0],
    dose_number: 1,
    route: 'Intramuscular',
    anatomical_site: 'Left deltoid',
    series_name: '',
    doses_in_series: 1,
    series_complete: false,
    administered_by: 'Nurse Smith',
    occupational_requirement: false,
    vaccine_cost: '',
    administration_fee: '50'
  });

  useEffect(() => {
    loadPatients();
  }, []);

  useEffect(() => {
    if (selectedPatient) {
      loadPatientImmunizations();
      loadImmunizationSummary();
    }
  }, [selectedPatient]);

  const loadPatients = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/patients`);
      setPatients(response.data || []);
    } catch (error) {
      console.error('Error loading patients:', error);
    }
  };

  const loadPatientImmunizations = async () => {
    if (!selectedPatient) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/immunizations/patient/${selectedPatient}`);
      setImmunizations(response.data || []);
    } catch (error) {
      showMessage('error', 'Error loading immunizations');
    } finally {
      setLoading(false);
    }
  };

  const loadImmunizationSummary = async () => {
    if (!selectedPatient) return;
    
    try {
      const response = await axios.get(`${BACKEND_URL}/api/immunizations/patient/${selectedPatient}/summary`);
      setSummary(response.data.summary || {});
    } catch (error) {
      console.error('Error loading summary:', error);
    }
  };

  const createImmunization = async (e) => {
    e.preventDefault();
    if (!selectedPatient) {
      showMessage('error', 'Please select a patient first');
      return;
    }

    setLoading(true);
    try {
      const data = {
        patient_id: selectedPatient,
        ...immunizationForm,
        dose_number: parseInt(immunizationForm.dose_number),
        doses_in_series: parseInt(immunizationForm.doses_in_series),
        vaccine_cost: immunizationForm.vaccine_cost ? parseFloat(immunizationForm.vaccine_cost) : null,
        administration_fee: immunizationForm.administration_fee ? parseFloat(immunizationForm.administration_fee) : null
      };
      
      await axios.post(`${BACKEND_URL}/api/immunizations`, data);
      
      showMessage('success', 'Immunization recorded successfully!');
      setImmunizationForm({
        vaccine_name: '',
        vaccine_type: '',
        administration_date: new Date().toISOString().split('T')[0],
        dose_number: 1,
        route: 'Intramuscular',
        anatomical_site: 'Left deltoid',
        series_name: '',
        doses_in_series: 1,
        series_complete: false,
        administered_by: 'Nurse Smith',
        occupational_requirement: false,
        vaccine_cost: '',
        administration_fee: '50'
      });
      loadPatientImmunizations();
      loadImmunizationSummary();
    } catch (error) {
      showMessage('error', error.response?.data?.detail || 'Error creating immunization');
    } finally {
      setLoading(false);
    }
  };

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 5000);
  };

  const getComplianceColor = (status) => {
    const colors = {
      'compliant': 'bg-green-100 text-green-800',
      'overdue': 'bg-red-100 text-red-800',
      'pending': 'bg-yellow-100 text-yellow-800',
      'exempt': 'bg-gray-100 text-gray-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const quickVaccines = [
    { name: 'COVID-19 Pfizer', type: 'COVID-19', series: 'COVID-19 Primary Series', doses: 2 },
    { name: 'Influenza 2025', type: 'Influenza', series: '', doses: 1 },
    { name: 'Hepatitis B', type: 'Hepatitis B', series: 'Hepatitis B Series', doses: 3 },
    { name: 'Tetanus', type: 'Tetanus', series: '', doses: 1 }
  ];

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Syringe className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Immunizations</h1>
        </div>
        <p className="text-gray-600">Track vaccinations, doses, and occupational health requirements</p>
      </div>

      {/* Message Banner */}
      {message.text && (
        <div className={`mb-6 p-4 rounded-lg ${message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
          {message.text}
        </div>
      )}

      {/* Patient Selection */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Select Patient</h2>
        <select
          value={selectedPatient}
          onChange={(e) => setSelectedPatient(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value="">-- Select a patient --</option>
          {patients.map((patient) => (
            <option key={patient.id} value={patient.id}>
              {patient.first_name} {patient.last_name} ({patient.id_number})
            </option>
          ))}
        </select>
      </div>

      {selectedPatient && (
        <>
          {/* Summary Cards */}
          {summary && Object.keys(summary).length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              {Object.entries(summary).map(([vaccineType, data]) => (
                <div key={vaccineType} className="bg-white rounded-lg shadow-md p-4 border-l-4 border-blue-500">
                  <h3 className="font-semibold text-gray-800 mb-2">{vaccineType}</h3>
                  <div className="space-y-1 text-sm">
                    <p className="text-gray-600">Total doses: <span className="font-semibold">{data.total_doses}</span></p>
                    {data.last_dose_date && (
                      <p className="text-gray-600">Last: {new Date(data.last_dose_date).toLocaleDateString()}</p>
                    )}
                    {data.next_due_date && (
                      <p className="text-orange-600">Next due: {new Date(data.next_due_date).toLocaleDateString()}</p>
                    )}
                    {data.series_complete && (
                      <p className="text-green-600 font-semibold">✓ Series Complete</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Quick Vaccines */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <h3 className="font-semibold mb-3">Quick Add Common Vaccines:</h3>
            <div className="flex flex-wrap gap-2">
              {quickVaccines.map((vaccine) => (
                <button
                  key={vaccine.name}
                  onClick={() => setImmunizationForm({
                    ...immunizationForm,
                    vaccine_name: vaccine.name,
                    vaccine_type: vaccine.type,
                    series_name: vaccine.series,
                    doses_in_series: vaccine.doses,
                    series_complete: vaccine.doses === 1
                  })}
                  className="px-4 py-2 bg-white border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-100 text-sm"
                >
                  {vaccine.name}
                </button>
              ))}
            </div>
          </div>

          {/* Add Immunization Form */}
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <Plus className="w-5 h-5" />
              Record Immunization
            </h2>
            <form onSubmit={createImmunization} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-1">Vaccine Name *</label>
                  <input
                    type="text"
                    value={immunizationForm.vaccine_name}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, vaccine_name: e.target.value })}
                    placeholder="e.g., Pfizer-BioNTech COVID-19"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Vaccine Type</label>
                  <input
                    type="text"
                    value={immunizationForm.vaccine_type}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, vaccine_type: e.target.value })}
                    placeholder="e.g., COVID-19, Influenza"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Administration Date *</label>
                  <input
                    type="date"
                    value={immunizationForm.administration_date}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, administration_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Dose Number</label>
                  <input
                    type="number"
                    min="1"
                    value={immunizationForm.dose_number}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, dose_number: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Doses in Series</label>
                  <input
                    type="number"
                    min="1"
                    value={immunizationForm.doses_in_series}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, doses_in_series: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Route</label>
                  <select
                    value={immunizationForm.route}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, route: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="Intramuscular">Intramuscular</option>
                    <option value="Subcutaneous">Subcutaneous</option>
                    <option value="Oral">Oral</option>
                    <option value="Intranasal">Intranasal</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Anatomical Site</label>
                  <select
                    value={immunizationForm.anatomical_site}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, anatomical_site: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="Left deltoid">Left deltoid</option>
                    <option value="Right deltoid">Right deltoid</option>
                    <option value="Left thigh">Left thigh</option>
                    <option value="Right thigh">Right thigh</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Administered By</label>
                  <input
                    type="text"
                    value={immunizationForm.administered_by}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, administered_by: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Vaccine Cost (R)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={immunizationForm.vaccine_cost}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, vaccine_cost: e.target.value })}
                    placeholder="250.00"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Admin Fee (R)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={immunizationForm.administration_fee}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, administration_fee: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
              </div>
              
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={immunizationForm.series_complete}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, series_complete: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">Series Complete</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={immunizationForm.occupational_requirement}
                    onChange={(e) => setImmunizationForm({ ...immunizationForm, occupational_requirement: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">Occupational Requirement</span>
                </label>
              </div>
              
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
              >
                Record Immunization
              </button>
            </form>
          </div>

          {/* Immunizations List */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Immunization History</h2>
            
            {loading ? (
              <div className="text-center py-8 text-gray-500">Loading...</div>
            ) : immunizations.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Syringe className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No immunizations recorded yet</p>
              </div>
            ) : (
              <div className="space-y-3">
                {immunizations.map((imm) => (
                  <div key={imm.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-lg">{imm.vaccine_name}</h3>
                          {imm.occupational_requirement && (
                            <Shield className="w-4 h-4 text-blue-600" title="Occupational Requirement" />
                          )}
                          {imm.series_complete && (
                            <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">Series Complete</span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm text-gray-600">
                          <div>
                            <Calendar className="w-3 h-3 inline mr-1" />
                            {new Date(imm.administration_date).toLocaleDateString()}
                          </div>
                          {imm.dose_number && (
                            <div>Dose {imm.dose_number}/{imm.doses_in_series || '?'}</div>
                          )}
                          <div>{imm.route}</div>
                          <div>{imm.anatomical_site}</div>
                        </div>
                        {imm.administered_by && (
                          <p className="text-sm text-gray-600 mt-1">By: {imm.administered_by}</p>
                        )}
                        {imm.next_dose_due && !imm.series_complete && (
                          <p className="text-sm text-orange-600 mt-1">
                            Next dose due: {new Date(imm.next_dose_due).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default ImmunizationsTestPage;
