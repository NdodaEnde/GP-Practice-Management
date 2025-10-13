import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, UserPlus, UserCheck, AlertCircle, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import api from '@/services/api';
import { useToast } from '@/hooks/use-toast';

const DocumentDigitization = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [parsedData, setParsedData] = useState(null);
  const [parsedDocId, setParsedDocId] = useState(null);
  const [matchResult, setMatchResult] = useState(null);
  const [validatedData, setValidatedData] = useState(null);
  const [step, setStep] = useState('upload'); // 'upload', 'review', 'match', 'complete'

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('document_type', 'medical_record');

      const response = await api.post('/documents/upload-standalone', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setParsedData(response.data.parsed_data);
      setParsedDocId(response.data.parsed_doc_id);
      setValidatedData(response.data.parsed_data); // Initialize with parsed data
      setStep('review');

      toast({
        title: 'Success',
        description: 'Document uploaded and parsed successfully',
      });
    } catch (error) {
      console.error('Error uploading document:', error);
      toast({
        title: 'Error',
        description: 'Failed to upload document',
        variant: 'destructive',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleMatchPatient = async () => {
    try {
      const formData = new FormData();
      formData.append('parsed_doc_id', parsedDocId);
      
      // Extract identifiers from parsed data
      if (validatedData.patient_demographics) {
        const demo = validatedData.patient_demographics;
        if (demo.id_number) formData.append('id_number', demo.id_number);
        if (demo.first_name) formData.append('first_name', demo.first_name);
        if (demo.last_name) formData.append('last_name', demo.last_name);
        if (demo.dob) formData.append('dob', demo.dob);
      }

      const response = await api.post('/documents/match-patient', formData);
      setMatchResult(response.data);
      setStep('match');
    } catch (error) {
      console.error('Error matching patient:', error);
      toast({
        title: 'Error',
        description: 'Failed to match patient',
        variant: 'destructive',
      });
    }
  };

  const handleLinkToExisting = async (patientId) => {
    try {
      const formData = new FormData();
      formData.append('parsed_doc_id', parsedDocId);
      formData.append('patient_id', patientId);
      formData.append('create_encounter', 'true');
      formData.append('validated_data', JSON.stringify(validatedData));

      const response = await api.post('/documents/link-to-patient', formData);
      
      toast({
        title: 'Success',
        description: 'Document linked to existing patient',
      });

      navigate(`/patients/${patientId}`);
    } catch (error) {
      console.error('Error linking document:', error);
      toast({
        title: 'Error',
        description: 'Failed to link document',
        variant: 'destructive',
      });
    }
  };

  const handleCreateNewPatient = async () => {
    try {
      // Build patient data from validated demographics
      const demo = validatedData.patient_demographics;
      const patientData = {
        first_name: demo.first_name || demo.name?.split(' ')[0] || 'Unknown',
        last_name: demo.last_name || demo.name?.split(' ').slice(1).join(' ') || 'Unknown',
        dob: demo.dob || '1900-01-01',
        id_number: demo.id_number || 'UNKNOWN',
        contact_number: demo.contact_number || '',
        email: demo.email || '',
        address: demo.address || '',
        medical_aid: demo.medical_aid || '',
      };

      const formData = new FormData();
      formData.append('parsed_doc_id', parsedDocId);
      formData.append('patient_data', JSON.stringify(patientData));

      const response = await api.post('/documents/create-patient-from-document', formData);
      
      toast({
        title: 'Success',
        description: 'New patient created and document linked',
      });

      navigate(`/patients/${response.data.patient_id}`);
    } catch (error) {
      console.error('Error creating patient:', error);
      toast({
        title: 'Error',
        description: 'Failed to create patient',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="document-digitization">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-slate-800 mb-2">Document Digitization</h1>
        <p className="text-slate-600">Upload, parse, and match medical records to patient profiles</p>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-center gap-4 mb-8">
        {['upload', 'review', 'match', 'complete'].map((s, idx) => (
          <div key={s} className="flex items-center">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
              step === s ? 'bg-teal-500 text-white' : 
              ['upload', 'review', 'match'].indexOf(step) > idx ? 'bg-emerald-500 text-white' : 
              'bg-slate-200 text-slate-500'
            }`}>
              {['upload', 'review', 'match'].indexOf(step) > idx ? '✓' : idx + 1}
            </div>
            {idx < 3 && <div className="w-16 h-1 bg-slate-200 mx-2" />}
          </div>
        ))}
      </div>

      {/* Step 1: Upload */}
      {step === 'upload' && (
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <Upload className="w-5 h-5" />
              Step 1: Upload Medical Document
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed border-slate-300 rounded-lg p-12 text-center hover:border-teal-400 transition-colors duration-200">
              <Upload className="w-16 h-16 text-slate-400 mx-auto mb-4" />
              <input
                type="file"
                id="file-upload"
                className="hidden"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileSelect}
                data-testid="digitization-file-input"
              />
              <label
                htmlFor="file-upload"
                className="cursor-pointer text-teal-600 hover:text-teal-700 font-medium text-lg"
              >
                Click to upload medical document
              </label>
              <p className="text-sm text-slate-500 mt-3">
                Supports: PDF, JPG, PNG (up to 10MB)
              </p>
              {selectedFile && (
                <div className="mt-6 p-4 bg-teal-50 rounded-lg inline-block">
                  <p className="text-sm font-medium text-teal-700">Selected: {selectedFile.name}</p>
                  <p className="text-xs text-teal-600 mt-1">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              )}
            </div>

            {selectedFile && (
              <div className="mt-6 flex justify-center">
                <Button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white px-8 py-3 text-lg shadow-md hover:shadow-lg"
                  data-testid="upload-and-parse-btn"
                >
                  {uploading ? 'Uploading & Parsing...' : 'Upload & Parse Document'}
                </Button>
              </div>
            )}

            <Alert className="mt-6 border-blue-200 bg-blue-50">
              <AlertCircle className="w-4 h-4 text-blue-600" />
              <AlertDescription className="text-blue-800">
                Documents are stored for compliance. Parsed data will be extracted using AI and ready for validation.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Review & Edit Parsed Data */}
      {step === 'review' && parsedData && (
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Step 2: Review & Edit Extracted Data
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="demographics" className="w-full">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="demographics">Demographics</TabsTrigger>
                <TabsTrigger value="history">History</TabsTrigger>
                <TabsTrigger value="medications">Medications</TabsTrigger>
                <TabsTrigger value="allergies">Allergies</TabsTrigger>
                <TabsTrigger value="labs">Lab Results</TabsTrigger>
              </TabsList>

              <TabsContent value="demographics" className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Full Name</Label>
                    <Input
                      value={validatedData.patient_demographics?.name || ''}
                      onChange={(e) => setValidatedData({
                        ...validatedData,
                        patient_demographics: {...validatedData.patient_demographics, name: e.target.value}
                      })}
                    />
                  </div>
                  <div>
                    <Label>Age</Label>
                    <Input
                      type="number"
                      value={validatedData.patient_demographics?.age || ''}
                      onChange={(e) => setValidatedData({
                        ...validatedData,
                        patient_demographics: {...validatedData.patient_demographics, age: parseInt(e.target.value)}
                      })}
                    />
                  </div>
                  <div>
                    <Label>Gender</Label>
                    <Input
                      value={validatedData.patient_demographics?.gender || ''}
                      onChange={(e) => setValidatedData({
                        ...validatedData,
                        patient_demographics: {...validatedData.patient_demographics, gender: e.target.value}
                      })}
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="history">
                {validatedData.medical_history?.map((item, idx) => (
                  <div key={idx} className="p-3 bg-green-50 rounded-lg mb-2">
                    <p className="font-semibold">{item.condition}</p>
                    <p className="text-sm text-slate-600">Diagnosed: {item.diagnosed_date}</p>
                  </div>
                ))}
              </TabsContent>

              <TabsContent value="medications">
                {validatedData.current_medications?.map((med, idx) => (
                  <div key={idx} className="p-3 bg-purple-50 rounded-lg mb-2">
                    <p className="font-semibold">{med.name}</p>
                    <p className="text-sm text-slate-600">{med.dosage} - {med.frequency}</p>
                  </div>
                ))}
              </TabsContent>

              <TabsContent value="allergies">
                <div className="flex flex-wrap gap-2">
                  {validatedData.allergies?.map((allergy, idx) => (
                    <Badge key={idx} className="bg-red-500 text-white">{allergy}</Badge>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="labs">
                {validatedData.lab_results?.map((lab, idx) => (
                  <div key={idx} className="flex justify-between p-3 bg-amber-50 rounded-lg mb-2">
                    <span className="font-semibold">{lab.test}</span>
                    <span>{lab.value}</span>
                  </div>
                ))}
              </TabsContent>
            </Tabs>

            <div className="mt-6 flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => setStep('upload')}
              >
                Cancel
              </Button>
              <Button
                onClick={handleMatchPatient}
                className="bg-gradient-to-r from-teal-500 to-cyan-600 text-white"
                data-testid="proceed-to-match-btn"
              >
                Proceed to Patient Matching
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Patient Matching */}
      {step === 'match' && matchResult && (
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
              {matchResult.match_found ? <UserCheck className="w-5 h-5" /> : <UserPlus className="w-5 h-5" />}
              Step 3: Patient Matching
            </CardTitle>
          </CardHeader>
          <CardContent>
            {matchResult.match_found ? (
              <div>
                <Alert className="mb-4 border-emerald-200 bg-emerald-50">
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                  <AlertDescription className="text-emerald-800">
                    <strong>Existing patient found!</strong> Match type: {matchResult.match_type} ({matchResult.confidence} confidence)
                  </AlertDescription>
                </Alert>

                {matchResult.patient && (
                  <div className="p-4 bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg border border-slate-200 mb-4">
                    <h3 className="text-lg font-semibold text-slate-800 mb-2">
                      {matchResult.patient.first_name} {matchResult.patient.last_name}
                    </h3>
                    <div className="text-sm text-slate-600 space-y-1">
                      <p>ID: {matchResult.patient.id_number}</p>
                      <p>DOB: {matchResult.patient.dob}</p>
                      <p>Contact: {matchResult.patient.contact_number}</p>
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-3">
                  <Button
                    variant="outline"
                    onClick={() => setStep('review')}
                  >
                    Back to Review
                  </Button>
                  <Button
                    onClick={() => handleLinkToExisting(matchResult.patient.id)}
                    className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white"
                    data-testid="link-to-existing-btn"
                  >
                    Link to This Patient
                  </Button>
                </div>
              </div>
            ) : (
              <div>
                <Alert className="mb-4 border-amber-200 bg-amber-50">
                  <AlertCircle className="w-4 h-4 text-amber-600" />
                  <AlertDescription className="text-amber-800">
                    No existing patient found. This appears to be a new patient.
                  </AlertDescription>
                </Alert>

                <div className="p-4 bg-slate-50 rounded-lg mb-4">
                  <p className="text-slate-600">A new patient record will be created with the validated demographics data.</p>
                </div>

                <div className="flex justify-end gap-3">
                  <Button
                    variant="outline"
                    onClick={() => setStep('review')}
                  >
                    Back to Review
                  </Button>
                  <Button
                    onClick={handleCreateNewPatient}
                    className="bg-gradient-to-r from-teal-500 to-cyan-600 text-white"
                    data-testid="create-new-patient-btn"
                  >
                    <UserPlus className="w-4 h-4 mr-2" />
                    Create New Patient
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default DocumentDigitization;
