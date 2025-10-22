import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import GPValidationInterface from '@/components/GPValidationInterface';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';

const DocumentValidation = () => {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [patientData, setPatientData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      
      if (!document.parsed_doc_id) {
        throw new Error('Document has not been parsed yet');
      }
      
      // Get parsed data from microservice
      const parsedResponse = await axios.get(`${backendUrl}/api/gp/parsed-document/${document.parsed_doc_id}`);
      
      console.log('Parsed data:', parsedResponse.data);
      
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
            ...parsedResponse.data
          }
        }
      };
      
      setPatientData(formattedData);
      
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

  if (!patientData) {
    return null;
  }

  return (
    <GPValidationInterface 
      patientData={patientData}
      onApproved={handleApproved}
    />
  );
};

export default DocumentValidation;
