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

// Configure PDF.js worker - use jsdelivr CDN (more reliable)
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

const GPValidationInterface = ({ patientData, onBack, onValidationComplete }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfScale, setPdfScale] = useState(1.0);
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
  const filePath = responseData.file_path || '';
  const documentId = responseData.document_id || '';

  console.log('4. Extracted data:', extractedData);
  console.log('5. Demographics:', demographics);
  console.log('6. Chunks:', chunks.length);
  console.log('7. File path:', filePath);
  console.log('8. Document ID:', documentId);

  // For PDF viewing - construct URL after documentId is defined
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
  const pdfUrl = documentId ? `${backendUrl}/api/gp/document/${documentId}/view` : null;
  
  console.log('9. PDF URL will be:', pdfUrl);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  const goToPrevPage = () => setPageNumber(prev => Math.max(prev - 1, 1));
  const goToNextPage = () => setPageNumber(prev => Math.min(prev + 1, numPages || 1));
  const zoomIn = () => setPdfScale(prev => Math.min(prev + 0.2, 2.0));
  const zoomOut = () => setPdfScale(prev => Math.max(prev - 0.2, 0.5));

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
        {/* Left Panel - Document Preview with PDF Viewer */}
        <div className="w-1/2 border-r bg-white overflow-hidden flex flex-col">
          <div className="p-4 border-b bg-gray-50">
            <h3 className="font-semibold flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Original Document
            </h3>
            {numPages && (
              <div className="flex items-center gap-2 mt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToPrevPage}
                  disabled={pageNumber <= 1}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm">
                  Page {pageNumber} of {numPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToNextPage}
                  disabled={pageNumber >= numPages}
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
                <div className="ml-4 flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={zoomOut}>
                    <ZoomOut className="w-4 h-4" />
                  </Button>
                  <span className="text-sm">{Math.round(pdfScale * 100)}%</span>
                  <Button variant="outline" size="sm" onClick={zoomIn}>
                    <ZoomIn className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
          
          <div className="flex-1 overflow-auto p-4 bg-gray-100">
            {pdfUrl ? (
              <div className="flex justify-center">
                <Document
                  file={pdfUrl}
                  onLoadSuccess={onDocumentLoadSuccess}
                  onLoadError={(error) => {
                    console.error('PDF Load Error:', error);
                    console.error('PDF URL:', pdfUrl);
                  }}
                  loading={
                    <div className="flex items-center justify-center p-8">
                      <div className="text-center">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto mb-4"></div>
                        <p className="text-gray-600">Loading PDF...</p>
                        <p className="text-xs text-gray-400 mt-2">Document ID: {documentId}</p>
                      </div>
                    </div>
                  }
                  error={
                    <div className="text-center text-red-600 p-8">
                      <p className="font-semibold">Failed to load PDF</p>
                      <p className="text-sm text-gray-600 mt-2">
                        Document ID: {documentId}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        URL: {pdfUrl}
                      </p>
                      <p className="text-xs text-gray-500 mt-2">
                        Check browser console for details
                      </p>
                    </div>
                  }
                  options={{
                    cMapUrl: 'https://unpkg.com/pdfjs-dist@3.11.174/cmaps/',
                    cMapPacked: true,
                  }}
                >
                  <Page 
                    pageNumber={pageNumber} 
                    scale={pdfScale}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                  />
                </Document>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400">
                <div className="text-center">
                  <FileText className="w-16 h-16 mx-auto mb-4" />
                  <p>Document not available</p>
                  <p className="text-sm mt-2">PDF path: {filePath || 'Not provided'}</p>
                  <p className="text-sm">Document ID: {documentId || 'Not provided'}</p>
                </div>
              </div>
            )}
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
                    <div className="space-y-4">
                      {chronicSummary.chronic_conditions && (
                        <div>
                          <h3 className="font-medium text-gray-700 mb-2">Chronic Conditions</h3>
                          <div className="space-y-2">
                            {Array.isArray(chronicSummary.chronic_conditions) ? (
                              chronicSummary.chronic_conditions.map((condition, idx) => (
                                <div key={idx} className="p-2 bg-gray-50 rounded border">
                                  {typeof condition === 'object' ? (
                                    <div className="space-y-1">
                                      {Object.entries(condition).map(([key, val]) => (
                                        <div key={key} className="flex justify-between text-sm">
                                          <span className="text-gray-600 capitalize">{key.replace(/_/g, ' ')}:</span>
                                          <span className="font-medium">{val || 'N/A'}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    condition
                                  )}
                                </div>
                              ))
                            ) : (
                              <div className="p-2 bg-gray-50 rounded border">
                                {JSON.stringify(chronicSummary.chronic_conditions)}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      
                      {chronicSummary.current_medications && (
                        <div>
                          <h3 className="font-medium text-gray-700 mb-2">Current Medications</h3>
                          <div className="space-y-2">
                            {Array.isArray(chronicSummary.current_medications) ? (
                              chronicSummary.current_medications.map((med, idx) => (
                                <div key={idx} className="p-2 bg-gray-50 rounded border">
                                  {typeof med === 'object' ? (
                                    <div className="space-y-1">
                                      {Object.entries(med).map(([key, val]) => (
                                        <div key={key} className="flex justify-between text-sm">
                                          <span className="text-gray-600 capitalize">{key.replace(/_/g, ' ')}:</span>
                                          <span className="font-medium">{val || 'N/A'}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    med
                                  )}
                                </div>
                              ))
                            ) : (
                              <div className="p-2 bg-gray-50 rounded border">
                                {JSON.stringify(chronicSummary.current_medications)}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      
                      {/* Show other fields */}
                      {Object.entries(chronicSummary)
                        .filter(([key]) => key !== 'chronic_conditions' && key !== 'current_medications')
                        .map(([key, value]) => (
                          <div key={key}>
                            <h3 className="font-medium text-gray-700 mb-2 capitalize">
                              {key.replace(/_/g, ' ')}
                            </h3>
                            <div className="p-2 bg-gray-50 rounded border">
                              {typeof value === 'object' ? JSON.stringify(value, null, 2) : value || 'N/A'}
                            </div>
                          </div>
                        ))}
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
                    Object.entries(vitals).map(([key, value]) => {
                      // Handle array of vital signs records
                      if (key === 'vital_signs_records' && Array.isArray(value)) {
                        return (
                          <div key={key} className="space-y-2">
                            <label className="text-sm font-medium text-gray-600 capitalize">
                              Vital Signs Records
                            </label>
                            {value.map((record, idx) => (
                              <div key={idx} className="p-3 bg-gray-50 rounded border space-y-1">
                                {Object.entries(record).map(([field, val]) => (
                                  <div key={field} className="flex justify-between text-sm">
                                    <span className="text-gray-600 capitalize">
                                      {field.replace(/_/g, ' ')}:
                                    </span>
                                    <span className="font-medium">
                                      {typeof val === 'object' ? JSON.stringify(val) : val || 'N/A'}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            ))}
                          </div>
                        );
                      }
                      
                      // Handle other fields
                      return (
                        <div key={key} className="flex flex-col">
                          <label className="text-sm font-medium text-gray-600 capitalize mb-1">
                            {key.replace(/_/g, ' ')}
                          </label>
                          <div className="p-2 bg-gray-50 rounded border">
                            {typeof value === 'object' ? JSON.stringify(value, null, 2) : value || 'Not recorded'}
                          </div>
                        </div>
                      );
                    })
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
