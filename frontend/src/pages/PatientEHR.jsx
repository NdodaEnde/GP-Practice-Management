import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Activity, FileText, Pill, FlaskConical, FolderOpen, Calendar, AlertCircle, Heart, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import ReactECharts from 'echarts-for-react';
import { patientAPI, encounterAPI, documentAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

const PatientEHR = () => {
  const { patientId } = useParams();
  const { toast } = useToast();
  const [patient, setPatient] = useState(null);
  const [encounters, setEncounters] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    loadPatientData();
  }, [patientId]);

  const loadPatientData = async () => {
    try {
      setLoading(true);
      const [patientRes, encountersRes] = await Promise.all([
        patientAPI.get(patientId),
        encounterAPI.listByPatient(patientId)
      ]);
      setPatient(patientRes.data);
      setEncounters(encountersRes.data);
      
      // Load documents for all encounters
      if (encountersRes.data.length > 0) {
        const allDocs = [];
        for (const enc of encountersRes.data) {
          try {
            const docsRes = await documentAPI.listByEncounter(enc.id);
            allDocs.push(...docsRes.data);
          } catch (err) {
            console.log('No documents for encounter', enc.id);
          }
        }
        setDocuments(allDocs);
      }
    } catch (error) {
      console.error('Error loading patient:', error);
      toast({
        title: 'Error',
        description: 'Failed to load patient data',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  // Mock data for demonstrations (replace with real data from API)
  const mockVitalsData = [
    { date: '2024-09', systolic: 128, diastolic: 82 },
    { date: '2024-10', systolic: 135, diastolic: 85 },
    { date: '2024-11', systolic: 132, diastolic: 84 },
    { date: '2024-12', systolic: 130, diastolic: 83 },
    { date: '2025-01', systolic: 133, diastolic: 85 },
  ];

  const mockMedications = [
    {
      name: 'Metformin',
      dosage: '500mg',
      frequency: 'Twice daily',
      startDate: '2024-01-15',
      prescriber: 'Dr. Sarah Johnson',
      status: 'active'
    },
    {
      name: 'Lisinopril',
      dosage: '10mg',
      frequency: 'Once daily',
      startDate: '2024-01-15',
      prescriber: 'Dr. Sarah Johnson',
      status: 'active'
    },
    {
      name: 'Aspirin',
      dosage: '81mg',
      frequency: 'Once daily',
      startDate: '2023-06-20',
      endDate: '2024-01-10',
      prescriber: 'Dr. Michael Chen',
      status: 'discontinued'
    }
  ];

  const mockInvestigations = [
    {
      name: 'Complete Blood Count',
      type: 'Laboratory',
      date: '2025-01-15',
      status: 'Completed',
      result: 'All values within normal range'
    },
    {
      name: 'Chest X-ray',
      type: 'Imaging',
      date: '2024-12-20',
      status: 'Completed',
      result: 'Clear lung fields, no acute findings'
    },
    {
      name: 'Echocardiogram',
      type: 'Procedure',
      date: '2024-11-10',
      status: 'Completed',
      result: 'Normal cardiac function, EF 60%'
    }
  ];

  const mockLabResults = [
    { test: 'HbA1c', value: '6.8', unit: '%', date: '2025-01-15', range: '4.0-6.0', status: 'high' },
    { test: 'Fasting Glucose', value: '110', unit: 'mg/dL', date: '2025-01-15', range: '70-100', status: 'high' },
    { test: 'Total Cholesterol', value: '195', unit: 'mg/dL', date: '2025-01-15', range: '<200', status: 'normal' },
    { test: 'HDL Cholesterol', value: '55', unit: 'mg/dL', date: '2025-01-15', range: '>40', status: 'normal' },
    { test: 'LDL Cholesterol', value: '120', unit: 'mg/dL', date: '2025-01-15', range: '<100', status: 'high' },
    { test: 'Triglycerides', value: '145', unit: 'mg/dL', date: '2025-01-15', range: '<150', status: 'normal' },
  ];

  const vitalsChartOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['Systolic', 'Diastolic'],
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: mockVitalsData.map(d => d.date)
    },
    yAxis: {
      type: 'value',
      name: 'mmHg',
      min: 60,
      max: 160
    },
    series: [
      {
        name: 'Systolic',
        type: 'line',
        data: mockVitalsData.map(d => d.systolic),
        smooth: true,
        itemStyle: { color: '#0891b2' },
        areaStyle: { opacity: 0.1 }
      },
      {
        name: 'Diastolic',
        type: 'line',
        data: mockVitalsData.map(d => d.diastolic),
        smooth: true,
        itemStyle: { color: '#14b8a6' },
        areaStyle: { opacity: 0.1 }
      }
    ]
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-16 h-16 border-4 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500 text-lg">Patient not found</p>
        <Link to="/patients">
          <Button className="mt-4">Back to Patients</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="patient-ehr-container">
      {/* Header */}
      <div>
        <Link to="/patients" className="inline-flex items-center text-teal-600 hover:text-teal-700 mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Patients
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center text-white font-bold text-3xl shadow-lg">
              {patient.first_name[0]}{patient.last_name[0]}
            </div>
            <div>
              <h1 className="text-4xl font-bold text-slate-800">
                {patient.first_name} {patient.last_name}
              </h1>
              <p className="text-slate-600">ID: {patient.id_number} • DOB: {patient.dob}</p>
            </div>
          </div>
          <Link to={`/encounters/new/${patientId}`}>
            <Button className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white shadow-md">
              <Plus className="w-4 h-4 mr-2" />
              New Encounter
            </Button>
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-6 h-auto bg-slate-100">
          <TabsTrigger value="overview" className="flex items-center gap-2 py-3" data-testid="tab-overview">
            <Activity className="w-4 h-4" />
            <span className="hidden sm:inline">Overview</span>
          </TabsTrigger>
          <TabsTrigger value="visits" className="flex items-center gap-2 py-3" data-testid="tab-visits">
            <Calendar className="w-4 h-4" />
            <span className="hidden sm:inline">Visits</span>
          </TabsTrigger>
          <TabsTrigger value="vitals" className="flex items-center gap-2 py-3" data-testid="tab-vitals">
            <TrendingUp className="w-4 h-4" />
            <span className="hidden sm:inline">Vitals & Labs</span>
          </TabsTrigger>
          <TabsTrigger value="medications" className="flex items-center gap-2 py-3" data-testid="tab-medications">
            <Pill className="w-4 h-4" />
            <span className="hidden sm:inline">Medications</span>
          </TabsTrigger>
          <TabsTrigger value="investigations" className="flex items-center gap-2 py-3" data-testid="tab-investigations">
            <FlaskConical className="w-4 h-4" />
            <span className="hidden sm:inline">Investigations</span>
          </TabsTrigger>
          <TabsTrigger value="documents" className="flex items-center gap-2 py-3" data-testid="tab-documents">
            <FolderOpen className="w-4 h-4" />
            <span className="hidden sm:inline">Documents</span>
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Overview */}
        <TabsContent value="overview" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Patient Info & Vitals */}
            <div className="lg:col-span-1 space-y-6">
              {/* Basic Info */}
              <Card className="border-0 shadow-lg">
                <CardHeader>
                  <CardTitle className="text-lg font-bold text-slate-800">Patient Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-sm text-slate-500">Contact</p>
                    <p className="font-semibold text-slate-800">{patient.contact_number || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Email</p>
                    <p className="font-semibold text-slate-800">{patient.email || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Address</p>
                    <p className="font-semibold text-slate-800">{patient.address || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Medical Aid</p>
                    {patient.medical_aid ? (
                      <Badge className="bg-violet-100 text-violet-700">{patient.medical_aid}</Badge>
                    ) : (
                      <p className="text-slate-400">None</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Current Vitals */}
              <Card className="border-0 shadow-lg">
                <CardHeader>
                  <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Heart className="w-5 h-5 text-red-500" />
                    Current Vitals
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {encounters.length > 0 && encounters[0].vitals_json ? (
                      <>
                        <VitalDisplay label="Blood Pressure" value={encounters[0].vitals_json.blood_pressure} unit="mmHg" />
                        <VitalDisplay label="Heart Rate" value={encounters[0].vitals_json.heart_rate} unit="bpm" />
                        <VitalDisplay label="Temperature" value={encounters[0].vitals_json.temperature} unit="°C" />
                        <VitalDisplay label="Weight" value={encounters[0].vitals_json.weight} unit="kg" />
                        <VitalDisplay label="O2 Saturation" value={encounters[0].vitals_json.oxygen_saturation} unit="%" />
                      </>
                    ) : (
                      <p className="text-slate-400 text-center py-4">No recent vitals</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Allergies & Alerts */}
              <Card className="border-0 shadow-lg border-l-4 border-l-red-500">
                <CardHeader>
                  <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-red-500" />
                    Allergies & Alerts
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                      <div className="flex items-center gap-2">
                        <Badge className="bg-red-500">Severe</Badge>
                        <span className="font-semibold text-red-800">Penicillin</span>
                      </div>
                      <p className="text-sm text-red-600 mt-1">Anaphylaxis reaction</p>
                    </div>
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                      <div className="flex items-center gap-2">
                        <Badge className="bg-amber-500">Moderate</Badge>
                        <span className="font-semibold text-amber-800">Latex</span>
                      </div>
                      <p className="text-sm text-amber-600 mt-1">Contact dermatitis</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Timeline */}
            <div className="lg:col-span-2">
              <Card className="border-0 shadow-lg">
                <CardHeader>
                  <CardTitle className="text-lg font-bold text-slate-800">Patient Timeline</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {encounters.length > 0 ? (
                      encounters.map((encounter, idx) => (
                        <div key={encounter.id} className="relative pl-8 pb-4 border-l-2 border-teal-200">
                          <div className="absolute left-0 top-0 -translate-x-1/2 w-4 h-4 rounded-full bg-teal-500"></div>
                          <div className="bg-gradient-to-r from-slate-50 to-blue-50 p-4 rounded-lg">
                            <div className="flex items-start justify-between mb-2">
                              <div>
                                <Badge className="bg-teal-100 text-teal-700 mb-2">Visit</Badge>
                                <p className="font-semibold text-slate-800">{encounter.chief_complaint || 'General Consultation'}</p>
                                <p className="text-sm text-slate-600">
                                  {new Date(encounter.encounter_date).toLocaleDateString('en-US', {
                                    year: 'numeric',
                                    month: 'long',
                                    day: 'numeric'
                                  })}
                                </p>
                              </div>
                              <Badge className={encounter.status === 'completed' ? 'bg-emerald-500' : 'bg-amber-500'}>
                                {encounter.status}
                              </Badge>
                            </div>
                            {encounter.gp_notes && (
                              <p className="text-sm text-slate-600 mt-2">{encounter.gp_notes}</p>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-400 text-center py-8">No encounters recorded</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Visits */}
        <TabsContent value="visits" className="mt-6">
          <Card className="border-0 shadow-lg">
            <CardHeader>
              <CardTitle className="text-lg font-bold text-slate-800">Consultation History</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {encounters.map((encounter) => (
                  <div key={encounter.id} className="p-5 bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg border border-slate-200">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <Badge className="bg-blue-100 text-blue-700 mb-2">General Consultation</Badge>
                        <p className="font-semibold text-slate-800">{encounter.chief_complaint || 'General consultation'}</p>
                        <p className="text-sm text-slate-600">
                          {new Date(encounter.encounter_date).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </p>
                      </div>
                      <Badge className={encounter.status === 'completed' ? 'bg-emerald-500' : 'bg-amber-500'}>
                        {encounter.status}
                      </Badge>
                    </div>
                    {encounter.gp_notes && (
                      <div className="mt-3 p-3 bg-white rounded border border-slate-200">
                        <p className="text-sm font-semibold text-slate-700 mb-1">Assessment & Plan:</p>
                        <p className="text-sm text-slate-600">{encounter.gp_notes}</p>
                      </div>
                    )}
                    {encounter.vitals_json && (
                      <div className="mt-3 flex gap-4 text-sm">
                        {encounter.vitals_json.blood_pressure && (
                          <span className="text-slate-600">
                            <strong>BP:</strong> {encounter.vitals_json.blood_pressure}
                          </span>
                        )}
                        {encounter.vitals_json.heart_rate && (
                          <span className="text-slate-600">
                            <strong>HR:</strong> {encounter.vitals_json.heart_rate} bpm
                          </span>
                        )}
                        {encounter.vitals_json.weight && (
                          <span className="text-slate-600">
                            <strong>WT:</strong> {encounter.vitals_json.weight} kg
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {encounters.length === 0 && (
                  <p className="text-slate-400 text-center py-8">No visits recorded</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 3: Vitals & Labs - CONTINUED IN NEXT MESSAGE DUE TO LENGTH */}
      </Tabs>
    </div>
  );
};

// Helper Component
const VitalDisplay = ({ label, value, unit }) => (
  <div className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
    <span className="text-sm text-slate-600">{label}</span>
    <span className="font-semibold text-slate-800">
      {value ? `${value} ${unit}` : 'N/A'}
    </span>
  </div>
);

export default PatientEHR;
