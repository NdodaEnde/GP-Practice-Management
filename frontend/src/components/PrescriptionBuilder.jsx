import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Plus, Trash2, Search, Save } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const PrescriptionBuilder = ({ patientId, encounterId, doctorName, onSave }) => {
  const { toast } = useToast();
  const [prescriptionDate, setPrescriptionDate] = useState(new Date().toISOString().split('T')[0]);
  const [items, setItems] = useState([{
    medication_name: '',
    dosage: '',
    frequency: '',
    duration: '',
    quantity: '',
    instructions: ''
  }]);
  const [notes, setNotes] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  // Search medications
  const searchMedications = async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    try {
      const response = await axios.get(
        `${backendUrl}/api/medications/search?query=${encodeURIComponent(query)}`
      );
      setSearchResults(response.data.medications || []);
    } catch (error) {
      console.error('Error searching medications:', error);
    } finally {
      setSearching(false);
    }
  };

  // Add medication item
  const addItem = () => {
    setItems([...items, {
      medication_name: '',
      dosage: '',
      frequency: '',
      duration: '',
      quantity: '',
      instructions: ''
    }]);
  };

  // Remove medication item
  const removeItem = (index) => {
    const newItems = items.filter((_, i) => i !== index);
    setItems(newItems);
  };

  // Update medication item
  const updateItem = (index, field, value) => {
    const newItems = [...items];
    newItems[index][field] = value;
    setItems(newItems);
  };

  // Select medication from search results
  const selectMedication = (index, medication) => {
    const newItems = [...items];
    newItems[index].medication_name = medication.name;
    newItems[index].dosage = medication.common_dosages?.[0] || '';
    newItems[index].frequency = medication.common_frequencies?.[0] || '';
    setItems(newItems);
    setSearchResults([]);
    setSearchQuery('');
  };

  // Save prescription
  const savePrescription = async () => {
    // Validation
    if (items.length === 0 || !items[0].medication_name) {
      toast({
        title: "Validation Error",
        description: "Please add at least one medication",
        variant: "destructive"
      });
      return;
    }

    setSaving(true);
    try {
      const response = await axios.post(`${backendUrl}/api/prescriptions`, {
        patient_id: patientId,
        encounter_id: encounterId,
        doctor_name: doctorName || 'Dr. Unknown',
        prescription_date: prescriptionDate,
        items: items,
        notes: notes
      });

      toast({
        title: "Success",
        description: "Prescription created successfully"
      });

      if (onSave) {
        onSave(response.data.prescription_id);
      }

      // Reset form
      setItems([{
        medication_name: '',
        dosage: '',
        frequency: '',
        duration: '',
        quantity: '',
        instructions: ''
      }]);
      setNotes('');
    } catch (error) {
      console.error('Error saving prescription:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to save prescription",
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
          <Save className="w-5 h-5" />
          Create Prescription
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Prescription Date */}
        <div>
          <Label htmlFor="prescription_date">Prescription Date</Label>
          <Input
            id="prescription_date"
            type="date"
            value={prescriptionDate}
            onChange={(e) => setPrescriptionDate(e.target.value)}
          />
        </div>

        {/* Medication Items */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Medications</Label>
            <Button onClick={addItem} size="sm" variant="outline">
              <Plus className="w-4 h-4 mr-1" />
              Add Medication
            </Button>
          </div>

          {items.map((item, index) => (
            <Card key={index} className="p-4 border-2">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sm">Medication {index + 1}</span>
                  {items.length > 1 && (
                    <Button
                      onClick={() => removeItem(index)}
                      size="sm"
                      variant="ghost"
                      className="text-red-500"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>

                {/* Medication Name with Search */}
                <div>
                  <Label>Medication Name</Label>
                  <div className="relative">
                    <Input
                      placeholder="Search or type medication name"
                      value={item.medication_name}
                      onChange={(e) => {
                        updateItem(index, 'medication_name', e.target.value);
                        setSearchQuery(e.target.value);
                        searchMedications(e.target.value);
                      }}
                    />
                    {searchResults.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border rounded-md shadow-lg max-h-60 overflow-auto">
                        {searchResults.map((med) => (
                          <div
                            key={med.id}
                            className="p-2 hover:bg-gray-100 cursor-pointer"
                            onClick={() => selectMedication(index, med)}
                          >
                            <div className="font-semibold">{med.name}</div>
                            <div className="text-xs text-gray-500">
                              {med.generic_name} | {med.category}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Dosage</Label>
                    <Input
                      placeholder="e.g., 500mg"
                      value={item.dosage}
                      onChange={(e) => updateItem(index, 'dosage', e.target.value)}
                    />
                  </div>

                  <div>
                    <Label>Frequency</Label>
                    <Input
                      placeholder="e.g., Twice daily"
                      value={item.frequency}
                      onChange={(e) => updateItem(index, 'frequency', e.target.value)}
                    />
                  </div>

                  <div>
                    <Label>Duration</Label>
                    <Input
                      placeholder="e.g., 7 days"
                      value={item.duration}
                      onChange={(e) => updateItem(index, 'duration', e.target.value)}
                    />
                  </div>

                  <div>
                    <Label>Quantity</Label>
                    <Input
                      placeholder="e.g., 14 tablets"
                      value={item.quantity}
                      onChange={(e) => updateItem(index, 'quantity', e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <Label>Instructions</Label>
                  <Textarea
                    placeholder="Special instructions for the patient"
                    value={item.instructions}
                    onChange={(e) => updateItem(index, 'instructions', e.target.value)}
                    rows={2}
                  />
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Notes */}
        <div>
          <Label htmlFor="notes">Additional Notes</Label>
          <Textarea
            id="notes"
            placeholder="Any additional notes about the prescription"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
          />
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2">
          <Button
            onClick={savePrescription}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Saving...' : 'Save Prescription'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default PrescriptionBuilder;
