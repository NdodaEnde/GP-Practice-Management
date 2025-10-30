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

  useEffect(() => {
    loadExtractionData();
  }, [extractionId]);

  const loadExtractionData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch extraction details
      const response = await axios.get(
        `${BACKEND_URL}/api/validation/extraction/${extractionId}`
      );

      const extraction = response.data;
      
      // Format data for GPValidationInterface
      // GPValidationInterface expects a structure with nested data
      const formattedData = {
        data: {
          data: {
            document_id: extraction.document_id,
            workspace_id: extraction.workspace_id,
            extractions: extraction.extracted_data || {},
            chunks: extraction.chunks || [],
            metadata: extraction.metadata || {}
          }
        },
        document_id: extraction.document_id,
        extraction_id: extraction.id
      };

      setExtractionData(formattedData);
    } catch (error) {
      console.error('Failed to load extraction data:', error);
      setError('Failed to load extraction data');
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to load extraction data. Please try again."
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
