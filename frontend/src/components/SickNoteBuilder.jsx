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
import { FileText, Save } from 'lucide-react';
import { useToast } from './ui/use-toast';

const SickNoteBuilder = ({ patientId, encounterId, doctorName, onSave }) => {
  const { toast } = useToast();
  const [issueDate, setIssueDate] = useState(new Date().toISOString().split('T')[0]);
  const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [endDate, setEndDate] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [fitnessStatus, setFitnessStatus] = useState('unfit');
  const [restrictions, setRestrictions] = useState('');
  const [additionalNotes, setAdditionalNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  // Calculate days
  const calculateDays = () => {
    if (startDate && endDate) {
      const start = new Date(startDate);
      const end = new Date(endDate);
      const diff = Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1;
      return diff > 0 ? diff : 0;
    }
    return 0;
  };

  // Save sick note
  const saveSickNote = async () => {
    // Validation
    if (!diagnosis || !startDate || !endDate) {
      toast({
        title: "Validation Error",
        description: "Please fill in all required fields",
        variant: "destructive"
      });
      return;
    }

    if (new Date(endDate) < new Date(startDate)) {
      toast({
        title: "Validation Error",
        description: "End date must be after start date",
        variant: "destructive"
      });
      return;
    }

    setSaving(true);
    try {
      const response = await axios.post(`${backendUrl}/api/sick-notes`, {
        patient_id: patientId,
        encounter_id: encounterId,
        doctor_name: doctorName || 'Dr. Unknown',
        issue_date: issueDate,
        start_date: startDate,
        end_date: endDate,
        diagnosis: diagnosis,
        fitness_status: fitnessStatus,
        restrictions: restrictions || null,
        additional_notes: additionalNotes || null
      });

      toast({
        title: "Success",
        description: "Sick note created successfully"
      });

      if (onSave) {
        onSave(response.data.sick_note_id);
      }

      // Reset form
      setDiagnosis('');
      setRestrictions('');
      setAdditionalNotes('');
      setEndDate('');
    } catch (error) {
      console.error('Error saving sick note:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to save sick note",
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
          <FileText className="w-5 h-5" />
          Create Sick Note / Medical Certificate
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Issue Date */}
        <div>
          <Label htmlFor="issue_date">Issue Date</Label>
          <Input
            id="issue_date"
            type="date"
            value={issueDate}
            onChange={(e) => setIssueDate(e.target.value)}
          />
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="start_date">Start Date *</Label>
            <Input
              id="start_date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
            />
          </div>

          <div>
            <Label htmlFor="end_date">End Date *</Label>
            <Input
              id="end_date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
            />
          </div>
        </div>

        {/* Days Calculation */}
        {startDate && endDate && (
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
            <span className="font-semibold">Duration: </span>
            <span className="text-blue-700">{calculateDays()} days</span>
          </div>
        )}

        {/* Diagnosis */}
        <div>
          <Label htmlFor="diagnosis">Diagnosis *</Label>
          <Input
            id="diagnosis"
            placeholder="e.g., Acute upper respiratory tract infection"
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            required
          />
        </div>

        {/* Fitness Status */}
        <div>
          <Label htmlFor="fitness_status">Fitness to Work Status *</Label>
          <Select value={fitnessStatus} onValueChange={setFitnessStatus}>
            <SelectTrigger>
              <SelectValue placeholder="Select fitness status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="unfit">Unfit for work</SelectItem>
              <SelectItem value="fit_with_restrictions">Fit with restrictions</SelectItem>
              <SelectItem value="fit">Fit for work</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Restrictions (conditional) */}
        {fitnessStatus === 'fit_with_restrictions' && (
          <div>
            <Label htmlFor="restrictions">Restrictions / Limitations</Label>
            <Textarea
              id="restrictions"
              placeholder="Specify work restrictions or limitations"
              value={restrictions}
              onChange={(e) => setRestrictions(e.target.value)}
              rows={3}
            />
          </div>
        )}

        {/* Additional Notes */}
        <div>
          <Label htmlFor="additional_notes">Additional Notes</Label>
          <Textarea
            id="additional_notes"
            placeholder="Any additional information"
            value={additionalNotes}
            onChange={(e) => setAdditionalNotes(e.target.value)}
            rows={3}
          />
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2">
          <Button
            onClick={saveSickNote}
            disabled={saving}
            className="bg-green-600 hover:bg-green-700"
          >
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Saving...' : 'Generate Sick Note'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default SickNoteBuilder;
