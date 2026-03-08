import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, Plus, X, Edit2, Trash2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';

const AllergyManagement = ({ patientId, readonly = false }) => {
  const [allergies, setAllergies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingAllergy, setEditingAllergy] = useState(null);
  const { toast } = useToast();

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  // Form state
  const [formData, setFormData] = useState({
    substance: '',
    reaction: '',
    severity: 'moderate',
    notes: ''
  });

  useEffect(() => {
    if (patientId) {
      loadAllergies();
    }
  }, [patientId]);

  const loadAllergies = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `${backendUrl}/api/allergies/patient/${patientId}?status=active`
      );
      setAllergies(response.data);
    } catch (error) {
      console.error('Error loading allergies:', error);
      toast({
        title: 'Error',
        description: 'Failed to load allergies',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      if (editingAllergy) {
        // Update existing allergy
        await axios.put(
          `${backendUrl}/api/allergies/${editingAllergy.id}`,
          formData
        );
        toast({
          title: 'Success',
          description: 'Allergy updated successfully'
        });
      } else {
        // Create new allergy
        await axios.post(`${backendUrl}/api/allergies`, {
          patient_id: patientId,
          ...formData,
          source: 'manual_entry'
        });
        toast({
          title: 'Success',
          description: 'Allergy added successfully'
        });
      }

      // Reset form and reload
      setFormData({ substance: '', reaction: '', severity: 'moderate', notes: '' });
      setShowAddForm(false);
      setEditingAllergy(null);
      loadAllergies();
    } catch (error) {
      console.error('Error saving allergy:', error);
      toast({
        title: 'Error',
        description: 'Failed to save allergy',
        variant: 'destructive'
      });
    }
  };

  const handleEdit = (allergy) => {
    setEditingAllergy(allergy);
    setFormData({
      substance: allergy.substance,
      reaction: allergy.reaction || '',
      severity: allergy.severity || 'moderate',
      notes: allergy.notes || ''
    });
    setShowAddForm(true);
  };

  const handleDelete = async (allergyId) => {
    if (!window.confirm('Are you sure you want to remove this allergy?')) {
      return;
    }

    try {
      await axios.delete(`${backendUrl}/api/allergies/${allergyId}`);
      toast({
        title: 'Success',
        description: 'Allergy removed'
      });
      loadAllergies();
    } catch (error) {
      console.error('Error deleting allergy:', error);
      toast({
        title: 'Error',
        description: 'Failed to remove allergy',
        variant: 'destructive'
      });
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'mild':
        return 'bg-yellow-100 text-yellow-800';
      case 'moderate':
        return 'bg-orange-100 text-orange-800';
      case 'severe':
        return 'bg-red-100 text-red-800';
      case 'life_threatening':
        return 'bg-red-600 text-white';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return <div className="text-center py-4">Loading allergies...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Active Allergies Alert Banner */}
      {allergies.length > 0 && (
        <div className="bg-red-50 border-2 border-red-500 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-bold text-red-800 text-lg mb-2">
                ⚠️ ALLERGY ALERT
              </h3>
              <p className="text-red-700 text-sm mb-3">
                This patient has {allergies.length} known allerg{allergies.length === 1 ? 'y' : 'ies'}.
                Review before prescribing medications.
              </p>
              <div className="space-y-2">
                {allergies.map((allergy) => (
                  <div
                    key={allergy.id}
                    className="bg-white rounded p-3 border border-red-200"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-gray-900">
                            {allergy.substance}
                          </span>
                          <Badge className={getSeverityColor(allergy.severity)}>
                            {allergy.severity || 'moderate'}
                          </Badge>
                        </div>
                        {allergy.reaction && (
                          <p className="text-sm text-gray-700 mb-1">
                            <span className="font-medium">Reaction:</span> {allergy.reaction}
                          </p>
                        )}
                        {allergy.notes && (
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">Notes:</span> {allergy.notes}
                          </p>
                        )}
                      </div>
                      {!readonly && (
                        <div className="flex gap-1 ml-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(allergy)}
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(allergy.id)}
                          >
                            <Trash2 className="w-4 h-4 text-red-600" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* No Allergies Message */}
      {allergies.length === 0 && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center gap-2 text-green-800">
            <span className="font-medium">✓ No known allergies recorded</span>
          </div>
        </div>
      )}

      {/* Add/Edit Form */}
      {!readonly && (
        <>
          {!showAddForm && (
            <Button
              onClick={() => setShowAddForm(true)}
              className="w-full"
              variant="outline"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Allergy
            </Button>
          )}

          {showAddForm && (
            <Card className="border-2 border-teal-200">
              <CardHeader>
                <CardTitle className="text-lg">
                  {editingAllergy ? 'Edit Allergy' : 'Add New Allergy'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Label htmlFor="substance">Substance / Allergen *</Label>
                    <Input
                      id="substance"
                      value={formData.substance}
                      onChange={(e) =>
                        setFormData({ ...formData, substance: e.target.value })
                      }
                      placeholder="e.g., Penicillin, Peanuts, Latex"
                      required
                    />
                  </div>

                  <div>
                    <Label htmlFor="reaction">Reaction</Label>
                    <Input
                      id="reaction"
                      value={formData.reaction}
                      onChange={(e) =>
                        setFormData({ ...formData, reaction: e.target.value })
                      }
                      placeholder="e.g., Rash, Anaphylaxis, Hives"
                    />
                  </div>

                  <div>
                    <Label htmlFor="severity">Severity *</Label>
                    <select
                      id="severity"
                      value={formData.severity}
                      onChange={(e) =>
                        setFormData({ ...formData, severity: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      required
                    >
                      <option value="mild">Mild</option>
                      <option value="moderate">Moderate</option>
                      <option value="severe">Severe</option>
                      <option value="life_threatening">Life Threatening</option>
                      <option value="unknown">Unknown</option>
                    </select>
                  </div>

                  <div>
                    <Label htmlFor="notes">Notes</Label>
                    <textarea
                      id="notes"
                      value={formData.notes}
                      onChange={(e) =>
                        setFormData({ ...formData, notes: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      rows={3}
                      placeholder="Additional information..."
                    />
                  </div>

                  <div className="flex gap-2">
                    <Button type="submit" className="flex-1">
                      {editingAllergy ? 'Update' : 'Add'} Allergy
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setShowAddForm(false);
                        setEditingAllergy(null);
                        setFormData({
                          substance: '',
                          reaction: '',
                          severity: 'moderate',
                          notes: ''
                        });
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default AllergyManagement;
