import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription 
} from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  Plus, 
  Edit, 
  Trash2, 
  Save, 
  X,
  FileText,
  Settings,
  ArrowRight,
  CheckCircle,
  AlertCircle
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const DEMO_WORKSPACE = 'demo-gp-workspace-001';

// Available target tables and their fields
const TARGET_TABLES = {
  immunizations: {
    name: 'Immunizations',
    fields: [
      'vaccine_name', 'vaccine_type', 'administration_date', 'dose_number',
      'doses_in_series', 'route', 'anatomical_site', 'series_name',
      'lot_number', 'manufacturer', 'administered_by'
    ]
  },
  lab_results: {
    name: 'Lab Results',
    fields: [
      'test_name', 'result_value', 'units', 'reference_range',
      'abnormal_flag', 'test_category', 'result_datetime', 'specimen_type'
    ]
  },
  procedures: {
    name: 'Procedures',
    fields: [
      'procedure_name', 'procedure_datetime', 'indication', 'anatomical_site',
      'performing_provider', 'status', 'outcome', 'operative_notes'
    ]
  },
  prescriptions: {
    name: 'Prescriptions',
    fields: [
      'medication_name', 'nappi_code', 'generic_name', 'dosage',
      'frequency', 'duration', 'quantity', 'instructions'
    ]
  },
  allergies: {
    name: 'Allergies',
    fields: [
      'allergen', 'allergen_type', 'reaction', 'severity',
      'onset_date', 'verified_by', 'notes'
    ]
  },
  diagnoses: {
    name: 'Diagnoses',
    fields: [
      'diagnosis_text', 'icd10_code', 'diagnosis_type', 'onset_date',
      'status', 'severity', 'notes'
    ]
  },
  vitals: {
    name: 'Vital Signs',
    fields: [
      'blood_pressure_systolic', 'blood_pressure_diastolic', 'heart_rate',
      'temperature', 'respiratory_rate', 'oxygen_saturation', 'weight', 'height'
    ]
  }
};

const TRANSFORMATION_TYPES = [
  { value: 'direct', label: 'Direct Copy', description: 'Copy value as-is' },
  { value: 'lookup', label: 'Lookup/Match', description: 'Match against reference data (e.g., ICD-10)' },
  { value: 'ai_match', label: 'AI Matching', description: 'Use AI to match/suggest codes' },
  { value: 'split', label: 'Split String', description: 'Split text (e.g., BP: 120/80 → 120 and 80)' },
  { value: 'concatenation', label: 'Combine Fields', description: 'Combine multiple fields' },
  { value: 'calculation', label: 'Calculate', description: 'Calculate from other fields (e.g., BMI)' }
];

const FIELD_TYPES = ['text', 'number', 'date', 'datetime', 'boolean', 'json'];

