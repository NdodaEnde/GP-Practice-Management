import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Alert, AlertDescription } from './ui/alert';
import { Plus, Trash2, Search, Save, AlertTriangle, Pill } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const PrescriptionBuilderNAPPI = ({ patientId, encounterId, doctorName, initialData, onSave }) => {
  const { toast } = useToast();
  const [prescriptionDate, setPrescriptionDate] = useState(new Date().toISOString().split('T')[0]);
  
  // Initialize items from initialData if provided
  const [items, setItems] = useState(() => {
    if (initialData && initialData.length > 0) {
      return initialData.map(item => ({
        medication_name: item.medication_name || '',
        nappi_code: item.nappi_code || '',
        generic_name: item.generic_name || '',
        dosage: item.dosage || '',
        frequency: item.frequency || '',
        duration: item.duration || '',
        quantity: item.quantity || '',
        instructions: item.instructions || ''
      }));
    }
    return [{
      medication_name: '',
      nappi_code: '',
      generic_name: '',
      dosage: '',
      frequency: '',
      duration: '',
      quantity: '',
      instructions: ''
    }];
  });
  const [notes, setNotes] = useState('');
  const [searchQueries, setSearchQueries] = useState({});
  const [searchResults, setSearchResults] = useState({});
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [allergies, setAllergies] = useState([]);
  const [loadingAllergies, setLoadingAllergies] = useState(false);
  const [showAllergyWarning, setShowAllergyWarning] = useState(false);
  const [allergyConflicts, setAllergyConflicts] = useState([]);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  // Fetch patient allergies on component mount
  useEffect(() => {
    if (patientId) {
      fetchPatientAllergies();
    }
  }, [patientId]);

  // Check for allergy conflicts whenever items change
  useEffect(() => {
    checkAllergyConflicts();
  }, [items, allergies]);

  const fetchPatientAllergies = async () => {
    setLoadingAllergies(true);
    try {
      const response = await axios.get(`${backendUrl}/api/allergies/patient/${patientId}`);
      setAllergies(response.data || []);
    } catch (error) {
      console.error('Error fetching allergies:', error);
    } finally {
      setLoadingAllergies(false);
    }
  };

  const checkAllergyConflicts = () => {
    if (allergies.length === 0) {
      setAllergyConflicts([]);
      setShowAllergyWarning(false);
      return;
    }

    const conflicts = [];
    items.forEach((item, index) => {
      if (!item.medication_name && !item.generic_name) return;
      
      allergies.forEach((allergy) => {
        // Skip if allergy doesn't have allergen field
        if (!allergy || !allergy.allergen) return;
        
        const medName = (item.medication_name || '').toLowerCase();
        const genericName = (item.generic_name || '').toLowerCase();
        const allergen = allergy.allergen.toLowerCase();
        
        // Check if medication name, generic name, or ingredient contains allergen
        if (medName.includes(allergen) || genericName.includes(allergen) || 
            allergen.includes(medName) || allergen.includes(genericName)) {
          conflicts.push({
            itemIndex: index,
            medication: item.medication_name || item.generic_name,
            allergy: allergy
          });
        }
      });
    });

    setAllergyConflicts(conflicts);
    setShowAllergyWarning(conflicts.length > 0);
  };

  // Search NAPPI medications
  const searchNAPPIMedications = async (query, itemIndex) => {
    if (query.length < 2) {
      setSearchResults(prev => ({ ...prev, [itemIndex]: [] }));
      return;
    }

    setSearching(true);
    try {
      const response = await axios.get(
        `${backendUrl}/api/nappi/search?query=${encodeURIComponent(query)}&limit=15`
      );
      setSearchResults(prev => ({ ...prev, [itemIndex]: response.data.results || [] }));
    } catch (error) {
      console.error('Error searching NAPPI medications:', error);
      toast({
        title: "Search Error",
        description: "Failed to search medications. Please try again.",
        variant: "destructive"
      });
    } finally {
      setSearching(false);
    }
  };

  // Add medication item
  const addItem = () => {
    setItems([...items, {
      medication_name: '',
      nappi_code: '',
      generic_name: '',
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
    // Clean up search state
    const newSearchQueries = { ...searchQueries };
    const newSearchResults = { ...searchResults };
    delete newSearchQueries[index];
    delete newSearchResults[index];
    setSearchQueries(newSearchQueries);
    setSearchResults(newSearchResults);
  };

  // Update medication item
  const updateItem = (index, field, value) => {
    const newItems = [...items];
    newItems[index][field] = value;
    setItems(newItems);
  };

  // Select medication from NAPPI search results
  const selectNAPPIMedication = (index, medication) => {
    const newItems = [...items];
    newItems[index].medication_name = medication.brand_name;
    newItems[index].nappi_code = medication.nappi_code;
    newItems[index].generic_name = medication.generic_name;
    newItems[index].dosage = medication.strength || '';
    setItems(newItems);
    
    // Clear search results
    setSearchResults(prev => ({ ...prev, [index]: [] }));
    setSearchQueries(prev => ({ ...prev, [index]: '' }));
  };

  // Get schedule badge color
  const getScheduleBadgeColor = (schedule) => {
    if (!schedule) return 'bg-gray-100 text-gray-700';
    if (schedule === 'S0' || schedule === 'Unscheduled') return 'bg-green-100 text-green-700';
    if (schedule === 'S1' || schedule === 'S2') return 'bg-yellow-100 text-yellow-700';
    if (schedule === 'S3' || schedule === 'S4') return 'bg-orange-100 text-orange-700';
    return 'bg-red-100 text-red-700';
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

    // Check for allergy conflicts
    if (allergyConflicts.length > 0) {
      const conflictMessages = allergyConflicts.map(c => 
        `${c.medication} may conflict with allergy: ${c.allergy.allergen}`
      ).join('\n');
      
      const confirmed = window.confirm(
        `⚠️ ALLERGY WARNING!\n\n${conflictMessages}\n\nReaction: ${allergyConflicts[0].allergy.reaction}\nSeverity: ${allergyConflicts[0].allergy.severity}\n\nAre you sure you want to proceed with this prescription?`
      );
      
      if (!confirmed) {
        return;
      }
    }

    setSaving(true);
    try {
      const response = await axios.post(`${backendUrl}/api/prescriptions`, {
        patient_id: patientId,
        encounter_id: encounterId,
        doctor_name: doctorName || 'Dr. Unknown',
        prescription_date: prescriptionDate,
        items: items.map(item => ({
          medication_name: item.medication_name,
          nappi_code: item.nappi_code || null,
          generic_name: item.generic_name || null,
          dosage: item.dosage,
          frequency: item.frequency,
          duration: item.duration,
          quantity: item.quantity,
          instructions: item.instructions
        })),
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
        nappi_code: '',
        generic_name: '',
        dosage: '',
        frequency: '',
        duration: '',
        quantity: '',
        instructions: ''
      }]);
      setNotes('');
      setAllergyConflicts([]);
      setShowAllergyWarning(false);
      setSearchQueries({});
      setSearchResults({});
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
          <Pill className="w-5 h-5" />
          Create Prescription with NAPPI Codes
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Patient Allergies Alert */}
        {allergies.length > 0 && (
          <Alert className="border-red-500 bg-red-50">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <AlertDescription>
              <strong className="text-red-700">Patient has {allergies.length} known {allergies.length === 1 ? 'allergy' : 'allergies'}:</strong>
              <ul className="mt-2 list-disc list-inside space-y-1">
                {allergies.map((allergy) => (
                  <li key={allergy.id} className="text-sm">
                    <strong>{allergy.allergen}</strong> - {allergy.reaction} 
                    <span className="ml-2 px-2 py-0.5 bg-red-200 text-red-800 rounded text-xs font-semibold">
                      {allergy.severity}
                    </span>
                  </li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {/* Allergy Conflict Warning */}
        {showAllergyWarning && allergyConflicts.length > 0 && (
          <Alert variant="destructive" className="border-orange-500 bg-orange-50">
            <AlertTriangle className="h-5 w-5 text-orange-600" />
            <AlertDescription>
              <strong className="text-orange-800 text-lg">⚠️ ALLERGY CONFLICT DETECTED!</strong>
              <ul className="mt-2 space-y-2">
                {allergyConflicts.map((conflict, idx) => (
                  <li key={idx} className="text-sm bg-white p-2 rounded border border-orange-300">
                    <strong className="text-orange-900">Medication #{conflict.itemIndex + 1}: {conflict.medication}</strong>
                    <br />
                    <span className="text-orange-700">May conflict with known allergy: {conflict.allergy.allergen}</span>
                    <br />
                    <span className="text-red-600 font-semibold">Reaction: {conflict.allergy.reaction} | Severity: {conflict.allergy.severity}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-orange-800 font-semibold">Please review before prescribing!</p>
            </AlertDescription>
          </Alert>
        )}

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

                {/* Medication Search with NAPPI */}
                <div>
                  <Label>Search Medication (NAPPI Database)</Label>
                  <div className="relative">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <Input
                        placeholder="Search by brand name, generic name, or ingredient..."
                        className="pl-10"
                        value={searchQueries[index] || ''}
                        onChange={(e) => {
                          const query = e.target.value;
                          setSearchQueries(prev => ({ ...prev, [index]: query }));
                          searchNAPPIMedications(query, index);
                        }}
                      />
                    </div>
                    
                    {/* Search Results Dropdown */}
                    {searchResults[index] && searchResults[index].length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border rounded-md shadow-lg max-h-80 overflow-auto">
                        {searchResults[index].map((med) => (
                          <div
                            key={med.nappi_code}
                            className="p-3 hover:bg-gray-50 cursor-pointer border-b last:border-b-0"
                            onClick={() => selectNAPPIMedication(index, med)}
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="font-semibold text-blue-700">{med.brand_name}</div>
                                <div className="text-sm text-gray-600">{med.generic_name}</div>
                                {med.strength && (
                                  <div className="text-xs text-gray-500 mt-1">Strength: {med.strength}</div>
                                )}
                                <div className="text-xs text-gray-400 mt-1">NAPPI: {med.nappi_code}</div>
                              </div>
                              <div className="flex flex-col gap-1 items-end">
                                {med.schedule && (
                                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getScheduleBadgeColor(med.schedule)}`}>
                                    {med.schedule}
                                  </span>
                                )}
                                {med.dosage_form && (
                                  <span className="text-xs text-gray-500">{med.dosage_form}</span>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Selected Medication Display */}
                {item.nappi_code && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-semibold text-blue-800">{item.medication_name}</div>
                        <div className="text-sm text-gray-600">{item.generic_name}</div>
                        <div className="text-xs text-gray-500 mt-1">NAPPI Code: {item.nappi_code}</div>
                      </div>
                      <Pill className="w-5 h-5 text-blue-600" />
                    </div>
                  </div>
                )}

                {/* Manual Entry Option */}
                {!item.nappi_code && (
                  <div>
                    <Label>Or Enter Medication Name Manually</Label>
                    <Input
                      placeholder="Medication name"
                      value={item.medication_name}
                      onChange={(e) => updateItem(index, 'medication_name', e.target.value)}
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Dosage / Strength *</Label>
                    <Input
                      placeholder="e.g., 500mg"
                      value={item.dosage}
                      onChange={(e) => updateItem(index, 'dosage', e.target.value)}
                      required
                    />
                  </div>

                  <div>
                    <Label>Frequency *</Label>
                    <Input
                      placeholder="e.g., Twice daily"
                      value={item.frequency}
                      onChange={(e) => updateItem(index, 'frequency', e.target.value)}
                      required
                    />
                  </div>

                  <div>
                    <Label>Duration *</Label>
                    <Input
                      placeholder="e.g., 7 days"
                      value={item.duration}
                      onChange={(e) => updateItem(index, 'duration', e.target.value)}
                      required
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
                  <Label>Instructions for Patient</Label>
                  <Textarea
                    placeholder="e.g., Take with food, avoid alcohol..."
                    value={item.instructions}
                    onChange={(e) => updateItem(index, 'instructions', e.target.value)}
                    rows={2}
                  />
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Additional Notes */}
        <div>
          <Label htmlFor="notes">Additional Notes</Label>
          <Textarea
            id="notes"
            placeholder="Any additional notes for the prescription..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
          />
        </div>

        {/* Save Button */}
        <div className="flex justify-end gap-3">
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

export default PrescriptionBuilderNAPPI;
