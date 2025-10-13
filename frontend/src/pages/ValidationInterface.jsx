import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, FileText, Edit, DollarSign } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { validationAPI, encounterAPI, documentAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

const ValidationInterface = () => {
  const { encounterId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [encounter, setEncounter] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [validationNotes, setValidationNotes] = useState('');

  useEffect(() => {
    loadValidationData();
  }, [encounterId]);

  const loadValidationData = async () => {
    try {
      setLoading(true);
      const [encounterRes, docsRes] = await Promise.all([
        encounterAPI.get(encounterId),
        documentAPI.listByEncounter(encounterId)
      ]);
      setEncounter(encounterRes.data);
      setDocuments(docsRes.data || []);
      if (docsRes.data && docsRes.data.length > 0) {
        setSelectedDoc(docsRes.data[0]);
      }
    } catch (error) {
      console.error('Error loading validation data:', error);
      toast({
        title: 'Error',
        description: 'Failed to load validation data',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedDoc) return;

    try {
      await validationAPI.approve(selectedDoc.document_id, {
        parsed_data: selectedDoc.parsed_data,
        status: 'approved',
        notes: validationNotes
      });

      toast({
        title: 'Success',
        description: 'Document approved successfully'
      });

      loadValidationData();
    } catch (error) {
      console.error('Error approving document:', error);
      toast({
        title: 'Error',
        description: 'Failed to approve document',
        variant: 'destructive'
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-16 h-16 border-4 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!encounter) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500 text-lg">Encounter not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="validation-interface">
      {/* Header */}
      <div>
        <Link to={`/patients/${encounter.patient_id}`} className="inline-flex items-center text-teal-600 hover:text-teal-700 mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Patient
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-slate-800 mb-2">Validation Interface</h1>
            <p className="text-slate-600">Review and validate parsed medical documents</p>
          </div>
          <Link to={`/billing?encounter=${encounterId}`}>
            <Button 
              className="bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white shadow-md"
              data-testid="proceed-to-billing-btn"
            >
              <DollarSign className="w-4 h-4 mr-2" />
              Proceed to Billing
            </Button>
          </Link>
        </div>
      </div>

      {/* Encounter Info */}
      <Card className="border-0 shadow-lg bg-gradient-to-r from-teal-50 to-cyan-50">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-slate-500 mb-1">Encounter Date</p>
              <p className="text-base font-semibold text-slate-800">
                {new Date(encounter.encounter_date).toLocaleDateString()}
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-500 mb-1">Chief Complaint</p>
              <p className="text-base font-semibold text-slate-800">
                {encounter.chief_complaint || 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-500 mb-1">Status</p>
              <Badge className={encounter.status === 'completed' ? 'bg-emerald-500' : 'bg-amber-500'}>
                {encounter.status}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {documents.length === 0 ? (
        <Card className="border-0 shadow-lg">
          <CardContent className="py-12 text-center">
            <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 text-lg">No documents uploaded for this encounter</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Original Document Preview */}
          <Card className="border-0 shadow-lg">
            <CardHeader>
              <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Original Document
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedDoc && (
                <div className="space-y-4">
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <p className="text-sm text-slate-600 mb-1">Filename</p>
                    <p className="font-semibold text-slate-800">{selectedDoc.filename}</p>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <p className="text-sm text-slate-600 mb-1">Upload Date</p>
                    <p className="font-semibold text-slate-800">
                      {new Date(selectedDoc.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <p className="text-sm text-slate-600 mb-1">Status</p>
                    <Badge className={selectedDoc.status === 'approved' ? 'bg-emerald-500' : 'bg-amber-500'}>
                      {selectedDoc.status}
                    </Badge>
                  </div>
                  <div className="aspect-[8.5/11] bg-white border-2 border-slate-200 rounded-lg flex items-center justify-center">
                    <div className="text-center text-slate-400">
                      <FileText className="w-16 h-16 mx-auto mb-2" />
                      <p>PDF Preview</p>
                      <p className="text-xs">(Original document stored)</p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Right: Parsed Data */}
          <Card className="border-0 shadow-lg">
            <CardHeader>
              <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
                <Edit className="w-5 h-5" />
                Parsed Data
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedDoc && selectedDoc.parsed_data && (
                <div className="space-y-4">
                  {/* Patient Demographics */}
                  {selectedDoc.parsed_data.patient_demographics && (
                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                      <h3 className="font-semibold text-slate-800 mb-2">Patient Demographics</h3>
                      <div className="space-y-1 text-sm">
                        <p><span className="text-slate-600">Name:</span> <span className="font-medium">{selectedDoc.parsed_data.patient_demographics.name}</span></p>
                        <p><span className="text-slate-600">Age:</span> <span className="font-medium">{selectedDoc.parsed_data.patient_demographics.age}</span></p>
                        <p><span className="text-slate-600">Gender:</span> <span className="font-medium">{selectedDoc.parsed_data.patient_demographics.gender}</span></p>
                      </div>
                    </div>
                  )}

                  {/* Medical History */}
                  {selectedDoc.parsed_data.medical_history && selectedDoc.parsed_data.medical_history.length > 0 && (
                    <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                      <h3 className="font-semibold text-slate-800 mb-2">Medical History</h3>
                      <div className="space-y-2">
                        {selectedDoc.parsed_data.medical_history.map((item, idx) => (
                          <div key={idx} className="text-sm">
                            <p className="font-medium">{item.condition}</p>
                            <p className="text-slate-600">Diagnosed: {item.diagnosed_date}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Current Medications */}
                  {selectedDoc.parsed_data.current_medications && selectedDoc.parsed_data.current_medications.length > 0 && (
                    <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                      <h3 className="font-semibold text-slate-800 mb-2">Current Medications</h3>
                      <div className="space-y-2">
                        {selectedDoc.parsed_data.current_medications.map((med, idx) => (
                          <div key={idx} className="text-sm">
                            <p className="font-medium">{med.name}</p>
                            <p className="text-slate-600">{med.dosage} - {med.frequency}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Allergies */}
                  {selectedDoc.parsed_data.allergies && selectedDoc.parsed_data.allergies.length > 0 && (
                    <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                      <h3 className="font-semibold text-slate-800 mb-2">Allergies</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedDoc.parsed_data.allergies.map((allergy, idx) => (
                          <Badge key={idx} className="bg-red-500">{allergy}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Lab Results */}
                  {selectedDoc.parsed_data.lab_results && selectedDoc.parsed_data.lab_results.length > 0 && (
                    <div className="p-4 bg-amber-50 rounded-lg border border-amber-200">
                      <h3 className="font-semibold text-slate-800 mb-2">Lab Results</h3>
                      <div className="space-y-2">
                        {selectedDoc.parsed_data.lab_results.map((lab, idx) => (
                          <div key={idx} className="text-sm flex justify-between">
                            <span className="font-medium">{lab.test}</span>
                            <span className="text-slate-600">{lab.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Clinical Notes */}
                  {selectedDoc.parsed_data.clinical_notes && (
                    <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                      <h3 className="font-semibold text-slate-800 mb-2">Clinical Notes</h3>
                      <p className="text-sm text-slate-600">{selectedDoc.parsed_data.clinical_notes}</p>
                    </div>
                  )}

                  {/* Validation Notes */}
                  <div className="pt-4">
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Validation Notes
                    </label>
                    <Textarea
                      placeholder="Add any notes about the validation..."
                      value={validationNotes}
                      onChange={(e) => setValidationNotes(e.target.value)}
                      rows={3}
                      data-testid="validation-notes-input"
                    />
                  </div>

                  {/* Approve Button */}
                  <Button
                    onClick={handleApprove}
                    disabled={selectedDoc.status === 'approved'}
                    className="w-full bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
                    data-testid="approve-document-btn"
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    {selectedDoc.status === 'approved' ? 'Already Approved' : 'Approve Document'}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ValidationInterface;