import React, { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { MedicalDocumentRenderer } from '@/components/MarkdownRenderer';
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

// Configure PDF.js worker - use local bundled worker (no CORS issues)
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

const GPValidationInterface = ({ patientData, onBack, onValidationComplete }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfScale, setPdfScale] = useState(1.0);
  const [selectedChunkId, setSelectedChunkId] = useState(null);
  const [hoveredChunkId, setHoveredChunkId] = useState(null);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [leftWidth, setLeftWidth] = useState(50); // For resizable panels
  const [isDragging, setIsDragging] = useState(false);
  
  const { toast } = useToast();
  
  // Refs
  const pageRef = useRef(null);
  const pdfContainerRef = useRef(null);
  const overviewScrollRef = useRef(null);
  const chunkRefs = useRef({});
  const containerRef = useRef(null);

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

  // Memoize options to prevent unnecessary reloads
  const pdfOptions = useMemo(() => ({
    cMapUrl: 'https://unpkg.com/pdfjs-dist@3.11.174/cmaps/',
    cMapPacked: true,
  }), []);

  // PDF load success handler
  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  // Page load success handler
  const onPageLoadSuccess = (page) => {
    setPageSize({
      width: page.width,
      height: page.height
    });
  };

  // Scroll chunk into center view
  const scrollToChunk = useCallback((chunkId) => {
    const chunkElement = chunkRefs.current[chunkId];
    const scrollContainer = overviewScrollRef.current;
    
    if (chunkElement && scrollContainer) {
      const containerRect = scrollContainer.getBoundingClientRect();
      const elementRect = chunkElement.getBoundingClientRect();
      
      const containerCenter = containerRect.height / 2;
      const elementCenter = elementRect.height / 2;
      const scrollTop = scrollContainer.scrollTop + (elementRect.top - containerRect.top) - containerCenter + elementCenter;
      
      scrollContainer.scrollTo({
        top: scrollTop,
        behavior: 'smooth'
      });
    }
  }, []);

  // Scroll PDF to center the highlighted region
  const scrollToHighlightedRegion = useCallback((chunk) => {
    if (!chunk.grounding || !pdfContainerRef.current || !pageRef.current) return;
    
    const g = chunk.grounding;
    const containerHeight = pdfContainerRef.current.clientHeight;
    const pageHeight = pageRef.current.clientHeight;
    
    const regionCenterY = (g.box.top + (g.box.bottom - g.box.top) / 2) * pageHeight;
    const scrollTop = regionCenterY - containerHeight / 2;
    
    pdfContainerRef.current.scrollTo({
      top: Math.max(0, scrollTop),
      behavior: 'smooth'
    });
  }, []);

  // Handle chunk click - scroll to corresponding section and highlight
  const handleChunkClick = (chunkId, grounding, chunkIndex) => {
    const wasSelected = selectedChunkId === chunkId;
    setSelectedChunkId(wasSelected ? null : chunkId);
    
    if (!wasSelected && grounding && grounding.page !== undefined) {
      // Navigate to the page where this chunk is located
      setPageNumber(grounding.page + 1); // PDF pages are 1-indexed
      
      // Scroll to the highlighted region after a delay
      const chunk = chunks[chunkIndex];
      setTimeout(() => scrollToHighlightedRegion(chunk), 200);
    }
    
    // Scroll markdown into view
    if (!wasSelected && activeTab === 'overview') {
      setTimeout(() => scrollToChunk(chunkId), 100);
    }
  };

  // Handle chunk hover
  const handleChunkHover = (chunkId) => {
    setHoveredChunkId(chunkId);
  };

  const handleChunkUnhover = () => {
    setHoveredChunkId(null);
  };

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
          
          <div className="flex-1 overflow-auto p-4 bg-gray-100" ref={pdfContainerRef}>
            {pdfUrl ? (
              <div className="flex justify-center relative">
                <Document
                  file={pdfUrl}
                  onLoadSuccess={onDocumentLoadSuccess}
                  onLoadError={(error) => {
                    console.error('PDF Load Error:', error);
                    console.error('PDF URL:', pdfUrl);
                  }}
                  options={pdfOptions}
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
                >
                  <div ref={pageRef} className="relative">
                    <Page 
                      pageNumber={pageNumber} 
                      scale={pdfScale}
                      renderTextLayer={false}
                      renderAnnotationLayer={false}
                      onLoadSuccess={onPageLoadSuccess}
                    />
                    
                    {/* Clickable overlay layer for grounding boxes */}
                    {pageSize.width > 0 && chunks.length > 0 && (
                      <div className="absolute inset-0 pointer-events-auto">
                        {chunks
                          .filter(chunk => chunk.grounding && (chunk.grounding.page + 1) === pageNumber)
                          .map((chunk, idx) => {
                            const chunkIndex = chunks.indexOf(chunk);
                            const chunkId = `chunk_${chunkIndex}`;
                            const isSelected = selectedChunkId === chunkId;
                            const isHovered = hoveredChunkId === chunkId;
                            
                            const box = chunk.grounding.box;
                            if (!box) return null;
                            
                            return (
                              <div
                                key={chunkId}
                                className={`absolute cursor-pointer transition-all ${
                                  isSelected 
                                    ? 'border-2 border-yellow-400 bg-yellow-300/30 shadow-lg z-20' 
                                    : isHovered
                                    ? 'border-2 border-blue-400 bg-blue-300/20 z-10'
                                    : 'border-2 border-transparent hover:border-blue-300 hover:bg-blue-300/10'
                                }`}
                                style={{
                                  left: `${box.left * 100}%`,
                                  top: `${box.top * 100}%`,
                                  width: `${(box.right - box.left) * 100}%`,
                                  height: `${(box.bottom - box.top) * 100}%`,
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleChunkClick(chunkId, chunk.grounding, chunkIndex);
                                }}
                                onMouseEnter={() => handleChunkHover(chunkId)}
                                onMouseLeave={handleChunkUnhover}
                                title={`Chunk ${chunkIndex + 1}: ${(chunk.markdown || '').substring(0, 50)}...`}
                              />
                            );
                          })}
                      </div>
                    )}
                  </div>
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
                {/* Parsed Document Content */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Parsed Document Content</CardTitle>
                    <p className="text-sm text-gray-600">
                      Click on any section to highlight and navigate to the corresponding area in the original document
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-3 max-h-[600px] overflow-y-auto" ref={overviewScrollRef}>
                    {chunks.length > 0 ? (
                      chunks.map((chunk, idx) => {
                        const chunkId = `chunk_${idx}`;
                        const isSelected = selectedChunkId === chunkId;
                        const isHovered = hoveredChunkId === chunkId;
                        
                        return (
                          <div
                            key={idx}
                            id={chunkId}
                            ref={el => chunkRefs.current[chunkId] = el}
                            className={`
                              p-3 rounded-lg border-2 transition-all duration-200 cursor-pointer
                              ${isSelected ? 'border-yellow-400 bg-yellow-50 shadow-lg' : 'border-gray-200'}
                              ${isHovered && !isSelected ? 'border-blue-300 bg-blue-50' : ''}
                              ${!isSelected && !isHovered ? 'hover:border-gray-300 hover:shadow-sm' : ''}
                            `}
                            onClick={() => handleChunkClick(chunkId, chunk.grounding, idx)}
                            onMouseEnter={() => handleChunkHover(chunkId)}
                            onMouseLeave={handleChunkUnhover}
                          >
                            <div className="flex items-start gap-2">
                              <span className="text-xs font-semibold text-gray-500 mt-1">
                                {chunk.grounding?.page !== undefined ? `P${chunk.grounding.page + 1}` : 'N/A'}
                              </span>
                              <div className="flex-1">
                                <div className="text-sm text-gray-800">
                                  <MedicalDocumentRenderer content={chunk.markdown || chunk.text || 'No content'} />
                                </div>
                              </div>
                            </div>
                            {(isSelected || isHovered) && (
                              <div className="mt-2 text-xs text-gray-500">
                                📍 Page {(chunk.grounding?.page || 0) + 1} 
                                {chunk.grounding?.box && ` • Box: (${Math.round(chunk.grounding.box.top * 100)}%, ${Math.round(chunk.grounding.box.left * 100)}%)`}
                              </div>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-gray-500 text-center py-8">No parsed content available</p>
                    )}
                  </CardContent>
                </Card>

                {/* Processing Stats - Collapsed */}
                <Card className="bg-gray-50">
                  <CardHeader>
                    <CardTitle className="text-sm">Processing Statistics</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Status:</span>
                        <span className="font-medium text-green-600 flex items-center gap-1">
                          <CheckCircle className="w-4 h-4" />
                          Complete
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Processing Time:</span>
                        <span className="font-medium">
                          {processingTime ? `${processingTime.toFixed(1)}s` : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Pages:</span>
                        <span className="font-medium">{pagesProcessed || 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Chunks:</span>
                        <span className="font-medium">{chunks.length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Model:</span>
                        <span className="font-medium">{modelUsed}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Sections:</span>
                        <span className="font-medium">{Object.keys(extractedData).length}</span>
                      </div>
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
