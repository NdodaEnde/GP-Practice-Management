import React, { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { MedicalDocumentRenderer } from '@/components/MarkdownRenderer';
import PatientMatchDialog from '@/components/PatientMatchDialog';
import axios from 'axios';
import {
  ArrowLeft,
  CheckCircle,
  FileText,
  User,
  Heart,
  Activity,
  FileCheck,
  ZoomIn,
  ZoomOut,
  Edit,
  Save,
  X,
  AlertTriangle,
  Plus,
  Trash2
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
  const [isSaving, setIsSaving] = useState(false);
  
  // Patient matching state
  const [showMatchDialog, setShowMatchDialog] = useState(false);
  const [patientMatches, setPatientMatches] = useState([]);
  const [isMatchingPatient, setIsMatchingPatient] = useState(false);
  
  // Editable data state
  const [editedDemographics, setEditedDemographics] = useState({});
  const [editedChronicCare, setEditedChronicCare] = useState({});
  const [editedVitals, setEditedVitals] = useState({});
  const [editedClinicalNotes, setEditedClinicalNotes] = useState({});
  const [modifications, setModifications] = useState([]);
  
  const { toast } = useToast();
  
  // Refs
  const pageRef = useRef(null);
  const pdfContainerRef = useRef(null);
  const overviewScrollRef = useRef(null);
  const chunkRefs = useRef({});
  const containerRef = useRef(null);

  console.log('=== GPValidationInterface Debug ===');
  console.log('1. patientData:', patientData);
  console.log('2. patientData.data:', patientData?.data);
  console.log('3. patientData.data.data:', patientData?.data?.data);

  // Handle nested data structure from microservice
  const responseData = patientData?.data?.data || patientData?.data || {};
  const extractedData = responseData.extractions || {};
  const demographics = extractedData.demographics || {};
  const rawChronicSummary = extractedData.chronic_summary || {};
  const rawVitals = extractedData.vitals || {};
  
  // Normalize chronic_summary data structure
  // LandingAI returns: conditions_mentioned, medications_mentioned
  // We need: chronic_conditions, current_medications
  const chronicSummary = {
    ...rawChronicSummary,
    chronic_conditions: rawChronicSummary.conditions_mentioned || 
                        rawChronicSummary.chronic_conditions || 
                        [],
    current_medications: rawChronicSummary.medications_mentioned || 
                         rawChronicSummary.current_medications || 
                         []
  };
  
  // Normalize vitals data structure
  // LandingAI returns: vital_entries
  // We need: vital_signs_records
  const vitals = {
    ...rawVitals,
    vital_signs_records: rawVitals.vital_entries || 
                         rawVitals.vital_signs_records || 
                         []
  };
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

  // Initialize edited data with original values
  useEffect(() => {
    setEditedDemographics(JSON.parse(JSON.stringify(demographics)));
    setEditedChronicCare(JSON.parse(JSON.stringify(chronicSummary)));
    setEditedVitals(JSON.parse(JSON.stringify(vitals)));
    setEditedClinicalNotes(JSON.parse(JSON.stringify(clinicalNotes)));
  }, [documentId]);

  // Track field modification
  const trackModification = (fieldPath, originalValue, newValue, section) => {
    const modification = {
      field_path: `${section}.${fieldPath}`,
      original_value: originalValue,
      new_value: newValue,
      timestamp: new Date().toISOString(),
      modification_type: 'edit'
    };
    setModifications(prev => [...prev, modification]);
  };

  // Handle save validated data - Step 1: Find patient matches
  const handleValidate = async () => {
    setIsSaving(true);
    setIsMatchingPatient(true);
    
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      // Step 1: Search for patient matches
      const matchResponse = await axios.post(
        `${backendUrl}/api/gp/validation/match-patient`,
        {
          document_id: documentId,
          demographics: editedDemographics
        }
      );

      setPatientMatches(matchResponse.data.matches || []);
      setShowMatchDialog(true);
      setIsMatchingPatient(false);
      
    } catch (error) {
      console.error('Error finding patient matches:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to search for patient matches",
        variant: "destructive"
      });
      setIsMatchingPatient(false);
    } finally {
      setIsSaving(false);
    }
  };

  // Handle confirm patient match
  const handleConfirmMatch = async (matchedPatient) => {
    setIsSaving(true);
    
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const validatedData = {
        demographics: editedDemographics,
        chronic_summary: editedChronicCare,
        vitals: editedVitals,
        clinical_notes: editedClinicalNotes
      };

      // Confirm match and create encounter
      const response = await axios.post(
        `${backendUrl}/api/gp/validation/confirm-match`,
        {
          document_id: documentId,
          patient_id: matchedPatient.patient_id,
          parsed_data: validatedData,
          modifications: modifications
        }
      );

      toast({
        title: "Success",
        description: `Patient matched successfully. Encounter created for ${matchedPatient.first_name} ${matchedPatient.last_name}`,
      });

      setShowMatchDialog(false);
      
      if (onValidationComplete) {
        onValidationComplete(response.data);
      }
    } catch (error) {
      console.error('Error confirming patient match:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to confirm patient match",
        variant: "destructive"
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Handle create new patient
  const handleCreateNewPatient = async (extractedData) => {
    setIsSaving(true);
    
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const validatedData = {
        demographics: editedDemographics,
        chronic_summary: editedChronicCare,
        vitals: editedVitals,
        clinical_notes: editedClinicalNotes
      };

      // Create new patient and encounter
      const response = await axios.post(
        `${backendUrl}/api/gp/validation/create-new-patient`,
        {
          document_id: documentId,
          demographics: editedDemographics,
          parsed_data: validatedData,
          modifications: modifications
        }
      );

      toast({
        title: "Success",
        description: "New patient created and encounter added to their record",
      });

      setShowMatchDialog(false);
      
      if (onValidationComplete) {
        onValidationComplete(response.data);
      }
    } catch (error) {
      console.error('Error creating new patient:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to create new patient",
        variant: "destructive"
      });
    } finally {
      setIsSaving(false);
    }
  };

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
    const container = pdfContainerRef.current;
    const containerHeight = container.clientHeight;
    const singlePageHeight = pageRef.current.clientHeight;
    
    // For continuous scrolling, calculate position based on page number
    const pageNumber = g.page; // 0-indexed
    const marginBetweenPages = 16; // mb-4 = 16px in Tailwind
    
    // Calculate total scroll offset to reach this page
    const scrollToPage = (singlePageHeight + marginBetweenPages) * pageNumber;
    
    // Add offset within the page for the specific box
    const regionCenterY = (g.box.top + (g.box.bottom - g.box.top) / 2) * singlePageHeight;
    
    // Center the region in the viewport
    const scrollTop = scrollToPage + regionCenterY - containerHeight / 2;
    
    container.scrollTo({
      top: Math.max(0, scrollTop),
      behavior: 'smooth'
    });
  }, []);

  // Handle chunk click - scroll to corresponding section and highlight
  const handleChunkClick = (chunkId, grounding, chunkIndex) => {
    const wasSelected = selectedChunkId === chunkId;
    setSelectedChunkId(wasSelected ? null : chunkId);
    
    if (!wasSelected && grounding && grounding.page !== undefined) {
      // Scroll to the highlighted region
      // Note: We DON'T change pageNumber to avoid PDF jumping back
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

  // Mouse handling for resizable divider
  const handleMouseDown = (e) => {
    setIsDragging(true);
    e.preventDefault();
  };

  const handleMouseMove = useCallback((e) => {
    if (!isDragging || !containerRef.current) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();
    const newLeftWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100;
    
    const clampedWidth = Math.max(30, Math.min(70, newLeftWidth));
    setLeftWidth(clampedWidth);
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      const doc = window.document;
      doc.addEventListener('mousemove', handleMouseMove);
      doc.addEventListener('mouseup', handleMouseUp);
      return () => {
        doc.removeEventListener('mousemove', handleMouseMove);
        doc.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

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
        <Button 
          onClick={handleValidate} 
          disabled={isSaving}
          className="gap-2 bg-teal-600 hover:bg-teal-700"
        >
          {isSaving ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              Saving...
            </>
          ) : (
            <>
              <FileCheck className="w-4 h-4" />
              Save Validated Data
            </>
          )}
        </Button>
      </div>

      {/* Main Content */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-hidden flex"
        style={{ cursor: isDragging ? 'col-resize' : 'default' }}
      >
        {/* Left Panel - Document Preview with All Pages */}
        <div 
          className="border-r bg-white overflow-hidden flex flex-col"
          style={{ width: `${leftWidth}%` }}
        >
          <div className="p-4 border-b bg-gray-50">
            <h3 className="font-semibold flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Original Document
            </h3>
            {numPages && (
              <div className="flex items-center gap-2 mt-2">
                <span className="text-sm">
                  {numPages} page{numPages > 1 ? 's' : ''} • {Math.round(pdfScale * 100)}%
                </span>
                <div className="ml-auto flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={zoomOut}>
                    <ZoomOut className="w-4 h-4" />
                  </Button>
                  <Button variant="outline" size="sm" onClick={zoomIn}>
                    <ZoomIn className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
          
          <div className="flex-1 overflow-auto p-4 bg-gray-100" ref={pdfContainerRef}>
            {pdfUrl ? (
              <div className="flex flex-col items-center gap-4">
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
                      <p className="text-sm text-gray-600 mt-2">Document ID: {documentId}</p>
                      <p className="text-xs text-gray-400 mt-1">URL: {pdfUrl}</p>
                    </div>
                  }
                >
                  {/* Render all pages for continuous scrolling */}
                  {Array.from(new Array(numPages), (el, index) => {
                    const currentPage = index + 1;
                    return (
                      <div key={`page_${currentPage}`} className="relative mb-4" ref={currentPage === 1 ? pageRef : null}>
                        <Page 
                          pageNumber={currentPage} 
                          scale={pdfScale}
                          renderTextLayer={false}
                          renderAnnotationLayer={false}
                          onLoadSuccess={currentPage === 1 ? onPageLoadSuccess : undefined}
                        />
                        
                        {/* Clickable overlay layer for grounding boxes on this page */}
                        {pageSize.width > 0 && chunks.length > 0 && (
                          <div className="absolute inset-0 pointer-events-auto">
                            {chunks
                              .filter(chunk => chunk.grounding && (chunk.grounding.page + 1) === currentPage)
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
                        
                        {/* Page number indicator */}
                        <div className="text-center mt-2 mb-2 text-xs text-gray-500">
                          Page {currentPage} of {numPages}
                        </div>
                      </div>
                    );
                  })}
                </Document>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400">
                <div className="text-center">
                  <FileText className="w-16 h-16 mx-auto mb-4" />
                  <p>Document not available</p>
                  <p className="text-sm mt-2">Document ID: {documentId || 'Not provided'}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Resizable Divider */}
        <div
          className="w-1 bg-gray-300 hover:bg-teal-500 cursor-col-resize flex-shrink-0 relative group transition-colors select-none"
          onMouseDown={handleMouseDown}
          style={{ touchAction: 'none' }}
        >
          <div className="absolute inset-y-0 -left-2 -right-2 group-hover:bg-teal-500 group-hover:bg-opacity-20" />
        </div>

        {/* Right Panel - Extracted Data */}
        <div 
          className="flex flex-col bg-white overflow-hidden"
          style={{ width: `${100 - leftWidth}%` }}
        >
          {/* Tabs */}
          <div className="bg-white border-b p-4">
            <div className="flex gap-2">
              {[
                { id: 'overview', label: 'Overview', icon: FileText },
                { id: 'demographics', label: 'Demographics', icon: User },
                { id: 'chronic', label: 'Chronic Care', icon: Heart },
                { id: 'vitals', label: 'Vitals', icon: Activity },
                { id: 'notes', label: 'Clinical Notes', icon: FileCheck },
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
                  <p className="text-sm text-gray-500">Edit patient information as needed</p>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.keys(editedDemographics).length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(editedDemographics).map(([key, value]) => (
                        <div key={key} className="flex flex-col">
                          <Label htmlFor={`demo-${key}`} className="text-sm font-medium text-gray-600 capitalize mb-2">
                            {key.replace(/_/g, ' ')}
                          </Label>
                          <Input
                            id={`demo-${key}`}
                            value={typeof value === 'object' ? JSON.stringify(value) : value || ''}
                            onChange={(e) => {
                              const originalValue = demographics[key];
                              const newValue = e.target.value;
                              if (originalValue !== newValue) {
                                trackModification(key, originalValue, newValue, 'demographics');
                              }
                              setEditedDemographics(prev => ({
                                ...prev,
                                [key]: newValue
                              }));
                            }}
                            className="border-gray-300 focus:border-teal-500"
                          />
                          {demographics[key] !== editedDemographics[key] && (
                            <span className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                              <Edit className="w-3 h-3" /> Modified
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500">No demographic data extracted</p>
                  )}
                </CardContent>
              </Card>
            )}

            {activeTab === 'chronic' && (
              <div className="space-y-4">
                {/* Chronic Conditions Table */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Chronic Conditions</CardTitle>
                        <p className="text-sm text-gray-500 mt-1">Click on rows to edit, add or remove conditions</p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          const newCondition = {
                            condition_name: '',
                            mentioned_date: '',
                            context: '',
                            is_chronic: null
                          };
                          setEditedChronicCare(prev => ({
                            ...prev,
                            chronic_conditions: [...(prev.chronic_conditions || []), newCondition]
                          }));
                        }}
                        className="gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        Add Condition
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {editedChronicCare.chronic_conditions && editedChronicCare.chronic_conditions.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse">
                          <thead>
                            <tr className="bg-gray-50 border-b">
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Condition</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Date</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Chronic?</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Context</th>
                              <th className="px-3 py-2 text-center text-xs font-medium text-gray-600">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {editedChronicCare.chronic_conditions.map((condition, idx) => (
                              <tr key={idx} className="border-b hover:bg-gray-50">
                                <td className="px-3 py-2">
                                  <Input
                                    value={condition.condition_name || ''}
                                    onChange={(e) => {
                                      const newConditions = [...editedChronicCare.chronic_conditions];
                                      newConditions[idx].condition_name = e.target.value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        chronic_conditions: newConditions
                                      }));
                                      trackModification(
                                        `chronic_conditions[${idx}].condition_name`,
                                        chronicSummary.chronic_conditions?.[idx]?.condition_name,
                                        e.target.value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-sm"
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <Input
                                    type="date"
                                    value={condition.mentioned_date || ''}
                                    onChange={(e) => {
                                      const newConditions = [...editedChronicCare.chronic_conditions];
                                      newConditions[idx].mentioned_date = e.target.value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        chronic_conditions: newConditions
                                      }));
                                      trackModification(
                                        `chronic_conditions[${idx}].mentioned_date`,
                                        chronicSummary.chronic_conditions?.[idx]?.mentioned_date,
                                        e.target.value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-sm"
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <select
                                    value={condition.is_chronic === null ? 'null' : condition.is_chronic.toString()}
                                    onChange={(e) => {
                                      const newConditions = [...editedChronicCare.chronic_conditions];
                                      const value = e.target.value === 'null' ? null : e.target.value === 'true';
                                      newConditions[idx].is_chronic = value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        chronic_conditions: newConditions
                                      }));
                                      trackModification(
                                        `chronic_conditions[${idx}].is_chronic`,
                                        chronicSummary.chronic_conditions?.[idx]?.is_chronic,
                                        value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:border-teal-500"
                                  >
                                    <option value="null">Unknown</option>
                                    <option value="true">Yes</option>
                                    <option value="false">No</option>
                                  </select>
                                </td>
                                <td className="px-3 py-2">
                                  <Textarea
                                    value={condition.context || ''}
                                    onChange={(e) => {
                                      const newConditions = [...editedChronicCare.chronic_conditions];
                                      newConditions[idx].context = e.target.value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        chronic_conditions: newConditions
                                      }));
                                      trackModification(
                                        `chronic_conditions[${idx}].context`,
                                        chronicSummary.chronic_conditions?.[idx]?.context,
                                        e.target.value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-sm min-h-[60px]"
                                    rows={2}
                                  />
                                </td>
                                <td className="px-3 py-2 text-center">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => {
                                      const newConditions = editedChronicCare.chronic_conditions.filter((_, i) => i !== idx);
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        chronic_conditions: newConditions
                                      }));
                                      trackModification(
                                        `chronic_conditions[${idx}]`,
                                        chronicSummary.chronic_conditions?.[idx],
                                        null,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-gray-500 text-center py-4">No chronic conditions recorded</p>
                    )}
                  </CardContent>
                </Card>

                {/* Medications Table */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Medications</CardTitle>
                        <p className="text-sm text-gray-500 mt-1">Manage current medications</p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          const newMedication = {
                            medication_name: '',
                            dosage_info: '',
                            mentioned_date: '',
                            context: '',
                            legibility: 'Clear'
                          };
                          setEditedChronicCare(prev => ({
                            ...prev,
                            current_medications: [...(prev.current_medications || []), newMedication]
                          }));
                        }}
                        className="gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        Add Medication
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {editedChronicCare.current_medications && editedChronicCare.current_medications.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse">
                          <thead>
                            <tr className="bg-gray-50 border-b">
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Medication</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Dosage</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Date</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Legibility</th>
                              <th className="px-3 py-2 text-center text-xs font-medium text-gray-600">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {editedChronicCare.current_medications.map((med, idx) => (
                              <tr key={idx} className="border-b hover:bg-gray-50">
                                <td className="px-3 py-2">
                                  <Input
                                    value={med.medication_name || ''}
                                    onChange={(e) => {
                                      const newMeds = [...editedChronicCare.current_medications];
                                      newMeds[idx].medication_name = e.target.value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        current_medications: newMeds
                                      }));
                                      trackModification(
                                        `current_medications[${idx}].medication_name`,
                                        chronicSummary.current_medications?.[idx]?.medication_name,
                                        e.target.value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-sm"
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <Input
                                    value={med.dosage_info || ''}
                                    onChange={(e) => {
                                      const newMeds = [...editedChronicCare.current_medications];
                                      newMeds[idx].dosage_info = e.target.value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        current_medications: newMeds
                                      }));
                                      trackModification(
                                        `current_medications[${idx}].dosage_info`,
                                        chronicSummary.current_medications?.[idx]?.dosage_info,
                                        e.target.value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-sm"
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <Input
                                    type="date"
                                    value={med.mentioned_date || ''}
                                    onChange={(e) => {
                                      const newMeds = [...editedChronicCare.current_medications];
                                      newMeds[idx].mentioned_date = e.target.value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        current_medications: newMeds
                                      }));
                                      trackModification(
                                        `current_medications[${idx}].mentioned_date`,
                                        chronicSummary.current_medications?.[idx]?.mentioned_date,
                                        e.target.value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-sm"
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <select
                                    value={med.legibility || 'Clear'}
                                    onChange={(e) => {
                                      const newMeds = [...editedChronicCare.current_medications];
                                      newMeds[idx].legibility = e.target.value;
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        current_medications: newMeds
                                      }));
                                      trackModification(
                                        `current_medications[${idx}].legibility`,
                                        chronicSummary.current_medications?.[idx]?.legibility,
                                        e.target.value,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:border-teal-500"
                                  >
                                    <option value="Clear">Clear</option>
                                    <option value="Partial">Partial</option>
                                    <option value="Poor">Poor</option>
                                  </select>
                                </td>
                                <td className="px-3 py-2 text-center">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => {
                                      const newMeds = editedChronicCare.current_medications.filter((_, i) => i !== idx);
                                      setEditedChronicCare(prev => ({
                                        ...prev,
                                        current_medications: newMeds
                                      }));
                                      trackModification(
                                        `current_medications[${idx}]`,
                                        chronicSummary.current_medications?.[idx],
                                        null,
                                        'chronic_summary'
                                      );
                                    }}
                                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-gray-500 text-center py-4">No medications recorded</p>
                    )}
                  </CardContent>
                </Card>
              </div>
            )}

            {activeTab === 'vitals' && (
              <Card>
                <CardHeader>
                  <CardTitle>Vital Signs</CardTitle>
                  <p className="text-sm text-gray-500 mt-1">Edit vital signs records</p>
                </CardHeader>
                <CardContent className="space-y-4">
                  {editedVitals.vital_signs_records && editedVitals.vital_signs_records.length > 0 ? (
                    <div className="space-y-3">
                      {editedVitals.vital_signs_records.map((record, idx) => (
                        <div key={idx} className="p-4 bg-gray-50 rounded-lg border-2 border-gray-200">
                          <div className="flex items-center justify-between mb-3">
                            <h4 className="font-medium text-gray-700">Record {idx + 1}</h4>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const newRecords = editedVitals.vital_signs_records.filter((_, i) => i !== idx);
                                setEditedVitals(prev => ({
                                  ...prev,
                                  vital_signs_records: newRecords
                                }));
                                trackModification(
                                  `vital_signs_records[${idx}]`,
                                  vitals.vital_signs_records?.[idx],
                                  null,
                                  'vitals'
                                );
                              }}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {Object.entries(record).map(([field, val]) => (
                              <div key={field} className="flex flex-col">
                                <Label htmlFor={`vital-${idx}-${field}`} className="text-xs font-medium text-gray-600 capitalize mb-1">
                                  {field.replace(/_/g, ' ')}
                                </Label>
                                <Input
                                  id={`vital-${idx}-${field}`}
                                  value={typeof val === 'object' ? JSON.stringify(val) : val || ''}
                                  onChange={(e) => {
                                    const newRecords = [...editedVitals.vital_signs_records];
                                    newRecords[idx][field] = e.target.value;
                                    setEditedVitals(prev => ({
                                      ...prev,
                                      vital_signs_records: newRecords
                                    }));
                                    trackModification(
                                      `vital_signs_records[${idx}].${field}`,
                                      vitals.vital_signs_records?.[idx]?.[field],
                                      e.target.value,
                                      'vitals'
                                    );
                                  }}
                                  className="text-sm"
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          const newRecord = {
                            date: '',
                            blood_pressure: '',
                            heart_rate: '',
                            temperature: '',
                            weight: '',
                            height: ''
                          };
                          setEditedVitals(prev => ({
                            ...prev,
                            vital_signs_records: [...(prev.vital_signs_records || []), newRecord]
                          }));
                        }}
                        className="gap-2 w-full"
                      >
                        <Plus className="w-4 h-4" />
                        Add Vital Signs Record
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-gray-500 mb-4">No vital signs records</p>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          const newRecord = {
                            date: '',
                            blood_pressure: '',
                            heart_rate: '',
                            temperature: '',
                            weight: '',
                            height: ''
                          };
                          setEditedVitals({
                            vital_signs_records: [newRecord]
                          });
                        }}
                        className="gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        Add First Record
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {activeTab === 'notes' && (
              <Card>
                <CardHeader>
                  <CardTitle>Clinical Notes</CardTitle>
                  <p className="text-sm text-gray-500 mt-1">Edit clinical notes and observations</p>
                </CardHeader>
                <CardContent>
                  <Textarea
                    value={typeof editedClinicalNotes === 'string' ? editedClinicalNotes : JSON.stringify(editedClinicalNotes, null, 2)}
                    onChange={(e) => {
                      const originalValue = typeof clinicalNotes === 'string' ? clinicalNotes : JSON.stringify(clinicalNotes);
                      const newValue = e.target.value;
                      if (originalValue !== newValue) {
                        trackModification('clinical_notes', originalValue, newValue, 'clinical_notes');
                      }
                      setEditedClinicalNotes(newValue);
                    }}
                    placeholder="Enter clinical notes and observations..."
                    className="min-h-[400px] font-mono text-sm"
                  />
                  {JSON.stringify(clinicalNotes) !== JSON.stringify(editedClinicalNotes) && (
                    <div className="mt-2 flex items-center gap-2 text-sm text-amber-600">
                      <Edit className="w-4 h-4" />
                      Clinical notes have been modified
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Patient Match Dialog */}
      <PatientMatchDialog
        isOpen={showMatchDialog}
        onClose={() => setShowMatchDialog(false)}
        matches={patientMatches}
        extractedData={editedDemographics}
        onConfirmMatch={handleConfirmMatch}
        onCreateNew={handleCreateNewPatient}
        isLoading={isSaving}
      />
    </div>
  );
};

export default GPValidationInterface;
