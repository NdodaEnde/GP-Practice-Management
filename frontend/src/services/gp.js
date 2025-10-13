import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// GP-specific API calls
export const gpAPI = {
  /**
   * Upload patient file for processing
   * @param {File} file - The patient file to upload
   * @param {string} patientId - Optional existing patient ID
   * @param {string} extractionMode - 'full' or 'partial'
   */
  uploadPatientFile: async (file, patientId = undefined, extractionMode = 'full') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('processing_mode', 'smart');
    formData.append('save_to_database', 'true');
    
    if (patientId) {
      formData.append('patient_id', patientId);
    }

    try {
      // Call through the main backend which will proxy to microservice
      const response = await axios.post(
        `${API_BASE_URL}/api/gp/upload-patient-file`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 180000, // 3 minute timeout (processing can take 2+ minutes)
        }
      );

      return {
        success: true,
        data: response.data,
        message: 'File processed successfully'
      };
    } catch (error) {
      console.error('GP file upload error:', error);
      return {
        success: false,
        message: error.response?.data?.detail || error.message || 'Upload failed',
        error: error
      };
    }
  },

  /**
   * Validate and save extracted data
   * @param {string} patientId - Patient ID
   * @param {object} validatedData - The validated/corrected data
   * @param {object} validationStatuses - Validation status for each section
   */
  validateExtraction: async (patientId, validatedData, validationStatuses) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/gp/validate-extraction`,
        {
          patient_id: patientId,
          validated_data: validatedData,
          validation_statuses: validationStatuses,
          validator_notes: ''
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Validation error:', error);
      return {
        success: false,
        message: error.response?.data?.detail || error.message || 'Validation failed',
        error: error
      };
    }
  },

  /**
   * Get list of processed patients
   */
  getPatientsList: async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/gp/patients`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Get patients list error:', error);
      return {
        success: false,
        message: error.message,
        data: []
      };
    }
  },

  /**
   * Get chronic summary for a patient
   * @param {string} patientId - Patient ID
   */
  getChronicSummary: async (patientId) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/gp/patient/${patientId}/chronic-summary`
      );
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Get chronic summary error:', error);
      return {
        success: false,
        message: error.message
      };
    }
  },

  /**
   * Get parsed document
   * @param {string} documentId - Document ID
   */
  getParsedDocument: async (documentId) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/gp/parsed-document/${documentId}`
      );
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Get parsed document error:', error);
      return {
        success: false,
        message: error.message
      };
    }
  },

  /**
   * Get GP statistics
   */
  getStatistics: async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/gp/statistics`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Get GP statistics error:', error);
      return {
        success: false,
        message: error.message
      };
    }
  }
};

// TypeScript-like type definitions for reference (as JSDoc comments)
/**
 * @typedef {Object} GPPatientFile
 * @property {boolean} success
 * @property {Object} data
 * @property {string} data.patient_id
 * @property {string} data.document_id
 * @property {number} data.processing_time
 * @property {number} data.pages_processed
 * @property {string} data.model_used
 * @property {Object} data.extractions
 * @property {Object} data.extractions.demographics
 * @property {Object} data.extractions.chronic_summary
 * @property {Object} data.extractions.vitals
 * @property {Object} data.extractions.clinical_notes
 * @property {Object} data.confidence_scores
 * @property {Array} data.chunks
 * @property {string} [message]
 */

export default gpAPI;
