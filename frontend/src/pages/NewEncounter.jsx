import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Upload, FileText, Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { patientAPI, encounterAPI, documentAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

const NewEncounter = () => {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [patient, setPatient] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const [encounterData, setEncounterData] = useState({
    chief_complaint: '',
    gp_notes: '',
    vitals: {
      blood_pressure: '',
      heart_rate: '',
      temperature: '',
      weight: '',
      height: '',
      oxygen_saturation: ''
    }
  });

  useEffect(() => {
    loadPatient();
  }, [patientId]);

  const loadPatient = async () => {
    try {
      const response = await patientAPI.get(patientId);
      setPatient(response.data);
    } catch (error) {
      console.error('Error loading patient:', error);
      toast({
        title: 'Error',
        description: 'Failed to load patient',
        variant: 'destructive'
      });
    }
  };

  const handleInputChange = (field, value) => {
    setEncounterData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleVitalsChange = (field, value) => {
    setEncounterData(prev => ({
      ...prev,
      vitals: {
        ...prev.vitals,
        [field]: value
      }
    }));
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Create encounter
      const encounterPayload = {
        patient_id: patientId,
        chief_complaint: encounterData.chief_complaint,
        gp_notes: encounterData.gp_notes,
        vitals: Object.values(encounterData.vitals).some(v => v) ? encounterData.vitals : null
      };

      const encounterRes = await encounterAPI.create(encounterPayload);
      const encounterId = encounterRes.data.id;

      // Upload document if selected
      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('encounter_id', encounterId);
        formData.append('patient_id', patientId);

        await documentAPI.upload(formData);
      }

      toast({
        title: 'Success',
        description: 'Encounter created successfully'
      });

      navigate(`/validation/${encounterId}`);
    } catch (error) {
      console.error('Error creating encounter:', error);
      toast({
        title: 'Error',
        description: 'Failed to create encounter',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  if (!patient) {
    return <div className="flex justify-center py-12">
      <div className="w-12 h-12 border-4 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
    </div>;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in" data-testid="new-encounter-container">
      <div>
        <Link to={`/patients/${patientId}`} className="inline-flex items-center text-teal-600 hover:text-teal-700 mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Patient
        </Link>
        <h1 className="text-4xl font-bold text-slate-800 mb-2">New Encounter</h1>
        <p className="text-slate-600">
          Patient: {patient.first_name} {patient.last_name}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Chief Complaint */}
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800">Chief Complaint</CardTitle>
          </CardHeader>
          <CardContent>
            <Input
              placeholder="What is the main reason for today's visit?"
              value={encounterData.chief_complaint}
              onChange={(e) => handleInputChange('chief_complaint', e.target.value)}
              data-testid="chief-complaint-input"
            />
          </CardContent>
        </Card>

        {/* Vitals */}
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              Vital Signs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <Label>Blood Pressure</Label>
                <Input
                  placeholder="120/80"
                  value={encounterData.vitals.blood_pressure}
                  onChange={(e) => handleVitalsChange('blood_pressure', e.target.value)}
                  data-testid="vitals-bp"
                />
              </div>
              <div>
                <Label>Heart Rate (bpm)</Label>
                <Input
                  type="number"
                  placeholder="72"
                  value={encounterData.vitals.heart_rate}
                  onChange={(e) => handleVitalsChange('heart_rate', e.target.value)}
                  data-testid="vitals-hr"
                />
              </div>
              <div>
                <Label>Temperature (°C)</Label>
                <Input
                  type="number"
                  step="0.1"
                  placeholder="36.5"
                  value={encounterData.vitals.temperature}
                  onChange={(e) => handleVitalsChange('temperature', e.target.value)}
                  data-testid="vitals-temp"
                />
              </div>
              <div>
                <Label>Weight (kg)</Label>
                <Input
                  type="number"
                  step="0.1"
                  placeholder="70"
                  value={encounterData.vitals.weight}
                  onChange={(e) => handleVitalsChange('weight', e.target.value)}
                  data-testid="vitals-weight"
                />
              </div>
              <div>
                <Label>Height (cm)</Label>
                <Input
                  type="number"
                  placeholder="170"
                  value={encounterData.vitals.height}
                  onChange={(e) => handleVitalsChange('height', e.target.value)}
                  data-testid="vitals-height"
                />
              </div>
              <div>
                <Label>O2 Saturation (%)</Label>
                <Input
                  type="number"
                  placeholder="98"
                  value={encounterData.vitals.oxygen_saturation}
                  onChange={(e) => handleVitalsChange('oxygen_saturation', e.target.value)}
                  data-testid="vitals-o2"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* GP Notes */}
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800">GP Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="Clinical notes, observations, treatment plan..."
              rows={6}
              value={encounterData.gp_notes}
              onChange={(e) => handleInputChange('gp_notes', e.target.value)}
              data-testid="gp-notes-textarea"
            />
          </CardContent>
        </Card>

        {/* Document Upload */}
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Upload Medical Document
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center hover:border-teal-400 transition-colors duration-200">
              <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
              <input
                type="file"
                id="file-upload"
                className="hidden"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileSelect}
                data-testid="file-upload-input"
              />
              <label
                htmlFor="file-upload"
                className="cursor-pointer text-teal-600 hover:text-teal-700 font-medium"
              >
                Click to upload
              </label>
              <p className="text-sm text-slate-500 mt-2">
                or drag and drop (PDF, JPG, PNG up to 10MB)
              </p>
              {selectedFile && (
                <div className="mt-4 p-3 bg-teal-50 rounded-lg">
                  <p className="text-sm font-medium text-teal-700">Selected: {selectedFile.name}</p>
                  <p className="text-xs text-teal-600 mt-1">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-4">
              Documents will be automatically parsed and available for validation
            </p>
          </CardContent>
        </Card>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <Link to={`/patients/${patientId}`}>
            <Button type="button" variant="outline" data-testid="cancel-encounter-btn">
              Cancel
            </Button>
          </Link>
          <Button
            type="submit"
            disabled={loading}
            className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
            data-testid="create-encounter-btn"
          >
            {loading ? 'Creating...' : 'Create Encounter'}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default NewEncounter;