const ExtractionConfiguration = () => {
  const { toast } = useToast();
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [showMappingForm, setShowMappingForm] = useState(false);
  const [editingMapping, setEditingMapping] = useState(null);

  // Template form state
  const [templateForm, setTemplateForm] = useState({
    template_name: '',
    template_description: '',
    document_type: 'medical_record',
    auto_populate: true,
    require_validation: true,
    is_active: true
  });

  // Mapping form state
  const [mappingForm, setMappingForm] = useState({
    source_section: '',
    source_field: '',
    target_table: '',
    target_field: '',
    transformation_type: 'direct',
    field_type: 'text',
    is_required: false,
    processing_order: 100
  });

  // Load templates on mount
  useEffect(() => {
    loadTemplates();
  }, []);

  // Load mappings when template is selected
  useEffect(() => {
    if (selectedTemplate) {
      loadMappings(selectedTemplate.id);
    }
  }, [selectedTemplate]);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `${BACKEND_URL}/api/extraction/templates?workspace_id=${DEMO_WORKSPACE}`
      );
      setTemplates(response.data);
    } catch (error) {
      console.error('Failed to load templates:', error);
      toast({
        title: "Error",
        description: "Failed to load extraction templates",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMappings = async (templateId) => {
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/extraction/templates/${templateId}/mappings`
      );
      setMappings(response.data);
    } catch (error) {
      console.error('Failed to load mappings:', error);
      toast({
        title: "Error",
        description: "Failed to load field mappings",
        variant: "destructive"
      });
    }
  };

  const handleCreateTemplate = async () => {
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/extraction/templates`,
        {
          ...templateForm,
          tenant_id: 'demo-tenant-001',
          workspace_id: DEMO_WORKSPACE
        }
      );
      
      setTemplates([...templates, response.data]);
      setShowTemplateForm(false);
      setTemplateForm({
        template_name: '',
        template_description: '',
        document_type: 'medical_record',
        auto_populate: true,
        require_validation: true,
        is_active: true
      });
      
      toast({
        title: "Success",
        description: "Extraction template created successfully"
      });
    } catch (error) {
      console.error('Failed to create template:', error);
      toast({
        title: "Error",
        description: "Failed to create template",
        variant: "destructive"
      });
    }
  };

  const handleCreateMapping = async () => {
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/extraction/mappings`,
        {
          ...mappingForm,
          template_id: selectedTemplate.id,
          workspace_id: DEMO_WORKSPACE
        }
      );
      
      setMappings([...mappings, response.data]);
      setShowMappingForm(false);
      resetMappingForm();
      
      toast({
        title: "Success",
        description: "Field mapping created successfully"
      });
    } catch (error) {
      console.error('Failed to create mapping:', error);
      toast({
        title: "Error",
        description: "Failed to create mapping",
        variant: "destructive"
      });
    }
  };

  const handleUpdateMapping = async () => {
    try {
      const response = await axios.patch(
        `${BACKEND_URL}/api/extraction/mappings/${editingMapping.id}`,
        mappingForm
      );
      
      setMappings(mappings.map(m => m.id === editingMapping.id ? response.data : m));
      setShowMappingForm(false);
      setEditingMapping(null);
      resetMappingForm();
      
      toast({
        title: "Success",
        description: "Field mapping updated successfully"
      });
    } catch (error) {
      console.error('Failed to update mapping:', error);
      toast({
        title: "Error",
        description: "Failed to update mapping",
        variant: "destructive"
      });
    }
  };

  const handleDeleteMapping = async (mappingId) => {
    if (!window.confirm('Are you sure you want to delete this mapping?')) return;
    
    try {
      await axios.delete(`${BACKEND_URL}/api/extraction/mappings/${mappingId}`);
      setMappings(mappings.filter(m => m.id !== mappingId));
      
      toast({
        title: "Success",
        description: "Field mapping deleted successfully"
      });
    } catch (error) {
      console.error('Failed to delete mapping:', error);
      toast({
        title: "Error",
        description: "Failed to delete mapping",
        variant: "destructive"
      });
    }
  };

  const handleEditMapping = (mapping) => {
    setEditingMapping(mapping);
    setMappingForm({
      source_section: mapping.source_section,
      source_field: mapping.source_field,
      target_table: mapping.target_table,
      target_field: mapping.target_field,
      transformation_type: mapping.transformation_type,
      field_type: mapping.field_type,
      is_required: mapping.is_required,
      processing_order: mapping.processing_order
    });
    setShowMappingForm(true);
  };

  const resetMappingForm = () => {
    setMappingForm({
      source_section: '',
      source_field: '',
      target_table: '',
      target_field: '',
      transformation_type: 'direct',
      field_type: 'text',
      is_required: false,
      processing_order: 100
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Extraction Configuration</h1>
        <p className="text-gray-600">
          Configure how medical documents are extracted and mapped to structured EHR tables
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Templates List */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Extraction Templates</CardTitle>
                <Button onClick={() => setShowTemplateForm(!showTemplateForm)} size="sm">
                  <Plus className="w-4 h-4 mr-1" />
                  New
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {showTemplateForm && (
                <div className="mb-4 p-4 border rounded-lg bg-gray-50">
                  <Label className="mb-2">Template Name</Label>
                  <Input
                    value={templateForm.template_name}
                    onChange={(e) => setTemplateForm({...templateForm, template_name: e.target.value})}
                    placeholder="e.g., Standard GP Record"
                    className="mb-3"
                  />
                  
                  <Label className="mb-2">Description</Label>
                  <Input
                    value={templateForm.template_description}
                    onChange={(e) => setTemplateForm({...templateForm, template_description: e.target.value})}
                    placeholder="Template description"
                    className="mb-3"
                  />
                  
                  <Label className="mb-2">Document Type</Label>
                  <select
                    value={templateForm.document_type}
                    onChange={(e) => setTemplateForm({...templateForm, document_type: e.target.value})}
                    className="w-full p-2 border rounded mb-3"
                  >
                    <option value="medical_record">Medical Record</option>
                    <option value="lab_report">Lab Report</option>
                    <option value="immunization_card">Immunization Card</option>
                    <option value="prescription">Prescription</option>
                    <option value="procedure_note">Procedure Note</option>
                  </select>
                  
                  <div className="flex gap-2">
                    <Button onClick={handleCreateTemplate} size="sm">
                      <Save className="w-4 h-4 mr-1" />
                      Save
                    </Button>
                    <Button 
                      onClick={() => setShowTemplateForm(false)} 
                      variant="outline" 
                      size="sm"
                    >
                      <X className="w-4 h-4 mr-1" />
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {loading ? (
                <p className="text-gray-500 text-center py-4">Loading templates...</p>
              ) : templates.length === 0 ? (
                <p className="text-gray-500 text-center py-4">
                  No templates yet. Create one to get started.
                </p>
              ) : (
                <div className="space-y-2">
                  {templates.map((template) => (
                    <div
                      key={template.id}
                      onClick={() => setSelectedTemplate(template)}
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                        selectedTemplate?.id === template.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{template.template_name}</p>
                          <p className="text-sm text-gray-500">{template.document_type}</p>
                        </div>
                        {template.is_active && (
                          <CheckCircle className="w-5 h-5 text-green-500" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Mappings Section */}
        <div className="lg:col-span-2">
          {selectedTemplate ? (
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>Field Mappings</CardTitle>
                    <CardDescription>
                      Map extracted fields to EHR tables for: {selectedTemplate.template_name}
                    </CardDescription>
                  </div>
                  <Button 
                    onClick={() => {
                      resetMappingForm();
                      setEditingMapping(null);
                      setShowMappingForm(!showMappingForm);
                    }} 
                    size="sm"
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    Add Mapping
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {showMappingForm && (
                  <div className="mb-6 p-4 border rounded-lg bg-gray-50">
                    <h3 className="font-medium mb-3">
                      {editingMapping ? 'Edit' : 'New'} Field Mapping
                    </h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="mb-2">Source Section</Label>
                        <Input
                          value={mappingForm.source_section}
                          onChange={(e) => setMappingForm({...mappingForm, source_section: e.target.value})}
                          placeholder="e.g., vaccination_records"
                        />
                      </div>
                      
                      <div>
                        <Label className="mb-2">Source Field</Label>
                        <Input
                          value={mappingForm.source_field}
                          onChange={(e) => setMappingForm({...mappingForm, source_field: e.target.value})}
                          placeholder="e.g., vaccine_type"
                        />
                      </div>
                      
                      <div>
                        <Label className="mb-2">Target Table</Label>
                        <select
                          value={mappingForm.target_table}
                          onChange={(e) => setMappingForm({...mappingForm, target_table: e.target.value})}
                          className="w-full p-2 border rounded"
                        >
                          <option value="">Select table...</option>
                          {Object.keys(TARGET_TABLES).map(table => (
                            <option key={table} value={table}>
                              {TARGET_TABLES[table].name}
                            </option>
                          ))}
                        </select>
                      </div>
                      
                      <div>
                        <Label className="mb-2">Target Field</Label>
                        <select
                          value={mappingForm.target_field}
                          onChange={(e) => setMappingForm({...mappingForm, target_field: e.target.value})}
                          className="w-full p-2 border rounded"
                          disabled={!mappingForm.target_table}
                        >
                          <option value="">Select field...</option>
                          {mappingForm.target_table && TARGET_TABLES[mappingForm.target_table].fields.map(field => (
                            <option key={field} value={field}>{field}</option>
                          ))}
                        </select>
                      </div>
                      
                      <div>
                        <Label className="mb-2">Transformation Type</Label>
                        <select
                          value={mappingForm.transformation_type}
                          onChange={(e) => setMappingForm({...mappingForm, transformation_type: e.target.value})}
                          className="w-full p-2 border rounded"
                        >
                          {TRANSFORMATION_TYPES.map(type => (
                            <option key={type.value} value={type.value}>
                              {type.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      
                      <div>
                        <Label className="mb-2">Field Type</Label>
                        <select
                          value={mappingForm.field_type}
                          onChange={(e) => setMappingForm({...mappingForm, field_type: e.target.value})}
                          className="w-full p-2 border rounded"
                        >
                          {FIELD_TYPES.map(type => (
                            <option key={type} value={type}>{type}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    
                    <div className="flex gap-2 mt-4">
                      <Button 
                        onClick={editingMapping ? handleUpdateMapping : handleCreateMapping} 
                        size="sm"
                      >
                        <Save className="w-4 h-4 mr-1" />
                        {editingMapping ? 'Update' : 'Create'}
                      </Button>
                      <Button 
                        onClick={() => {
                          setShowMappingForm(false);
                          setEditingMapping(null);
                          resetMappingForm();
                        }} 
                        variant="outline" 
                        size="sm"
                      >
                        <X className="w-4 h-4 mr-1" />
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {mappings.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Settings className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No field mappings configured yet.</p>
                    <p className="text-sm">Add mappings to define how extracted fields populate your EHR tables.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {mappings.map((mapping) => (
                      <div key={mapping.id} className="p-3 border rounded-lg hover:bg-gray-50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 flex-1">
                            <div className="text-sm">
                              <span className="font-mono text-blue-600">{mapping.source_section}</span>
                              <span className="text-gray-400 mx-1">.</span>
                              <span className="font-mono text-blue-600">{mapping.source_field}</span>
                            </div>
                            <ArrowRight className="w-4 h-4 text-gray-400" />
                            <div className="text-sm">
                              <span className="font-medium text-green-600">{mapping.target_table}</span>
                              <span className="text-gray-400 mx-1">.</span>
                              <span className="font-mono text-green-600">{mapping.target_field}</span>
                            </div>
                            <span className="text-xs px-2 py-1 bg-gray-100 rounded">
                              {mapping.transformation_type}
                            </span>
                          </div>
                          
                          <div className="flex gap-2">
                            <Button 
                              onClick={() => handleEditMapping(mapping)} 
                              variant="outline" 
                              size="sm"
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button 
                              onClick={() => handleDeleteMapping(mapping.id)} 
                              variant="destructive" 
                              size="sm"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <FileText className="w-16 h-16 text-gray-300 mb-4" />
                <p className="text-gray-500 text-center">
                  Select a template to view and configure field mappings
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExtractionConfiguration;
