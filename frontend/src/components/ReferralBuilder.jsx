import React, { useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Send, Save } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const ReferralBuilder = ({ patientId, encounterId, doctorName, onSave }) => {
  const { toast } = useToast();
  const [referralDate, setReferralDate] = useState(new Date().toISOString().split('T')[0]);
  const [specialistType, setSpecialistType] = useState('');
  const [specialistName, setSpecialistName] = useState('');
  const [specialistPractice, setSpecialistPractice] = useState('');
  const [reasonForReferral, setReasonForReferral] = useState('');
  const [clinicalFindings, setClinicalFindings] = useState('');
  const [investigationsDone, setInvestigationsDone] = useState('');
  const [currentMedications, setCurrentMedications] = useState('');
  const [urgency, setUrgency] = useState('routine');
  const [saving, setSaving] = useState(false);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  const specialistTypes = [
    'Cardiologist',
    'Dermatologist',
    'Endocrinologist',
    'Gastroenterologist',
    'Neurologist',
    'Orthopedist',
    'Psychiatrist',
    'Pulmonologist',
    'Rheumatologist',
    'Urologist',
    'Ophthalmologist',
    'ENT Specialist',
    'Gynecologist',
    'Oncologist',
    'Nephrologist',
    'Other'
  ];

  // Save referral
  const saveReferral = async () => {
    // Validation
    if (!specialistType || !reasonForReferral || !clinicalFindings) {
      toast({
        title: "Validation Error",
        description: "Please fill in all required fields",
        variant: "destructive"
      });
      return;
    }

    setSaving(true);
    try {
      const response = await axios.post(`${backendUrl}/api/referrals`, {
        patient_id: patientId,
        encounter_id: encounterId,
        referring_doctor_name: doctorName || 'Dr. Unknown',
        referral_date: referralDate,
        specialist_type: specialistType,
        specialist_name: specialistName || null,
        specialist_practice: specialistPractice || null,
        reason_for_referral: reasonForReferral,
        clinical_findings: clinicalFindings,
        investigations_done: investigationsDone || null,
        current_medications: currentMedications || null,
        urgency: urgency
      });

      toast({
        title: "Success",
        description: "Referral letter created successfully"
      });

      if (onSave) {
        onSave(response.data.referral_id);
      }

      // Reset form
      setSpecialistType('');
      setSpecialistName('');
      setSpecialistPractice('');
      setReasonForReferral('');
      setClinicalFindings('');
      setInvestigationsDone('');
      setCurrentMedications('');
      setUrgency('routine');
    } catch (error) {
      console.error('Error saving referral:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to save referral",
        variant: "destructive"
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Send className="w-5 h-5" />
          Create Referral Letter
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Referral Date */}
        <div>
          <Label htmlFor="referral_date">Referral Date</Label>
          <Input
            id="referral_date"
            type="date"
            value={referralDate}
            onChange={(e) => setReferralDate(e.target.value)}
          />
        </div>

        {/* Specialist Type */}
        <div>
          <Label htmlFor="specialist_type">Specialist Type *</Label>
          <Select value={specialistType} onValueChange={setSpecialistType}>
            <SelectTrigger>
              <SelectValue placeholder="Select specialist type" />
            </SelectTrigger>
            <SelectContent>
              {specialistTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Specialist Details */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="specialist_name">Specialist Name (Optional)</Label>
            <Input
              id="specialist_name"
              placeholder="Dr. John Smith"
              value={specialistName}
              onChange={(e) => setSpecialistName(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="specialist_practice">Practice / Hospital (Optional)</Label>
            <Input
              id="specialist_practice"
              placeholder="City Hospital"
              value={specialistPractice}
              onChange={(e) => setSpecialistPractice(e.target.value)}
            />
          </div>
        </div>

        {/* Urgency */}
        <div>
          <Label htmlFor="urgency">Urgency</Label>
          <Select value={urgency} onValueChange={setUrgency}>
            <SelectTrigger>
              <SelectValue placeholder="Select urgency" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="urgent">Urgent</SelectItem>
              <SelectItem value="routine">Routine</SelectItem>
              <SelectItem value="non-urgent">Non-urgent</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Reason for Referral */}
        <div>
          <Label htmlFor="reason">Reason for Referral *</Label>
          <Textarea
            id="reason"
            placeholder="Brief reason for referring the patient"
            value={reasonForReferral}
            onChange={(e) => setReasonForReferral(e.target.value)}
            rows={3}
            required
          />
        </div>

        {/* Clinical Findings */}
        <div>
          <Label htmlFor="clinical_findings">Clinical Findings *</Label>
          <Textarea
            id="clinical_findings"
            placeholder="Relevant clinical findings, symptoms, examination results"
            value={clinicalFindings}
            onChange={(e) => setClinicalFindings(e.target.value)}
            rows={4}
            required
          />
        </div>

        {/* Investigations Done */}
        <div>
          <Label htmlFor="investigations">Investigations Done (Optional)</Label>
          <Textarea
            id="investigations"
            placeholder="Tests, scans, or other investigations completed"
            value={investigationsDone}
            onChange={(e) => setInvestigationsDone(e.target.value)}
            rows={3}
          />
        </div>

        {/* Current Medications */}
        <div>
          <Label htmlFor="medications">Current Medications (Optional)</Label>
          <Textarea
            id="medications"
            placeholder="List of current medications the patient is taking"
            value={currentMedications}
            onChange={(e) => setCurrentMedications(e.target.value)}
            rows={3}
          />
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2">
          <Button
            onClick={saveReferral}
            disabled={saving}
            className="bg-purple-600 hover:bg-purple-700"
          >
            <Send className="w-4 h-4 mr-2" />
            {saving ? 'Saving...' : 'Generate Referral Letter'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default ReferralBuilder;
