import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';
import PrescriptionBuilder from '@/components/PrescriptionBuilder';
import SickNoteBuilder from '@/components/SickNoteBuilder';
import ReferralBuilder from '@/components/ReferralBuilder';
import {
  Mic,
  Square,
  Save,
  Sparkles,
  User,
  ArrowLeft,
  Clock,
  FileText,
  Loader2,
  Pill,
  Send,
  Zap
} from 'lucide-react';

const AIScribe = () => {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [patient, setPatient] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [transcription, setTranscription] = useState('');
  const [soapNotes, setSoapNotes] = useState('');
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedData, setExtractedData] = useState(null);
  const [showPrescriptionBuilder, setShowPrescriptionBuilder] = useState(false);
  const [showSickNoteBuilder, setShowSickNoteBuilder] = useState(false);
  const [showReferralBuilder, setShowReferralBuilder] = useState(false);
  
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  useEffect(() => {
    if (patientId) {
      fetchPatient();
    }
  }, [patientId]);

  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
    
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRecording]);

  const fetchPatient = async () => {
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      const response = await axios.get(`${backendUrl}/api/patients/${patientId}`);
      setPatient(response.data);
    } catch (error) {
      console.error('Error fetching patient:', error);
      toast({
        title: "Error",
        description: "Failed to load patient details",
        variant: "destructive"
      });
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(track => track.stop());
        await transcribeAudio(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      toast({
        title: "Recording Started",
        description: "Speak clearly about the consultation",
      });
    } catch (error) {
      console.error('Error starting recording:', error);
      toast({
        title: "Error",
        description: "Could not access microphone. Please check permissions.",
        variant: "destructive"
      });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const transcribeAudio = async (audioBlob) => {
    try {
      setIsTranscribing(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const formData = new FormData();
      formData.append('file', audioBlob, 'consultation.webm');

      const response = await axios.post(
        `${backendUrl}/api/ai-scribe/transcribe`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      setTranscription(response.data.transcription);
      
      toast({
        title: "Transcription Complete",
        description: "Audio has been transcribed. Click 'Generate SOAP Notes' to continue.",
      });
    } catch (error) {
      console.error('Error transcribing audio:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to transcribe audio",
        variant: "destructive"
      });
    } finally {
      setIsTranscribing(false);
    }
  };

  const generateSOAPNotes = async () => {
    if (!transcription.trim()) {
      toast({
        title: "Error",
        description: "No transcription available. Please record consultation first.",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsGenerating(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const patientContext = patient ? {
        name: `${patient.first_name} ${patient.last_name}`,
        age: calculateAge(patient.dob),
      } : null;

      const response = await axios.post(
        `${backendUrl}/api/ai-scribe/generate-soap`,
        {
          transcription: transcription,
          patient_context: patientContext
        }
      );

      setSoapNotes(response.data.soap_notes);
      
      toast({
        title: "SOAP Notes Generated",
        description: "AI has generated structured notes. Review and save to encounter.",
      });
    } catch (error) {
      console.error('Error generating SOAP notes:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to generate SOAP notes",
        variant: "destructive"
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const extractClinicalActions = async () => {
    if (!soapNotes.trim()) {
      toast({
        title: "Error",
        description: "Generate SOAP notes first",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsExtracting(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const patientContext = patient ? {
        name: `${patient.first_name} ${patient.last_name}`,
        age: calculateAge(patient.dob),
      } : null;

      const response = await axios.post(
        `${backendUrl}/api/ai-scribe/extract-clinical-actions`,
        {
          soap_notes: soapNotes,
          patient_context: patientContext
        }
      );

      // Normalize keys to lowercase (GPT returns uppercase)
      const rawData = response.data.extracted_data;
      const normalized = {
        prescriptions: rawData.PRESCRIPTIONS || rawData.prescriptions || [],
        sick_note: rawData.SICK_NOTE || rawData.sick_note || null,
        referral: rawData.REFERRAL || rawData.referral || null
      };

      setExtractedData(normalized);
      
      toast({
        title: "Clinical Actions Extracted",
        description: "AI has extracted prescriptions, sick notes, and referrals from SOAP notes.",
      });
    } catch (error) {
      console.error('Error extracting clinical actions:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to extract clinical actions",
        variant: "destructive"
      });
    } finally {
      setIsExtracting(false);
    }
  };

  const saveToEncounter = async () => {
    if (!soapNotes.trim()) {
      toast({
        title: "Error",
        description: "No SOAP notes to save",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsSaving(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const consultationData = {
        patient_id: patientId,
        soap_notes: soapNotes,
        transcription: transcription,
        doctor_name: "Dr. Current User"
      };

      const response = await axios.post(
        `${backendUrl}/api/ai-scribe/save-consultation`,
        consultationData
      );

      toast({
        title: "Success",
        description: `Consultation saved to EHR. Diagnosis: ${response.data.diagnosis || 'N/A'}`,
      });

      // Navigate back to patient EHR
      navigate(`/patients/${patientId}`);
    } catch (error) {
      console.error('Error saving consultation:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to save consultation",
        variant: "destructive"
      });
    } finally {
      setIsSaving(false);
    }
  };

  const calculateAge = (dob) => {
    if (!dob) return null;
    const birthDate = new Date(dob);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    return age;
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <Button
            variant="ghost"
            onClick={() => navigate(`/patients/${patientId}`)}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Patient
          </Button>
          
          <h1 className="text-3xl font-bold text-gray-900 mb-2 flex items-center gap-2">
            <Sparkles className="w-8 h-8 text-teal-600" />
            AI Scribe - Consultation Notes
          </h1>
          <p className="text-gray-600">Record consultation and generate SOAP notes automatically</p>
        </div>

        {/* Patient Info */}
        {patient && (
          <Card className="mb-6 bg-teal-50 border-2 border-teal-200">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-teal-500 rounded-full flex items-center justify-center">
                  <User className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900">
                    {patient.first_name} {patient.last_name}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {calculateAge(patient.dob)} years • ID: {patient.id_number}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recording Panel */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mic className="w-5 h-5" />
                Voice Recording
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Recording Status */}
              {isRecording && (
                <div className="p-4 bg-red-50 border-2 border-red-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-3 h-3 bg-red-600 rounded-full animate-pulse"></div>
                      <span className="font-semibold text-red-900">Recording...</span>
                    </div>
                    <div className="flex items-center gap-2 text-red-900 font-mono text-lg">
                      <Clock className="w-5 h-5" />
                      {formatTime(recordingTime)}
                    </div>
                  </div>
                </div>
              )}

              {/* Recording Button */}
              <div className="flex justify-center">
                {!isRecording ? (
                  <Button
                    onClick={startRecording}
                    disabled={isTranscribing}
                    className="w-32 h-32 rounded-full bg-teal-600 hover:bg-teal-700 text-white"
                  >
                    <Mic className="w-12 h-12" />
                  </Button>
                ) : (
                  <Button
                    onClick={stopRecording}
                    className="w-32 h-32 rounded-full bg-red-600 hover:bg-red-700 text-white"
                  >
                    <Square className="w-12 h-12" />
                  </Button>
                )}
              </div>

              <p className="text-center text-sm text-gray-600">
                {!isRecording 
                  ? 'Click to start recording consultation' 
                  : 'Click to stop recording'}
              </p>

              {/* Transcription Status */}
              {isTranscribing && (
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
                    <span className="font-medium text-blue-900">Transcribing audio...</span>
                  </div>
                </div>
              )}

              {/* Transcription Display */}
              {transcription && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">Transcription:</label>
                  <Textarea
                    value={transcription}
                    onChange={(e) => setTranscription(e.target.value)}
                    className="min-h-[200px] font-mono text-sm"
                    placeholder="Transcription will appear here..."
                  />
                  
                  <Button
                    onClick={generateSOAPNotes}
                    disabled={isGenerating || !transcription.trim()}
                    className="w-full bg-teal-600 hover:bg-teal-700"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Generating SOAP Notes...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4 mr-2" />
                        Generate SOAP Notes
                      </>
                    )}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* SOAP Notes Panel */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                SOAP Notes
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {soapNotes ? (
                <>
                  <Textarea
                    value={soapNotes}
                    onChange={(e) => setSoapNotes(e.target.value)}
                    className="min-h-[400px] font-mono text-sm"
                    placeholder="SOAP notes will be generated here..."
                  />
                  
                  <div className="flex gap-3">
                    <Button
                      onClick={extractClinicalActions}
                      disabled={isExtracting}
                      className="flex-1 bg-purple-600 hover:bg-purple-700"
                    >
                      {isExtracting ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Extracting...
                        </>
                      ) : (
                        <>
                          <Zap className="w-4 h-4 mr-2" />
                          Auto-Extract Forms
                        </>
                      )}
                    </Button>
                    
                    <Button
                      onClick={saveToEncounter}
                      disabled={isSaving}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      {isSaving ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Save className="w-4 h-4 mr-2" />
                          Save to Encounter
                        </>
                      )}
                    </Button>
                  </div>
                  
                  {/* Extracted Clinical Actions Summary */}
                  {extractedData && (
                    <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
                      <h4 className="font-semibold text-purple-900 mb-2">✨ Extracted Clinical Actions:</h4>
                      <div className="space-y-1 text-sm text-purple-800">
                        {extractedData.prescriptions && extractedData.prescriptions.length > 0 && (
                          <div>• {extractedData.prescriptions.length} medication(s) found</div>
                        )}
                        {extractedData.sick_note && extractedData.sick_note.needed && (
                          <div>• Sick note needed ({extractedData.sick_note.days_off} days)</div>
                        )}
                        {extractedData.referral && extractedData.referral.needed && (
                          <div>• Referral to {extractedData.referral.specialist_type}</div>
                        )}
                      </div>
                      <p className="text-xs text-purple-600 mt-2">Click buttons below to review and create documents</p>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-20">
                  <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 mb-2">No SOAP notes yet</p>
                  <p className="text-sm text-gray-400">
                    Record consultation and click "Generate SOAP Notes"
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Phase 4.2: Smart Form Generation - Show after extraction */}
        {extractedData && (
          <div className="mt-8 space-y-6">
            <div className="border-t pt-6">
              <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                <Zap className="w-6 h-6 text-purple-600" />
                Smart Clinical Documentation
              </h2>
              <p className="text-gray-600 mb-6">
                AI-extracted forms ready for your review. Click to open, review, edit, and save.
              </p>
              
              {/* Action Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Prescription Card */}
                {extractedData.prescriptions && extractedData.prescriptions.length > 0 && (
                  <div className="text-center p-8 border-2 border-blue-300 bg-blue-50 rounded-lg">
                    <Pill className="w-12 h-12 text-blue-600 mx-auto mb-3" />
                    <h3 className="font-semibold mb-2">Prescriptions</h3>
                    <p className="text-sm text-gray-600 mb-2">
                      {extractedData.prescriptions.length} medication(s) extracted
                    </p>
                    <Badge variant="default" className="mb-4">Auto-filled</Badge>
                    <Button
                      onClick={() => setShowPrescriptionBuilder(true)}
                      className="w-full bg-blue-600 hover:bg-blue-700"
                    >
                      Review & Create
                    </Button>
                  </div>
                )}

                {/* Sick Note Card */}
                {extractedData.sick_note && extractedData.sick_note.needed && (
                  <div className="text-center p-8 border-2 border-green-300 bg-green-50 rounded-lg">
                    <FileText className="w-12 h-12 text-green-600 mx-auto mb-3" />
                    <h3 className="font-semibold mb-2">Sick Note</h3>
                    <p className="text-sm text-gray-600 mb-2">
                      {extractedData.sick_note.days_off} days off work
                    </p>
                    <Badge variant="default" className="mb-4 bg-green-600">Auto-filled</Badge>
                    <Button
                      onClick={() => setShowSickNoteBuilder(true)}
                      className="w-full bg-green-600 hover:bg-green-700"
                    >
                      Review & Create
                    </Button>
                  </div>
                )}

                {/* Referral Card */}
                {extractedData.referral && extractedData.referral.needed && (
                  <div className="text-center p-8 border-2 border-purple-300 bg-purple-50 rounded-lg">
                    <Send className="w-12 h-12 text-purple-600 mx-auto mb-3" />
                    <h3 className="font-semibold mb-2">Referral</h3>
                    <p className="text-sm text-gray-600 mb-2">
                      To: {extractedData.referral.specialist_type}
                    </p>
                    <Badge variant="default" className="mb-4 bg-purple-600">Auto-filled</Badge>
                    <Button
                      onClick={() => setShowReferralBuilder(true)}
                      className="w-full bg-purple-600 hover:bg-purple-700"
                    >
                      Review & Create
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Prescription Builder Dialog */}
        <Dialog open={showPrescriptionBuilder} onOpenChange={setShowPrescriptionBuilder}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Review Prescription (Auto-filled from SOAP)</DialogTitle>
            </DialogHeader>
            <PrescriptionBuilder
              patientId={patientId}
              doctorName="Dr. Current User"
              initialData={extractedData?.prescriptions || []}
              onSave={() => {
                setShowPrescriptionBuilder(false);
                toast({
                  title: "Success",
                  description: "Prescription saved successfully"
                });
              }}
            />
          </DialogContent>
        </Dialog>

        {/* Sick Note Builder Dialog */}
        <Dialog open={showSickNoteBuilder} onOpenChange={setShowSickNoteBuilder}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Review Sick Note (Auto-filled from SOAP)</DialogTitle>
            </DialogHeader>
            <SickNoteBuilder
              patientId={patientId}
              doctorName="Dr. Current User"
              initialData={extractedData?.sick_note || null}
              onSave={() => {
                setShowSickNoteBuilder(false);
                toast({
                  title: "Success",
                  description: "Sick note saved successfully"
                });
              }}
            />
          </DialogContent>
        </Dialog>

        {/* Referral Builder Dialog */}
        <Dialog open={showReferralBuilder} onOpenChange={setShowReferralBuilder}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Review Referral (Auto-filled from SOAP)</DialogTitle>
            </DialogHeader>
            <ReferralBuilder
              patientId={patientId}
              doctorName="Dr. Current User"
              initialData={extractedData?.referral || null}
              onSave={() => {
                setShowReferralBuilder(false);
                toast({
                  title: "Success",
                  description: "Referral saved successfully"
                });
              }}
            />
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default AIScribe;
