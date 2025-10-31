import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import GPValidationInterface from '@/components/GPValidationInterface';
import { useToast } from '@/hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const ValidationReview = () => {
  const { extractionId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [extractionData, setExtractionData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [documentStatus, setDocumentStatus] = useState(null);

  useEffect(() => {
    loadExtractionData();
  }, [extractionId]);

  const loadExtractionData = async () => {
    try {
      setLoading(true);
      setError(null);

      // The extractionId is actually the document_id
      const documentId = extractionId;

      // Step 1: Fetch document metadata
      const docResponse = await axios.get(
        `${BACKEND_URL}/api/gp/documents/${documentId}`
      );
      
      console.log('Document response:', docResponse.data);
      
      // The API returns {status: 'success', document: {...}}
      const documentData = docResponse.data.document || docResponse.data.data || docResponse.data;
      console.log('Document data:', documentData);
      
      const parsedDocId = documentData.parsed_doc_id;
      
      if (!parsedDocId) {
        console.error('Document missing parsed_doc_id:', documentData);
        throw new Error('Document has not been parsed yet. Please parse the document first.');
      }

      // Step 2: Fetch parsed document data with extractions
      const parsedResponse = await axios.get(
        `${BACKEND_URL}/api/gp/parsed-document/${parsedDocId}`
      );
      
      const parsedData = parsedResponse.data;
      console.log('Parsed data:', parsedData);
      
      // Format data for GPValidationInterface (same structure as DigitisedDocuments)
      const formattedData = {
        success: true,
        data: {
          success: true,
          message: 'Document loaded successfully',
          data: {
            document_id: documentId,
            parsed_doc_id: parsedDocId,
            file_path: documentData.file_path,
            extractions: parsedData.data || {},
            chunks: parsedData.chunks || [],
            success: true
          }
        }
      };

      console.log('Formatted data for GPValidationInterface:', formattedData);
      setExtractionData(formattedData);
    } catch (error) {
      console.error('Failed to load extraction data:', error);
      setError('Failed to load extraction data');
      toast({
        variant: "destructive",
        title: "Error",
        description: error.response?.data?.detail || error.message || "Failed to load extraction data. Please try again."
      });
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    navigate('/validation-queue');
  };

  const handleValidationComplete = async (validatedData) => {
    try {
      // Mark as approved in validation system
      await axios.post(`${BACKEND_URL}/api/validation/approve`, {
        extraction_id: extractionId,
        validated_by: 'current-user', // TODO: Get from auth context
        notes: 'Validated through review interface'
      });

      toast({
        title: "Validation Complete ✅",
        description: "Data has been validated and saved successfully"
      });

      // Navigate back to queue
      navigate('/validation-queue');
    } catch (error) {
      console.error('Failed to complete validation:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to save validation. Please try again."
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading extraction data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="text-red-600 text-xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold mb-2">Error Loading Data</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Back to Queue
          </button>
        </div>
      </div>
    );
  }

  if (!extractionData) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-gray-600">No extraction data found</p>
          <button
            onClick={handleBack}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Back to Queue
          </button>
        </div>
      </div>
    );
  }

  return (
    <GPValidationInterface
      patientData={extractionData}
      onBack={handleBack}
      onValidationComplete={handleValidationComplete}
    />
  );
};

export default ValidationReview;
