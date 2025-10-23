import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Activity, FileText, Pill, FlaskConical, FolderOpen, Calendar, AlertCircle, Heart, TrendingUp, Plus, Upload, Sparkles } from 'lucide-react';
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
  const [conditions, setConditions] = useState([]);
  const [medications, setMedications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [expandedEncounters, setExpandedEncounters] = useState({});

  useEffect(() => {
    loadPatientData();
  }, [patientId]);

  const loadPatientData = async () => {
    try {
      setLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const [patientRes, encountersRes, conditionsRes, medicationsRes] = await Promise.all([
        patientAPI.get(patientId),
        encounterAPI.listByPatient(patientId),
        fetch(`${backendUrl}/api/patients/${patientId}/conditions`).then(r => r.json()),
        fetch(`${backendUrl}/api/patients/${patientId}/medications`).then(r => r.json())
      ]);
      
      setPatient(patientRes.data);
      setEncounters(encountersRes.data);
      setConditions(conditionsRes.conditions || []);
      setMedications(medicationsRes.medications || []);
      
      console.log('Loaded conditions:', conditionsRes.conditions);
      console.log('Loaded medications:', medicationsRes.medications);
      
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
          <div className="flex gap-3">
            <Link to={`/patients/${patientId}/ai-scribe`}>
              <Button variant="outline" className="shadow-md gap-2 bg-purple-50 border-purple-300 hover:bg-purple-100">
                <Sparkles className="w-4 h-4 text-purple-600" />
                <span className="text-purple-700">AI Scribe</span>
              </Button>
            </Link>
            <Link to={`/patients/${patientId}/prescriptions`}>
              <Button variant="outline" className="shadow-md gap-2 bg-blue-50 border-blue-300 hover:bg-blue-100">
                <Pill className="w-4 h-4 text-blue-600" />
                <span className="text-blue-700">Prescriptions</span>
              </Button>
            </Link>
            <Link to={`/patients/${patientId}/documents`}>
              <Button variant="outline" className="shadow-md gap-2">
                <FolderOpen className="w-4 h-4" />
                View Documents
              </Button>
            </Link>
            <Link to={`/encounters/new/${patientId}`}>
              <Button className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white shadow-md">
                <Plus className="w-4 h-4 mr-2" />
                New Encounter
              </Button>
            </Link>
          </div>
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
                  <div className="space-y-6">
                    {encounters.length > 0 ? (
                      (() => {
                        // State to track expanded encounters
                        const [expandedEncounters, setExpandedEncounters] = React.useState({});
                        
                        const toggleEncounter = (encounterId) => {
                          setExpandedEncounters(prev => ({
                            ...prev,
                            [encounterId]: !prev[encounterId]
                          }));
                        };

                        // Group encounters by date
                        const groupedEncounters = encounters.reduce((groups, encounter) => {
                          const date = new Date(encounter.encounter_date).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                          });
                          if (!groups[date]) groups[date] = [];
                          groups[date].push(encounter);
                          return groups;
                        }, {});

                        return Object.entries(groupedEncounters).map(([date, encountersForDate]) => (
                          <div key={date}>
                            {/* Date Header - Compact Style */}
                            <div className="flex items-center gap-2 mb-3">
                              <div className="w-2 h-2 rounded-full bg-teal-500"></div>
                              <h3 className="text-sm font-bold text-slate-700">{date}</h3>
                            </div>
                            
                            {/* Timeline entries for this date - Compact */}
                            <div className="ml-3 pl-4 border-l-2 border-slate-200 space-y-3 pb-4">
                              {encountersForDate.map((encounter) => {
                                const isExpanded = expandedEncounters[encounter.id];
                                
                                // Extract diagnosis from GP notes
                                const diagnosis = encounter.gp_notes ? 
                                  encounter.gp_notes.split('\n')[0].substring(0, 80) + (encounter.gp_notes.length > 80 ? '...' : '') 
                                  : 'No diagnosis recorded';

                                return (
                                  <div key={encounter.id} className="space-y-2">
                                    {/* Compact info */}
                                    <div className="text-sm">
                                      <p className="text-slate-600">
                                        <span className="font-medium text-slate-800">Dr. [Provider Name]</span>
                                      </p>
                                      <p className="text-slate-700">
                                        <span className="font-semibold">Complaint:</span> {encounter.chief_complaint || 'General consultation'}
                                      </p>
                                      <p className="text-slate-700">
                                        <span className="font-semibold">Diagnosis:</span> {diagnosis}
                                      </p>
                                    </div>

                                    {/* Expandable details */}
                                    {isExpanded && (
                                      <div className="mt-3 p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
                                        <div>
                                          <p className="text-xs font-semibold text-slate-600 mb-1">Time:</p>
                                          <p className="text-sm text-slate-800">
                                            {new Date(encounter.encounter_date).toLocaleTimeString('en-US', {
                                              hour: '2-digit',
                                              minute: '2-digit'
                                            })}
                                          </p>
                                        </div>
                                        
                                        {encounter.vitals_json && (
                                          <div>
                                            <p className="text-xs font-semibold text-slate-600 mb-1">Vitals:</p>
                                            <div className="flex gap-4 text-sm text-slate-700">
                                              {encounter.vitals_json.blood_pressure && (
                                                <span><strong>BP:</strong> {encounter.vitals_json.blood_pressure}</span>
                                              )}
                                              {encounter.vitals_json.heart_rate && (
                                                <span><strong>HR:</strong> {encounter.vitals_json.heart_rate} bpm</span>
                                              )}
                                              {encounter.vitals_json.weight && (
                                                <span><strong>WT:</strong> {encounter.vitals_json.weight} kg</span>
                                              )}
                                            </div>
                                          </div>
                                        )}

                                        {encounter.gp_notes && (
                                          <div>
                                            <p className="text-xs font-semibold text-slate-600 mb-1">Full Notes:</p>
                                            <p className="text-sm text-slate-700 whitespace-pre-wrap">{encounter.gp_notes}</p>
                                          </div>
                                        )}

                                        <Badge className={encounter.status === 'completed' ? 'bg-emerald-500 text-white' : 'bg-amber-500 text-white'}>
                                          {encounter.status}
                                        </Badge>
                                      </div>
                                    )}

                                    {/* View Details button */}
                                    <button
                                      onClick={() => toggleEncounter(encounter.id)}
                                      className="text-xs text-teal-600 hover:text-teal-700 font-medium flex items-center gap-1"
                                    >
                                      {isExpanded ? '▼ Hide Details' : '▶ View Details'}
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ));
                      })()
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
              <div className="space-y-6">
                {encounters.length > 0 ? (
                  (() => {
                    // Group encounters by date
                    const groupedEncounters = encounters.reduce((groups, encounter) => {
                      const date = new Date(encounter.encounter_date).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                      });
                      if (!groups[date]) groups[date] = [];
                      groups[date].push(encounter);
                      return groups;
                    }, {});

                    return Object.entries(groupedEncounters).map(([date, encountersForDate]) => (
                      <div key={date} className="space-y-3">
                        {/* Date Header */}
                        <div className="flex items-center gap-3">
                          <div className="flex-shrink-0 w-2 h-2 bg-teal-500 rounded-full"></div>
                          <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">{date}</h3>
                          <div className="flex-1 h-px bg-slate-200"></div>
                        </div>
                        
                        {/* Encounters for this date */}
                        <div className="space-y-3 ml-5 border-l-2 border-slate-200 pl-4">
                          {encountersForDate.map((encounter) => (
                            <div key={encounter.id} className="p-4 bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg border border-slate-200">
                              <div className="flex items-center justify-between mb-3">
                                <div>
                                  <Badge className="bg-blue-100 text-blue-700 mb-2">General Consultation</Badge>
                                  <p className="font-semibold text-slate-800">{encounter.chief_complaint || 'General consultation'}</p>
                                  <p className="text-xs text-slate-500">
                                    {new Date(encounter.encounter_date).toLocaleTimeString('en-US', {
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
                        </div>
                      </div>
                    ));
                  })()
                ) : (
                  <p className="text-slate-400 text-center py-8">No visits recorded</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 3: Vitals & Labs */}
        <TabsContent value="vitals" className="mt-6">
          <div className="space-y-6">
            {/* Vitals Trends Chart */}
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <CardTitle className="text-lg font-bold text-slate-800">Vital Signs Trends</CardTitle>
              </CardHeader>
              <CardContent>
                <ReactECharts option={vitalsChartOption} style={{ height: '400px' }} />
              </CardContent>
            </Card>

            {/* Recent Lab Results */}
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <CardTitle className="text-lg font-bold text-slate-800">Recent Lab Results</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {mockLabResults.map((lab, idx) => (
                    <div key={idx} className="flex items-center justify-between p-4 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors">
                      <div className="flex-1">
                        <p className="font-semibold text-slate-800">{lab.test}</p>
                        <p className="text-sm text-slate-600">Normal range: {lab.range}</p>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="font-bold text-lg text-slate-800">{lab.value}</p>
                          <p className="text-sm text-slate-600">{lab.unit}</p>
                        </div>
                        <Badge className={
                          lab.status === 'high' ? 'bg-red-100 text-red-700' :
                          lab.status === 'low' ? 'bg-amber-100 text-amber-700' :
                          'bg-emerald-100 text-emerald-700'
                        }>
                          {lab.status}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 4: Medications */}
        <TabsContent value="medications" className="mt-6">
          <Card className="border-0 shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg font-bold text-slate-800">Medication History</CardTitle>
              <Button className="bg-gradient-to-r from-teal-500 to-cyan-600 text-white">
                <Plus className="w-4 h-4 mr-2" />
                Add Medication
              </Button>
            </CardHeader>
            <CardContent>
              {/* Active Medications */}
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-slate-800 mb-4">Active Medications</h3>
                <div className="space-y-6">
                  {medications.filter(m => m.status === 'active').length > 0 ? (
                    (() => {
                      // Group medications by date
                      const groupedByDate = medications
                        .filter(m => m.status === 'active')
                        .reduce((groups, med) => {
                          const date = med.start_date || 'Unknown Date';
                          if (!groups[date]) groups[date] = [];
                          groups[date].push(med);
                          return groups;
                        }, {});
                      
                      // Sort dates descending
                      const sortedDates = Object.keys(groupedByDate).sort((a, b) => {
                        if (a === 'Unknown Date') return 1;
                        if (b === 'Unknown Date') return -1;
                        return new Date(b) - new Date(a);
                      });
                      
                      return sortedDates.map((date) => (
                        <div key={date} className="border-l-4 border-emerald-500 pl-4">
                          <div className="flex items-center gap-2 mb-3">
                            <Calendar className="w-4 h-4 text-emerald-600" />
                            <h4 className="font-bold text-slate-700">
                              {date !== 'Unknown Date' 
                                ? new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
                                : 'Unknown Date'}
                            </h4>
                            <Badge className="bg-emerald-100 text-emerald-700">
                              {groupedByDate[date].length} medication{groupedByDate[date].length > 1 ? 's' : ''}
                            </Badge>
                          </div>
                          <div className="space-y-2">
                            {groupedByDate[date].map((med, idx) => (
                              <div key={idx} className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
                                <div className="flex items-start justify-between">
                                  <div className="flex-1">
                                    <h5 className="font-bold text-slate-800 mb-2">{med.medication_name}</h5>
                                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                                      {med.dosage && (
                                        <div>
                                          <span className="text-slate-600">Dosage:</span>
                                          <span className="ml-2 font-semibold text-slate-800">{med.dosage}</span>
                                        </div>
                                      )}
                                      {med.frequency && (
                                        <div>
                                          <span className="text-slate-600">Frequency:</span>
                                          <span className="ml-2 font-semibold text-slate-800">{med.frequency}</span>
                                        </div>
                                      )}
                                    </div>
                                    {med.notes && med.notes !== 'Imported from scanned document' && (
                                      <div className="mt-2 text-xs text-slate-600 italic">
                                        {med.notes}
                                      </div>
                                    )}
                                  </div>
                                  <Pill className="w-6 h-6 text-emerald-600" />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ));
                    })()
                  ) : (
                    <p className="text-slate-500 italic">No active medications on record</p>
                  )}
                </div>
              </div>

              {/* Discontinued Medications */}
              <div>
                <h3 className="text-lg font-semibold text-slate-800 mb-4">Discontinued Medications</h3>
                <div className="space-y-3">
                  {medications.filter(m => m.status === 'discontinued' || m.status === 'inactive').length > 0 ? (
                    medications.filter(m => m.status === 'discontinued' || m.status === 'inactive').map((med, idx) => (
                      <div key={idx} className="p-5 bg-slate-50 rounded-lg border border-slate-200 opacity-75">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <Badge className="bg-slate-400">Discontinued</Badge>
                              <h4 className="text-lg font-bold text-slate-600">{med.medication_name}</h4>
                            </div>
                            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                              <div>
                                <span className="text-slate-500">Dosage:</span>
                                <span className="ml-2 font-semibold text-slate-600">{med.dosage || 'Not specified'}</span>
                              </div>
                              <div>
                                <span className="text-slate-500">End Date:</span>
                                <span className="ml-2 font-semibold text-slate-600">{med.end_date || 'Not specified'}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500 italic">No discontinued medications</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 5: Investigations */}
        <TabsContent value="investigations" className="mt-6">
          <Card className="border-0 shadow-lg">
            <CardHeader>
              <CardTitle className="text-lg font-bold text-slate-800">Investigations & Procedures</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {mockInvestigations.map((inv, idx) => (
                  <div key={idx} className="p-5 bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg border border-slate-200">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Badge className={
                            inv.type === 'Laboratory' ? 'bg-purple-100 text-purple-700' :
                            inv.type === 'Imaging' ? 'bg-blue-100 text-blue-700' :
                            'bg-cyan-100 text-cyan-700'
                          }>
                            {inv.type}
                          </Badge>
                          <Badge className="bg-emerald-100 text-emerald-700">{inv.status}</Badge>
                        </div>
                        <h4 className="text-lg font-bold text-slate-800 mb-1">{inv.name}</h4>
                        <p className="text-sm text-slate-600">
                          Date: {new Date(inv.date).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                          })}
                        </p>
                      </div>
                      <FlaskConical className="w-8 h-8 text-slate-400" />
                    </div>
                    <div className="p-3 bg-white rounded border border-slate-200">
                      <p className="text-sm font-semibold text-slate-700 mb-1">Result:</p>
                      <p className="text-sm text-slate-600">{inv.result}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 6: Documents */}
        <TabsContent value="documents" className="mt-6">
          <Card className="border-0 shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg font-bold text-slate-800">Documents & Attachments</CardTitle>
              <Link to="/digitize">
                <Button className="bg-gradient-to-r from-teal-500 to-cyan-600 text-white">
                  <Upload className="w-4 h-4 mr-2" />
                  Upload Document
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {documents.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {documents.map((doc) => (
                    <div key={doc.document_id} className="p-5 bg-gradient-to-br from-slate-50 to-blue-50 rounded-lg border border-slate-200 hover:shadow-md transition-all cursor-pointer">
                      <div className="flex items-start gap-3">
                        <div className="w-12 h-12 rounded-lg bg-teal-100 flex items-center justify-center flex-shrink-0">
                          <FileText className="w-6 h-6 text-teal-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-slate-800 truncate">{doc.filename}</p>
                          <p className="text-xs text-slate-500 mt-1">
                            {new Date(doc.uploaded_at).toLocaleDateString()}
                          </p>
                          <Badge className={
                            doc.status === 'approved' ? 'bg-emerald-100 text-emerald-700 mt-2' :
                            'bg-amber-100 text-amber-700 mt-2'
                          }>
                            {doc.status}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <FolderOpen className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                  <p className="text-slate-500 text-lg">No documents uploaded</p>
                  <Link to="/digitize">
                    <Button className="mt-4 bg-gradient-to-r from-teal-500 to-cyan-600 text-white">
                      Upload First Document
                    </Button>
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
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
