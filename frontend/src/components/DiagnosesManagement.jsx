import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { Plus, Edit, Trash2, Search, FileText } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const DiagnosesManagement = ({ patientId }) => {
  const { toast } = useToast();
  const [diagnoses, setDiagnoses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  
  // Form state
  const [icd10Code, setIcd10Code] = useState('');
  const [description, setDescription] = useState('');
  const [diagnosisType, setDiagnosisType] = useState('primary');
  const [status, setStatus] = useState('active');
  const [onsetDate, setOnsetDate] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  // ICD-10 search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (patientId) {
      fetchDiagnoses();
    }
  }, [patientId]);

  const fetchDiagnoses = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/diagnoses/patient/${patientId}`);
      setDiagnoses(response.data || []);
    } catch (error) {
      console.error('Error fetching diagnoses:', error);
      toast({
        title: 'Error',
        description: 'Failed to load diagnoses',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const searchICD10 = async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/icd10/search`, {
        params: {
          query: query,
          limit: 10,
          clinical_use_only: true
        }
      });
      setSearchResults(response.data || []);
    } catch (error) {
      console.error('Error searching ICD-10 codes:', error);
    } finally {
      setSearching(false);
    }
  };

  const selectICD10Code = (code) => {
    setIcd10Code(code.code);
    setDescription(code.who_full_desc);
    setSearchResults([]);
    setSearchQuery('');
  };

  const handleAddDiagnosis = async (e) => {
    e.preventDefault();

    if (!icd10Code || !description) {
      toast({
        title: 'Validation Error',
        description: 'ICD-10 code and description are required',
        variant: 'destructive'
      });
      return;
    }

    setSaving(true);
    try {
      await axios.post(`${BACKEND_URL}/api/diagnoses`, {
        patient_id: patientId,
        icd10_code: icd10Code,
        diagnosis_description: description,
        diagnosis_type: diagnosisType,
        status: status,
        onset_date: onsetDate || null,
        notes: notes || null
      });

      toast({
        title: 'Success',
        description: 'Diagnosis added successfully'
      });

      // Reset form
      setIcd10Code('');
      setDescription('');
      setDiagnosisType('primary');
      setStatus('active');
      setOnsetDate('');
      setNotes('');
      setShowAddForm(false);

      // Refresh list
      fetchDiagnoses();
    } catch (error) {
      console.error('Error adding diagnosis:', error);
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to add diagnosis',
        variant: 'destructive'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateStatus = async (diagnosisId, newStatus) => {
    try {
      await axios.patch(`${BACKEND_URL}/api/diagnoses/${diagnosisId}`, {
        status: newStatus
      });

      toast({
        title: 'Success',
        description: `Diagnosis status updated to ${newStatus}`
      });

      fetchDiagnoses();
    } catch (error) {
      console.error('Error updating diagnosis:', error);
      toast({
        title: 'Error',
        description: 'Failed to update diagnosis status',
        variant: 'destructive'
      });
    }
  };

  const handleDelete = async (diagnosisId) => {
    if (!window.confirm('Are you sure you want to delete this diagnosis?')) {
      return;
    }

    try {
      await axios.delete(`${BACKEND_URL}/api/diagnoses/${diagnosisId}`);

      toast({
        title: 'Success',
        description: 'Diagnosis deleted successfully'
      });

      fetchDiagnoses();
    } catch (error) {
      console.error('Error deleting diagnosis:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete diagnosis',
        variant: 'destructive'
      });
    }
  };

  const getStatusBadgeColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800 border-green-300';
      case 'resolved': return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'ruled_out': return 'bg-gray-100 text-gray-800 border-gray-300';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTypeBadgeColor = (type) => {
    switch (type) {
      case 'primary': return 'bg-purple-100 text-purple-800 border-purple-300';
      case 'secondary': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'differential': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const activeDiagnoses = diagnoses.filter(d => d.status === 'active');

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Diagnoses ({activeDiagnoses.length} active)
          </CardTitle>
          <Button onClick={() => setShowAddForm(!showAddForm)} size="sm">
            <Plus className="w-4 h-4 mr-1" />
            Add Diagnosis
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add Diagnosis Form */}
        {showAddForm && (
          <Card className="border-2 border-blue-200 bg-blue-50">
            <CardContent className="pt-6">
              <form onSubmit={handleAddDiagnosis} className="space-y-4">
                <div>
                  <Label>Search ICD-10 Code</Label>
                  <div className="relative">
                    <Input
                      placeholder="Search by disease name or code..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        searchICD10(e.target.value);
                      }}
                    />
                    {searching && <span className="absolute right-3 top-3 text-sm text-gray-500">Searching...</span>}
                    {searchResults.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border rounded-md shadow-lg max-h-60 overflow-auto">
                        {searchResults.map((code) => (
                          <div
                            key={code.code}
                            className="p-3 hover:bg-gray-100 cursor-pointer border-b"
                            onClick={() => selectICD10Code(code)}
                          >
                            <div className="flex items-start gap-2">
                              <Badge variant="outline" className="font-mono">{code.code}</Badge>
                              <div className="flex-1">
                                <div className="font-medium text-sm">{code.who_full_desc}</div>
                                {code.chapter_desc && (
                                  <div className="text-xs text-gray-500">{code.chapter_desc}</div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <Label>ICD-10 Code *</Label>
                  <Input
                    value={icd10Code}
                    onChange={(e) => setIcd10Code(e.target.value)}
                    placeholder="E.g., E11.9"
                    required
                  />
                </div>

                <div>
                  <Label>Description *</Label>
                  <Textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Diagnosis description"
                    rows={2}
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Type</Label>
                    <select
                      value={diagnosisType}
                      onChange={(e) => setDiagnosisType(e.target.value)}
                      className="w-full px-3 py-2 border rounded-md"
                    >
                      <option value="primary">Primary</option>
                      <option value="secondary">Secondary</option>
                      <option value="differential">Differential</option>
                    </select>
                  </div>

                  <div>
                    <Label>Status</Label>
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                      className="w-full px-3 py-2 border rounded-md"
                    >
                      <option value="active">Active</option>
                      <option value="resolved">Resolved</option>
                      <option value="ruled_out">Ruled Out</option>
                    </select>
                  </div>
                </div>

                <div>
                  <Label>Onset Date</Label>
                  <Input
                    type="date"
                    value={onsetDate}
                    onChange={(e) => setOnsetDate(e.target.value)}
                  />
                </div>

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
                    {saving ? 'Saving...' : 'Add Diagnosis'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Diagnoses List */}
        {loading ? (
          <div className="text-center py-8 text-gray-500">Loading diagnoses...</div>
        ) : diagnoses.length === 0 ? (
          <Alert>
            <AlertDescription>No diagnoses recorded for this patient.</AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-3">
            {diagnoses.map((diagnosis) => (
              <Card key={diagnosis.id} className="border-l-4 border-l-blue-500">
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline" className="font-mono font-bold">{diagnosis.icd10_code}</Badge>
                        <Badge className={getTypeBadgeColor(diagnosis.diagnosis_type)}>
                          {diagnosis.diagnosis_type}
                        </Badge>
                        <Badge className={getStatusBadgeColor(diagnosis.status)}>
                          {diagnosis.status}
                        </Badge>
                      </div>
                      <div className="font-medium text-gray-900 mb-1">
                        {diagnosis.diagnosis_description}
                      </div>
                      {diagnosis.onset_date && (
                        <div className="text-sm text-gray-600">
                          Onset: {new Date(diagnosis.onset_date).toLocaleDateString()}
                        </div>
                      )}
                      {diagnosis.notes && (
                        <div className="text-sm text-gray-600 mt-1">
                          Notes: {diagnosis.notes}
                        </div>
                      )}
                      <div className="text-xs text-gray-500 mt-2">
                        Recorded: {new Date(diagnosis.created_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="flex flex-col gap-2">
                      {diagnosis.status === 'active' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUpdateStatus(diagnosis.id, 'resolved')}
                        >
                          Mark Resolved
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-500"
                        onClick={() => handleDelete(diagnosis.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
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

export default DiagnosesManagement;
