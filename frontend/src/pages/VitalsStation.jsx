import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';
import {
  Activity,
  Heart,
  Thermometer,
  Wind,
  User,
  Search,
  Save,
  CheckCircle,
  AlertCircle,
  TrendingUp,
  Users
} from 'lucide-react';

const VitalsStation = () => {
  const { toast } = useToast();
  
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [queuePatients, setQueuePatients] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // Vitals state
  const [vitals, setVitals] = useState({
    systolic: '',
    diastolic: '',
    heart_rate: '',
    temperature: '',
    weight: '',
    height: '',
    oxygen_saturation: ''
  });

  useEffect(() => {
    fetchQueuePatients();
    // Refresh queue every 30 seconds
    const interval = setInterval(fetchQueuePatients, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchQueuePatients = async () => {
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      const response = await axios.get(`${backendUrl}/api/queue/current?station=vitals`);
      setQueuePatients(response.data.queue || []);
    } catch (error) {
      console.error('Error fetching queue:', error);
    }
  };

  const searchPatients = async () => {
    if (!searchQuery.trim()) return;
    
    try {
      setIsSearching(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const response = await axios.get(
        `${backendUrl}/api/patients?search=${encodeURIComponent(searchQuery)}`
      );

      setSearchResults(response.data || []);
    } catch (error) {
      console.error('Error searching patients:', error);
      toast({
        title: "Error",
        description: "Failed to search patients",
        variant: "destructive"
      });
    } finally {
      setIsSearching(false);
    }
  };

  const selectPatient = async (patient, queueEntry = null) => {
    // If no queue entry provided, try to find it
    if (!queueEntry && patient.id) {
      try {
        const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
        const response = await axios.get(`${backendUrl}/api/queue/current`);
        const allQueueEntries = response.data.queue || [];
        
        // Find queue entry for this patient
        const foundEntry = allQueueEntries.find(entry => entry.patient_id === patient.id);
        if (foundEntry) {
          queueEntry = foundEntry;
          console.log('✅ Found queue entry for patient:', foundEntry);
        } else {
          console.log('⚠️ No queue entry found for patient');
        }
      } catch (error) {
        console.error('Error fetching queue entry:', error);
      }
    }
    
    setSelectedPatient({ ...patient, queueEntry });
    setSearchQuery('');
    setSearchResults([]);
    // Reset vitals
    setVitals({
      systolic: '',
      diastolic: '',
      heart_rate: '',
      temperature: '',
      weight: '',
      height: '',
      oxygen_saturation: ''
    });
  };

  const calculateBMI = () => {
    if (vitals.weight && vitals.height) {
      const weightKg = parseFloat(vitals.weight);
      const heightM = parseFloat(vitals.height) / 100; // Convert cm to m
      if (weightKg > 0 && heightM > 0) {
        const bmi = (weightKg / (heightM * heightM)).toFixed(1);
        return bmi;
      }
    }
    return null;
  };

  const getBMICategory = (bmi) => {
    if (!bmi) return '';
    const bmiNum = parseFloat(bmi);
    if (bmiNum < 18.5) return 'Underweight';
    if (bmiNum < 25) return 'Normal';
    if (bmiNum < 30) return 'Overweight';
    return 'Obese';
  };

  const handleSaveVitals = async () => {
    if (!selectedPatient) {
      toast({
        title: "Error",
        description: "Please select a patient first",
        variant: "destructive"
      });
      return;
    }

    // Validate at least one vital is entered
    const hasVitals = Object.values(vitals).some(v => v !== '');
    if (!hasVitals) {
      toast({
        title: "Error",
        description: "Please enter at least one vital sign",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsSaving(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      // Prepare vitals data
      const vitalsData = {
        blood_pressure: vitals.systolic && vitals.diastolic 
          ? `${vitals.systolic}/${vitals.diastolic}` 
          : null,
        heart_rate: vitals.heart_rate ? parseInt(vitals.heart_rate) : null,
        temperature: vitals.temperature ? parseFloat(vitals.temperature) : null,
        weight: vitals.weight ? parseFloat(vitals.weight) : null,
        height: vitals.height ? parseFloat(vitals.height) : null,
        oxygen_saturation: vitals.oxygen_saturation ? parseInt(vitals.oxygen_saturation) : null
      };

      // Create a quick encounter for vitals
      const encounterData = {
        patient_id: selectedPatient.id,
        encounter_date: new Date().toISOString(),
        status: 'completed',
        chief_complaint: 'Vitals recording',
        vitals_json: vitalsData
      };

      await axios.post(`${backendUrl}/api/encounters`, encounterData);

      // Update queue status if patient is from queue
      if (selectedPatient.queueEntry) {
        await axios.put(
          `${backendUrl}/api/queue/${selectedPatient.queueEntry.id}/update-status`,
          {
            status: 'waiting',
            station: 'consultation',
            notes: 'Vitals recorded'
          }
        );
      }

      toast({
        title: "Success",
        description: `Vitals saved for ${selectedPatient.first_name} ${selectedPatient.last_name}`,
      });

      // Reset form
      setSelectedPatient(null);
      setVitals({
        systolic: '',
        diastolic: '',
        heart_rate: '',
        temperature: '',
        weight: '',
        height: '',
        oxygen_saturation: ''
      });

      // Refresh queue
      fetchQueuePatients();
      
    } catch (error) {
      console.error('Error saving vitals:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to save vitals",
        variant: "destructive"
      });
    } finally {
      setIsSaving(false);
    }
  };

  const bmi = calculateBMI();
  const bmiCategory = getBMICategory(bmi);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Vitals Station</h1>
          <p className="text-gray-600">Record patient vital signs quickly and efficiently</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Vitals Entry Panel */}
          <div className="lg:col-span-2 space-y-6">
            {/* Patient Selection */}
            {!selectedPatient && (
              <Card>
                <CardHeader>
                  <CardTitle>Select Patient</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Search */}
                  <div className="flex gap-3">
                    <div className="flex-1 relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                      <Input
                        placeholder="Search by name, ID number..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && searchPatients()}
                        className="pl-10"
                      />
                    </div>
                    <Button onClick={searchPatients} disabled={isSearching}>
                      {isSearching ? 'Searching...' : 'Search'}
                    </Button>
                  </div>

                  {/* Search Results */}
                  {searchResults.length > 0 && (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      <p className="text-sm font-medium text-gray-600">Search Results:</p>
                      {searchResults.map((patient) => (
                        <div
                          key={patient.id}
                          onClick={() => selectPatient(patient)}
                          className="p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                        >
                          <p className="font-semibold text-gray-900">
                            {patient.first_name} {patient.last_name}
                          </p>
                          <p className="text-sm text-gray-600">ID: {patient.id_number}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Queue Patients */}
                  {queuePatients.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium text-gray-600 flex items-center gap-2">
                        <Users className="w-4 h-4" />
                        Waiting in Queue:
                      </p>
                      {queuePatients.slice(0, 5).map((entry) => (
                        <div
                          key={entry.id}
                          onClick={() => {
                            // Find full patient details
                            const patient = {
                              id: entry.patient_id,
                              first_name: entry.patient_name.split(' ')[0],
                              last_name: entry.patient_name.split(' ').slice(1).join(' ')
                            };
                            selectPatient(patient, entry);
                          }}
                          className="p-3 border rounded-lg hover:bg-teal-50 cursor-pointer transition-colors flex items-center justify-between"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-teal-500 rounded-full flex items-center justify-center text-white font-bold">
                              {entry.queue_number}
                            </div>
                            <div>
                              <p className="font-semibold text-gray-900">{entry.patient_name}</p>
                              <p className="text-sm text-gray-600">{entry.reason_for_visit}</p>
                            </div>
                          </div>
                          <Badge className="bg-teal-100 text-teal-800">
                            Next
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Vitals Entry Form */}
            {selectedPatient && (
              <>
                {/* Selected Patient Info */}
                <Card className="bg-teal-50 border-2 border-teal-200">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-teal-500 rounded-full flex items-center justify-center">
                          <User className="w-6 h-6 text-white" />
                        </div>
                        <div>
                          <h3 className="text-xl font-bold text-gray-900">
                            {selectedPatient.first_name} {selectedPatient.last_name}
                          </h3>
                          {selectedPatient.queueEntry && (
                            <p className="text-sm text-gray-600">
                              Queue #{selectedPatient.queueEntry.queue_number}
                            </p>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        onClick={() => setSelectedPatient(null)}
                      >
                        Change Patient
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Vitals Input */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="w-5 h-5" />
                      Record Vital Signs
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-6">
                      {/* Blood Pressure */}
                      <div className="col-span-2">
                        <Label className="text-base font-semibold mb-2 flex items-center gap-2">
                          <Heart className="w-5 h-5 text-red-500" />
                          Blood Pressure (mmHg)
                        </Label>
                        <div className="flex gap-3 items-center">
                          <Input
                            type="number"
                            placeholder="Systolic"
                            value={vitals.systolic}
                            onChange={(e) => setVitals({...vitals, systolic: e.target.value})}
                            className="text-2xl h-16 text-center"
                          />
                          <span className="text-2xl font-bold text-gray-400">/</span>
                          <Input
                            type="number"
                            placeholder="Diastolic"
                            value={vitals.diastolic}
                            onChange={(e) => setVitals({...vitals, diastolic: e.target.value})}
                            className="text-2xl h-16 text-center"
                          />
                        </div>
                      </div>

                      {/* Heart Rate */}
                      <div>
                        <Label className="text-base font-semibold mb-2 flex items-center gap-2">
                          <Activity className="w-5 h-5 text-pink-500" />
                          Heart Rate (bpm)
                        </Label>
                        <Input
                          type="number"
                          placeholder="72"
                          value={vitals.heart_rate}
                          onChange={(e) => setVitals({...vitals, heart_rate: e.target.value})}
                          className="text-2xl h-16 text-center"
                        />
                      </div>

                      {/* Temperature */}
                      <div>
                        <Label className="text-base font-semibold mb-2 flex items-center gap-2">
                          <Thermometer className="w-5 h-5 text-orange-500" />
                          Temperature (°C)
                        </Label>
                        <Input
                          type="number"
                          step="0.1"
                          placeholder="36.5"
                          value={vitals.temperature}
                          onChange={(e) => setVitals({...vitals, temperature: e.target.value})}
                          className="text-2xl h-16 text-center"
                        />
                      </div>

                      {/* Weight */}
                      <div>
                        <Label className="text-base font-semibold mb-2 flex items-center gap-2">
                          <TrendingUp className="w-5 h-5 text-blue-500" />
                          Weight (kg)
                        </Label>
                        <Input
                          type="number"
                          step="0.1"
                          placeholder="70"
                          value={vitals.weight}
                          onChange={(e) => setVitals({...vitals, weight: e.target.value})}
                          className="text-2xl h-16 text-center"
                        />
                      </div>

                      {/* Height */}
                      <div>
                        <Label className="text-base font-semibold mb-2 flex items-center gap-2">
                          <TrendingUp className="w-5 h-5 text-green-500" />
                          Height (cm)
                        </Label>
                        <Input
                          type="number"
                          placeholder="170"
                          value={vitals.height}
                          onChange={(e) => setVitals({...vitals, height: e.target.value})}
                          className="text-2xl h-16 text-center"
                        />
                      </div>

                      {/* Oxygen Saturation */}
                      <div className="col-span-2">
                        <Label className="text-base font-semibold mb-2 flex items-center gap-2">
                          <Wind className="w-5 h-5 text-cyan-500" />
                          Oxygen Saturation (%)
                        </Label>
                        <Input
                          type="number"
                          placeholder="98"
                          value={vitals.oxygen_saturation}
                          onChange={(e) => setVitals({...vitals, oxygen_saturation: e.target.value})}
                          className="text-2xl h-16 text-center"
                        />
                      </div>

                      {/* BMI Display */}
                      {bmi && (
                        <div className="col-span-2 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm font-medium text-gray-600">Body Mass Index (BMI)</p>
                              <p className="text-3xl font-bold text-blue-600">{bmi}</p>
                            </div>
                            <Badge className="bg-blue-100 text-blue-800 text-lg px-4 py-2">
                              {bmiCategory}
                            </Badge>
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Save Button */}
                <Button
                  onClick={handleSaveVitals}
                  disabled={isSaving}
                  className="w-full bg-teal-600 hover:bg-teal-700 h-14 text-lg"
                >
                  {isSaving ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="w-5 h-5 mr-2" />
                      Save Vitals & Send to Consultation
                    </>
                  )}
                </Button>
              </>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Quick Guide</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex items-start gap-2">
                  <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <p>Select patient from queue or search</p>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <p>Enter vital signs in large input fields</p>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <p>BMI calculated automatically</p>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <p>Patient sent to consultation automatically</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Normal Ranges</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">BP:</span>
                  <span className="font-medium">120/80 mmHg</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">HR:</span>
                  <span className="font-medium">60-100 bpm</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Temp:</span>
                  <span className="font-medium">36.5-37.5°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">O2 Sat:</span>
                  <span className="font-medium">95-100%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">BMI:</span>
                  <span className="font-medium">18.5-24.9</span>
                </div>
              </CardContent>
            </Card>

            {queuePatients.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Queue Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center">
                    <p className="text-4xl font-bold text-teal-600">{queuePatients.length}</p>
                    <p className="text-sm text-gray-600">Patients waiting</p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VitalsStation;
