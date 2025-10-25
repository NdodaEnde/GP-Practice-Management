import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { Plus, Heart, Trash2, Activity } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const VitalsManagement = ({ patientId }) => {
  const { toast } = useToast();
  const [vitals, setVitals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  
  // Form state
  const [measurementDate, setMeasurementDate] = useState(new Date().toISOString().split('T')[0]);
  const [bpSystolic, setBpSystolic] = useState('');
  const [bpDiastolic, setBpDiastolic] = useState('');
  const [heartRate, setHeartRate] = useState('');
  const [temperature, setTemperature] = useState('');
  const [respiratoryRate, setRespiratoryRate] = useState('');
  const [oxygenSaturation, setOxygenSaturation] = useState('');
  const [weight, setWeight] = useState('');
  const [height, setHeight] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (patientId) {
      fetchVitals();
    }
  }, [patientId]);

  const fetchVitals = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/vitals/patient/${patientId}`, {
        params: { limit: 20 }
      });
      setVitals(response.data || []);
    } catch (error) {
      console.error('Error fetching vitals:', error);
      toast({
        title: 'Error',
        description: 'Failed to load vitals',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const calculateBMI = () => {
    if (weight && height) {
      const heightM = parseFloat(height) / 100;
      const bmi = parseFloat(weight) / (heightM * heightM);
      return bmi.toFixed(1);
    }
    return null;
  };

  const handleAddVital = async (e) => {
    e.preventDefault();

    // At least one vital sign should be provided
    if (!bpSystolic && !heartRate && !temperature && !weight) {
      toast({
        title: 'Validation Error',
        description: 'Please provide at least one vital sign measurement',
        variant: 'destructive'
      });
      return;
    }

    setSaving(true);
    try {
      await axios.post(`${BACKEND_URL}/api/vitals`, {
        patient_id: patientId,
        measurement_date: measurementDate,
        blood_pressure_systolic: bpSystolic ? parseInt(bpSystolic) : null,
        blood_pressure_diastolic: bpDiastolic ? parseInt(bpDiastolic) : null,
        heart_rate: heartRate ? parseInt(heartRate) : null,
        temperature: temperature ? parseFloat(temperature) : null,
        respiratory_rate: respiratoryRate ? parseInt(respiratoryRate) : null,
        oxygen_saturation: oxygenSaturation ? parseInt(oxygenSaturation) : null,
        weight: weight ? parseFloat(weight) : null,
        height: height ? parseFloat(height) : null,
        notes: notes || null
      });

      toast({
        title: 'Success',
        description: 'Vital signs recorded successfully'
      });

      // Reset form
      setMeasurementDate(new Date().toISOString().split('T')[0]);
      setBpSystolic('');
      setBpDiastolic('');
      setHeartRate('');
      setTemperature('');
      setRespiratoryRate('');
      setOxygenSaturation('');
      setWeight('');
      setHeight('');
      setNotes('');
      setShowAddForm(false);

      // Refresh list
      fetchVitals();
    } catch (error) {
      console.error('Error adding vital:', error);
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to record vitals',
        variant: 'destructive'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (vitalId) => {
    if (!window.confirm('Are you sure you want to delete this vital signs record?')) {
      return;
    }

    try {
      await axios.delete(`${BACKEND_URL}/api/vitals/${vitalId}`);

      toast({
        title: 'Success',
        description: 'Vital signs deleted successfully'
      });

      fetchVitals();
    } catch (error) {
      console.error('Error deleting vital:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete vital signs',
        variant: 'destructive'
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Vital Signs History ({vitals.length} records)
          </CardTitle>
          <Button onClick={() => setShowAddForm(!showAddForm)} size="sm">
            <Plus className="w-4 h-4 mr-1" />
            Record Vitals
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add Vitals Form */}
        {showAddForm && (
          <Card className="border-2 border-green-200 bg-green-50">
            <CardContent className="pt-6">
              <form onSubmit={handleAddVital} className="space-y-4">
                <div>
                  <Label>Measurement Date</Label>
                  <Input
                    type="date"
                    value={measurementDate}
                    onChange={(e) => setMeasurementDate(e.target.value)}
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Blood Pressure (Systolic)</Label>
                    <Input
                      type="number"
                      value={bpSystolic}
                      onChange={(e) => setBpSystolic(e.target.value)}
                      placeholder="e.g., 120"
                    />
                  </div>
                  <div>
                    <Label>Blood Pressure (Diastolic)</Label>
                    <Input
                      type="number"
                      value={bpDiastolic}
                      onChange={(e) => setBpDiastolic(e.target.value)}
                      placeholder="e.g., 80"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Heart Rate (bpm)</Label>
                    <Input
                      type="number"
                      value={heartRate}
                      onChange={(e) => setHeartRate(e.target.value)}
                      placeholder="e.g., 72"
                    />
                  </div>
                  <div>
                    <Label>Temperature (°C)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={temperature}
                      onChange={(e) => setTemperature(e.target.value)}
                      placeholder="e.g., 36.5"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Respiratory Rate (breaths/min)</Label>
                    <Input
                      type="number"
                      value={respiratoryRate}
                      onChange={(e) => setRespiratoryRate(e.target.value)}
                      placeholder="e.g., 16"
                    />
                  </div>
                  <div>
                    <Label>Oxygen Saturation (%)</Label>
                    <Input
                      type="number"
                      value={oxygenSaturation}
                      onChange={(e) => setOxygenSaturation(e.target.value)}
                      placeholder="e.g., 98"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Weight (kg)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={weight}
                      onChange={(e) => setWeight(e.target.value)}
                      placeholder="e.g., 70.5"
                    />
                  </div>
                  <div>
                    <Label>Height (cm)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={height}
                      onChange={(e) => setHeight(e.target.value)}
                      placeholder="e.g., 175"
                    />
                  </div>
                </div>

                {weight && height && (
                  <Alert>
                    <AlertDescription>
                      <strong>Calculated BMI:</strong> {calculateBMI()}
                    </AlertDescription>
                  </Alert>
                )}

                <div>
                  <Label>Notes</Label>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Additional notes"
                    rows={2}
                  />
                </div>

                <div className="flex gap-2 justify-end">
                  <Button type="button" variant="outline" onClick={() => setShowAddForm(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={saving}>
                    {saving ? 'Saving...' : 'Record Vitals'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Vitals List */}
        {loading ? (
          <div className="text-center py-8 text-gray-500">Loading vitals...</div>
        ) : vitals.length === 0 ? (
          <Alert>
            <AlertDescription>No vital signs recorded for this patient.</AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-3">
            {vitals.map((vital) => (
              <Card key={vital.id} className="border-l-4 border-l-green-500">
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline">
                          {new Date(vital.measurement_date).toLocaleDateString()}
                        </Badge>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                        {vital.blood_pressure_systolic && (
                          <div>
                            <span className="text-gray-600">BP:</span>{' '}
                            <span className="font-semibold">
                              {vital.blood_pressure_systolic}/{vital.blood_pressure_diastolic} mmHg
                            </span>
                          </div>
                        )}
                        {vital.heart_rate && (
                          <div>
                            <span className="text-gray-600">HR:</span>{' '}
                            <span className="font-semibold">{vital.heart_rate} bpm</span>
                          </div>
                        )}
                        {vital.temperature && (
                          <div>
                            <span className="text-gray-600">Temp:</span>{' '}
                            <span className="font-semibold">{vital.temperature}°C</span>
                          </div>
                        )}
                        {vital.respiratory_rate && (
                          <div>
                            <span className="text-gray-600">RR:</span>{' '}
                            <span className="font-semibold">{vital.respiratory_rate} /min</span>
                          </div>
                        )}
                        {vital.oxygen_saturation && (
                          <div>
                            <span className="text-gray-600">SpO2:</span>{' '}
                            <span className="font-semibold">{vital.oxygen_saturation}%</span>
                          </div>
                        )}
                        {vital.weight && (
                          <div>
                            <span className="text-gray-600">Weight:</span>{' '}
                            <span className="font-semibold">{vital.weight} kg</span>
                          </div>
                        )}
                        {vital.height && (
                          <div>
                            <span className="text-gray-600">Height:</span>{' '}
                            <span className="font-semibold">{vital.height} cm</span>
                          </div>
                        )}
                        {vital.bmi && (
                          <div>
                            <span className="text-gray-600">BMI:</span>{' '}
                            <span className="font-semibold">{vital.bmi}</span>
                          </div>
                        )}
                      </div>
                      {vital.notes && (
                        <div className="text-sm text-gray-600 mt-2">
                          Notes: {vital.notes}
                        </div>
                      )}
                      <div className="text-xs text-gray-500 mt-2">
                        Recorded: {new Date(vital.created_at).toLocaleString()}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-500"
                      onClick={() => handleDelete(vital.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default VitalsManagement;
