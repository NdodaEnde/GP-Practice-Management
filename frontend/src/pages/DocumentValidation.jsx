import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import GPValidationInterface from '@/components/GPValidationInterface';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { FileText, Sparkles, ArrowLeft } from 'lucide-react';
import axios from 'axios';

const DocumentValidation = () => {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [patientData, setPatientData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [documentStatus, setDocumentStatus] = useState(null);
  const [extracting, setExtracting] = useState(false);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  useEffect(() => {
    loadDocumentData();
  }, [documentId]);

  const loadDocumentData = async () => {
    try {
      setLoading(true);
      
      // Get document metadata from digitised_documents
      const docResponse = await axios.get(`${backendUrl}/api/gp/documents/${documentId}`);
      const document = docResponse.data.document;
      
      console.log('Document metadata:', document);
      setDocumentStatus(document.status);
      
      if (!document.parsed_doc_id) {
        throw new Error('Document has not been parsed yet');
      }
      
      // Only load full data if document is extracted or approved
      if (document.status === 'extracted' || document.status === 'approved') {
        // Get parsed data from MongoDB (our internal storage)
        const parsedResponse = await axios.get(`${backendUrl}/api/gp/parsed-document/${document.parsed_doc_id}`);
        
        console.log('Document metadata:', document);
        console.log('Parsed data from MongoDB:', parsedResponse.data);
        
        // Extract the microservice_response which has the full original structure
        const microserviceData = parsedResponse.data.microservice_response || {};
        
        // Format data for validation interface
        const formattedData = {
          success: true,
          data: {
            success: true,
            message: 'Patient file processed successfully',
            data: {
              success: true,
              document_id: documentId,
              parsed_doc_id: document.parsed_doc_id,
              scanned_doc_id: microserviceData.data?.scanned_doc_id,
              validation_session_id: microserviceData.data?.validation_session_id,
              extracted_data: parsedResponse.data.data || {},
              chunks: microserviceData.data?.chunks || [],
              file_path: document.file_path
            }
          }
        };
        
        setPatientData(formattedData);
      }
      
    } catch (error) {
      console.error('Error loading document:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to load document');
      toast({
        title: 'Error',
        description: 'Failed to load document data',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    try {
      setExtracting(true);
      
      const response = await axios.post(`${backendUrl}/api/gp/documents/${documentId}/extract`);
      
      toast({
        title: 'Success',
        description: 'Data extraction completed successfully'
      });
      
      // Reload document data to show extracted fields
      await loadDocumentData();
      
    } catch (error) {
      console.error('Error extracting document:', error);
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to extract document data',
        variant: 'destructive'
      });
    } finally {
      setExtracting(false);
    }
  };

  const handleApproved = () => {
    toast({
      title: 'Success',
      description: 'Document approved and patient record updated'
    });
    navigate('/gp/documents');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading document...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-2">Error Loading Document</h2>
          <p className="text-slate-600 mb-4">{error}</p>
          <button
            onClick={() => navigate('/gp/documents')}
            className="px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700"
          >
            Back to Documents
          </button>
        </div>
      </div>
    );
  }

  // Show extraction prompt if document is only parsed, not yet extracted
  if (documentStatus === 'parsed' && !patientData) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="bg-white border-b p-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate('/gp/documents')}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Documents
            </Button>
            <div>
              <h1 className="text-xl font-bold">Document Ready for Extraction</h1>
              <p className="text-sm text-gray-600">Click Extract to process structured data fields</p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 80px)' }}>
          <Card className="max-w-md">
            <CardContent className="pt-6 text-center">
              <div className="w-16 h-16 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileText className="w-8 h-8 text-teal-600" />
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Document Parsed Successfully</h2>
              <p className="text-gray-600 mb-6">
                The document has been parsed and is ready for data extraction. 
                Click the button below to extract structured fields (Demographics, Conditions, Vitals, Clinical Notes).
              </p>
              <Button 
                onClick={handleExtract}
                disabled={extracting}
                className="w-full gap-2 bg-teal-600 hover:bg-teal-700"
                size="lg"
              >
                {extracting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Extracting...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Extract Data
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (!patientData) {
    return null;
  }

  return (
    <GPValidationInterface 
      patientData={patientData}
      onBack={() => navigate('/gp/documents')}
      onValidationComplete={handleApproved}
    />
  );
};

export default DocumentValidation;
