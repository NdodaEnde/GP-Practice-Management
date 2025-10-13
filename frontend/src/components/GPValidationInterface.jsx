import React, { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import {
  ArrowLeft,
  CheckCircle,
  FileText,
  User,
  Heart,
  Activity,
  FileCheck,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut
} from 'lucide-react';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

const GPValidationInterface = ({ patientData, onBack, onValidationComplete }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const { toast } = useToast();

  const handleValidate = () => {
    toast({
      title: "Data Validated",
      description: "Patient data has been validated and saved successfully",
    });
    if (onValidationComplete) {
      onValidationComplete();
    }
  };

  console.log('=== GPValidationInterface Debug ===');
  console.log('1. patientData:', patientData);
  console.log('2. patientData.data:', patientData?.data);
  console.log('3. patientData.data.data:', patientData?.data?.data);

  // Handle nested data structure from microservice
  const responseData = patientData?.data?.data || patientData?.data || {};
  const extractedData = responseData.extractions || {};
  const demographics = extractedData.demographics || {};
  const chronicSummary = extractedData.chronic_summary || {};
  const vitals = extractedData.vitals || {};
  const clinicalNotes = extractedData.clinical_notes || {};
  
  const processingTime = responseData.processing_time;
  const pagesProcessed = responseData.pages_processed;
  const modelUsed = responseData.model_used || 'LandingAI';
  const chunks = responseData.chunks || [];

  console.log('4. Extracted data:', extractedData);
  console.log('5. Demographics:', demographics);
  console.log('6. Chunks:', chunks.length);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b p-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={onBack}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Upload
          </Button>
          <div>
            <h1 className="text-xl font-bold">GP Patient Data Validation</h1>
            <p className="text-sm text-gray-600">Review and validate extracted data</p>
          </div>
        </div>
        <Button onClick={handleValidate} className="gap-2 bg-teal-600 hover:bg-teal-700">
          <FileCheck className="w-4 h-4" />
          Save Validated Data
        </Button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex">
        {/* Left Panel - Document Preview (Placeholder) */}
        <div className="w-1/2 border-r bg-white p-4 overflow-auto">
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <FileText className="w-16 h-16 mx-auto mb-4" />
              <p>Document preview will appear here</p>
              <p className="text-sm mt-2">PDF viewer coming soon</p>
            </div>
          </div>
        </div>

        {/* Right Panel - Extracted Data */}
        <div className="w-1/2 flex flex-col">
          {/* Tabs */}
          <div className="bg-white border-b p-4">
            <div className="flex gap-2">
              {[
                { id: 'overview', label: 'Overview', icon: FileText },
                { id: 'demographics', label: 'Demographics', icon: User },
                { id: 'chronic', label: 'Chronic Care', icon: Heart },
                { id: 'vitals', label: 'Vitals', icon: Activity },
              ].map(tab => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`
                      flex items-center gap-2 px-4 py-2 rounded-lg transition-colors
                      ${activeTab === tab.id 
                        ? 'bg-teal-100 text-teal-700 font-medium' 
                        : 'text-gray-600 hover:bg-gray-100'
                      }
                    `}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-auto p-6 space-y-6">
            {activeTab === 'overview' && (
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Processing Summary</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className="font-medium text-green-600 flex items-center gap-1">
                        <CheckCircle className="w-4 h-4" />
                        Processing Complete
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Processing Time:</span>
                      <span className="font-medium">
                        {processingTime ? `${processingTime.toFixed(1)}s` : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Pages Processed:</span>
                      <span className="font-medium">{pagesProcessed || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Model Used:</span>
                      <span className="font-medium">{modelUsed}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Chunks Extracted:</span>
                      <span className="font-medium">{chunks.length}</span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Extracted Sections</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.keys(extractedData).length > 0 ? (
                        Object.keys(extractedData).map(section => (
                          <div key={section} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                            <span className="capitalize">{section.replace('_', ' ')}</span>
                            <CheckCircle className="w-4 h-4 text-green-500" />
                          </div>
                        ))
                      ) : (
                        <p className="text-gray-500 text-sm">No data extracted yet</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {activeTab === 'demographics' && (
              <Card>
                <CardHeader>
                  <CardTitle>Patient Demographics</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.keys(demographics).length > 0 ? (
                    Object.entries(demographics).map(([key, value]) => (
                      <div key={key} className="flex flex-col">
                        <label className="text-sm font-medium text-gray-600 capitalize mb-1">
                          {key.replace(/_/g, ' ')}
                        </label>
                        <div className="p-2 bg-gray-50 rounded border">
                          {typeof value === 'object' ? JSON.stringify(value) : value || 'Not available'}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500">No demographic data extracted</p>
                  )}
                </CardContent>
              </Card>
            )}

            {activeTab === 'chronic' && (
              <Card>
                <CardHeader>
                  <CardTitle>Chronic Care Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.keys(chronicSummary).length > 0 ? (
                    <div>
                      <h3 className="font-medium mb-2">Conditions & Medications</h3>
                      {chronicSummary.conditions && (
                        <div className="mb-4">
                          <p className="text-sm text-gray-600 mb-2">Conditions:</p>
                          <div className="p-2 bg-gray-50 rounded border">
                            {Array.isArray(chronicSummary.conditions) 
                              ? chronicSummary.conditions.map((c, i) => (
                                  <div key={i} className="mb-1">{c.condition || c}</div>
                                ))
                              : JSON.stringify(chronicSummary.conditions)
                            }
                          </div>
                        </div>
                      )}
                      {chronicSummary.medications && (
                        <div>
                          <p className="text-sm text-gray-600 mb-2">Medications:</p>
                          <div className="p-2 bg-gray-50 rounded border">
                            {Array.isArray(chronicSummary.medications) 
                              ? chronicSummary.medications.map((m, i) => (
                                  <div key={i} className="mb-1">{m.medication || m}</div>
                                ))
                              : JSON.stringify(chronicSummary.medications)
                            }
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-gray-500">No chronic care data extracted</p>
                  )}
                </CardContent>
              </Card>
            )}

            {activeTab === 'vitals' && (
              <Card>
                <CardHeader>
                  <CardTitle>Vital Signs</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.keys(vitals).length > 0 ? (
                    Object.entries(vitals).map(([key, value]) => (
                      <div key={key} className="flex flex-col">
                        <label className="text-sm font-medium text-gray-600 capitalize mb-1">
                          {key.replace(/_/g, ' ')}
                        </label>
                        <div className="p-2 bg-gray-50 rounded border">
                          {typeof value === 'object' ? JSON.stringify(value) : value || 'Not recorded'}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500">No vital signs data extracted</p>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GPValidationInterface;
