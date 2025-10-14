import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import PrescriptionBuilder from '../components/PrescriptionBuilder';
import SickNoteBuilder from '../components/SickNoteBuilder';
import ReferralBuilder from '../components/ReferralBuilder';
import {
  FileText,
  Pill,
  Send,
  Plus,
  Calendar,
  User,
  Clock,
  Download
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const PatientPrescriptions = () => {
  const { patientId } = useParams();
  const { toast } = useToast();
  const [patient, setPatient] = useState(null);
  const [prescriptions, setPrescriptions] = useState([]);
  const [sickNotes, setSickNotes] = useState([]);
  const [referrals, setReferrals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewPrescription, setShowNewPrescription] = useState(false);
  const [showNewSickNote, setShowNewSickNote] = useState(false);
  const [showNewReferral, setShowNewReferral] = useState(false);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  useEffect(() => {
    if (patientId) {
      fetchData();
    }
  }, [patientId]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch patient details
      const patientRes = await axios.get(`${backendUrl}/api/patients/${patientId}`);
      setPatient(patientRes.data.patient);

      // Fetch prescriptions
      const prescriptionsRes = await axios.get(`${backendUrl}/api/prescriptions/patient/${patientId}`);
      setPrescriptions(prescriptionsRes.data.prescriptions || []);

      // Fetch sick notes
      const sickNotesRes = await axios.get(`${backendUrl}/api/sick-notes/patient/${patientId}`);
      setSickNotes(sickNotesRes.data.sick_notes || []);

      // Fetch referrals
      const referralsRes = await axios.get(`${backendUrl}/api/referrals/patient/${patientId}`);
      setReferrals(referralsRes.data.referrals || []);

    } catch (error) {
      console.error('Error fetching data:', error);
      toast({
        title: "Error",
        description: "Failed to load patient data",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePrescriptionSaved = () => {
    setShowNewPrescription(false);
    fetchData();
  };

  const handleSickNoteSaved = () => {
    setShowNewSickNote(false);
    fetchData();
  };

  const handleReferralSaved = () => {
    setShowNewReferral(false);
    fetchData();
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-ZA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      {/* Patient Header */}
      {patient && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <User className="w-8 h-8 text-blue-600" />
                <div>
                  <h1 className="text-2xl font-bold">
                    {patient.first_name} {patient.last_name}
                  </h1>
                  <p className="text-gray-600">
                    DOB: {formatDate(patient.dob)} | ID: {patient.id_number}
                  </p>
                </div>
              </div>
            </div>
          </CardHeader>
        </Card>
      )}

      {/* Tabs for different document types */}
      <Tabs defaultValue="prescriptions" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="prescriptions" className="flex items-center gap-2">
            <Pill className="w-4 h-4" />
            Prescriptions ({prescriptions.length})
          </TabsTrigger>
          <TabsTrigger value="sick-notes" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Sick Notes ({sickNotes.length})
          </TabsTrigger>
          <TabsTrigger value="referrals" className="flex items-center gap-2">
            <Send className="w-4 h-4" />
            Referrals ({referrals.length})
          </TabsTrigger>
        </TabsList>

        {/* Prescriptions Tab */}
        <TabsContent value="prescriptions" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Prescriptions</h2>
            <Dialog open={showNewPrescription} onOpenChange={setShowNewPrescription}>
              <DialogTrigger asChild>
                <Button className="bg-blue-600 hover:bg-blue-700">
                  <Plus className="w-4 h-4 mr-2" />
                  New Prescription
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create New Prescription</DialogTitle>
                </DialogHeader>
                <PrescriptionBuilder
                  patientId={patientId}
                  doctorName="Dr. Current User"
                  onSave={handlePrescriptionSaved}
                />
              </DialogContent>
            </Dialog>
          </div>

          {prescriptions.length === 0 ? (
            <Card className="p-12 text-center">
              <Pill className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No prescriptions found</p>
            </Card>
          ) : (
            <div className="space-y-4">
              {prescriptions.map((prescription) => (
                <Card key={prescription.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">
                        Prescription - {formatDate(prescription.prescription_date)}
                      </CardTitle>
                      <Badge variant={prescription.status === 'active' ? 'default' : 'secondary'}>
                        {prescription.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600">Dr. {prescription.doctor_name}</p>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {prescription.items && prescription.items.map((item, idx) => (
                        <div key={idx} className="p-3 bg-gray-50 rounded-md">
                          <div className="flex justify-between items-start">
                            <div>
                              <p className="font-semibold">{item.medication_name}</p>
                              <p className="text-sm text-gray-600">
                                {item.dosage} - {item.frequency} - {item.duration}
                              </p>
                              {item.instructions && (
                                <p className="text-sm text-gray-500 mt-1">{item.instructions}</p>
                              )}
                            </div>
                            {item.quantity && (
                              <Badge variant="outline">{item.quantity}</Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    {prescription.notes && (
                      <div className="mt-3 p-3 bg-blue-50 rounded-md">
                        <p className="text-sm text-gray-700">{prescription.notes}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Sick Notes Tab */}
        <TabsContent value="sick-notes" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Sick Notes / Medical Certificates</h2>
            <Dialog open={showNewSickNote} onOpenChange={setShowNewSickNote}>
              <DialogTrigger asChild>
                <Button className="bg-green-600 hover:bg-green-700">
                  <Plus className="w-4 h-4 mr-2" />
                  New Sick Note
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create New Sick Note</DialogTitle>
                </DialogHeader>
                <SickNoteBuilder
                  patientId={patientId}
                  doctorName="Dr. Current User"
                  onSave={handleSickNoteSaved}
                />
              </DialogContent>
            </Dialog>
          </div>

          {sickNotes.length === 0 ? (
            <Card className="p-12 text-center">
              <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No sick notes found</p>
            </Card>
          ) : (
            <div className="space-y-4">
              {sickNotes.map((note) => (
                <Card key={note.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">
                        Sick Note - {formatDate(note.issue_date)}
                      </CardTitle>
                      <Badge variant={note.fitness_status === 'unfit' ? 'destructive' : 'default'}>
                        {note.fitness_status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600">Dr. {note.doctor_name}</p>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <p className="text-sm text-gray-500">Period</p>
                        <p className="font-semibold">
                          {formatDate(note.start_date)} to {formatDate(note.end_date)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Diagnosis</p>
                        <p className="font-semibold">{note.diagnosis}</p>
                      </div>
                    </div>
                    {note.restrictions && (
                      <div className="p-3 bg-yellow-50 rounded-md mb-3">
                        <p className="text-sm font-semibold text-yellow-800">Restrictions:</p>
                        <p className="text-sm text-yellow-700">{note.restrictions}</p>
                      </div>
                    )}
                    {note.additional_notes && (
                      <div className="p-3 bg-gray-50 rounded-md">
                        <p className="text-sm text-gray-700">{note.additional_notes}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Referrals Tab */}
        <TabsContent value="referrals" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Referral Letters</h2>
            <Dialog open={showNewReferral} onOpenChange={setShowNewReferral}>
              <DialogTrigger asChild>
                <Button className="bg-purple-600 hover:bg-purple-700">
                  <Plus className="w-4 h-4 mr-2" />
                  New Referral
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create New Referral</DialogTitle>
                </DialogHeader>
                <ReferralBuilder
                  patientId={patientId}
                  doctorName="Dr. Current User"
                  onSave={handleReferralSaved}
                />
              </DialogContent>
            </Dialog>
          </div>

          {referrals.length === 0 ? (
            <Card className="p-12 text-center">
              <Send className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No referrals found</p>
            </Card>
          ) : (
            <div className="space-y-4">
              {referrals.map((referral) => (
                <Card key={referral.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">
                        Referral to {referral.specialist_type}
                      </CardTitle>
                      <div className="flex gap-2">
                        <Badge variant={referral.urgency === 'urgent' ? 'destructive' : 'default'}>
                          {referral.urgency}
                        </Badge>
                        <Badge variant="outline">{referral.status}</Badge>
                      </div>
                    </div>
                    <p className="text-sm text-gray-600">
                      Dr. {referral.referring_doctor_name} | {formatDate(referral.referral_date)}
                    </p>
                  </CardHeader>
                  <CardContent>
                    {referral.specialist_name && (
                      <div className="mb-3">
                        <p className="text-sm text-gray-500">Referred to:</p>
                        <p className="font-semibold">
                          {referral.specialist_name}
                          {referral.specialist_practice && ` - ${referral.specialist_practice}`}
                        </p>
                      </div>
                    )}
                    <div className="mb-3">
                      <p className="text-sm text-gray-500">Reason for Referral:</p>
                      <p className="text-sm">{referral.reason_for_referral}</p>
                    </div>
                    <div className="mb-3">
                      <p className="text-sm text-gray-500">Clinical Findings:</p>
                      <p className="text-sm">{referral.clinical_findings}</p>
                    </div>
                    {referral.current_medications && (
                      <div className="p-3 bg-blue-50 rounded-md">
                        <p className="text-sm font-semibold text-blue-800">Current Medications:</p>
                        <p className="text-sm text-blue-700">{referral.current_medications}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PatientPrescriptions;
