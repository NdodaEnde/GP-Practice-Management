import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  User, 
  CheckCircle, 
  AlertTriangle, 
  Calendar,
  Phone,
  CreditCard,
  X
} from 'lucide-react';

// Utility function to format date for display
const formatDateForDisplay = (dateStr) => {
  if (!dateStr) return 'Not available';
  
  try {
    // Handle various input formats: 1991.02:03, 1991.02.03, 1991-02-03, etc.
    let cleanDate = dateStr.toString().replace(/[.:]/g, '-');
    
    // Parse the date
    const parts = cleanDate.split('-');
    if (parts.length === 3) {
      // Determine if format is YYYY-MM-DD or DD-MM-YYYY based on first part length
      let year, month, day;
      
      if (parts[0].length === 4) {
        // YYYY-MM-DD format
        year = parts[0];
        month = parts[1].padStart(2, '0');
        day = parts[2].padStart(2, '0');
      } else {
        // DD-MM-YYYY format (already in desired format)
        day = parts[0].padStart(2, '0');
        month = parts[1].padStart(2, '0');
        year = parts[2];
      }
      
      // Return in DD/MM/YYYY format
      return `${day}/${month}/${year}`;
    }
    
    // If we can't parse it, return original
    return dateStr;
  } catch (e) {
    return dateStr;
  }
};

const PatientMatchDialog = ({ 
  isOpen, 
  onClose, 
  matches, 
  extractedData,
  onConfirmMatch,
  onCreateNew,
  isLoading 
}) => {
  const [selectedMatch, setSelectedMatch] = useState(null);

  if (!isOpen) return null;

  const getConfidenceColor = (score) => {
    if (score >= 0.95) return 'bg-green-100 text-green-800 border-green-300';
    if (score >= 0.70) return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    return 'bg-red-100 text-red-800 border-red-300';
  };

  const getConfidenceLabel = (score) => {
    if (score >= 0.95) return 'High Confidence';
    if (score >= 0.70) return 'Medium Confidence';
    return 'Low Confidence';
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-teal-600 text-white px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">Patient Matching</h2>
            <p className="text-sm text-teal-100">Review and confirm patient match</p>
          </div>
          <button onClick={onClose} className="text-white hover:bg-teal-700 p-2 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {matches && matches.length > 0 ? (
            <div className="space-y-6">
              {/* Extracted Data Section */}
              <div>
                <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <User className="w-5 h-5" />
                  Extracted from Document
                </h3>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-600">Name:</span>
                      <p className="font-medium">
                        {extractedData.first_name || extractedData.first_names || ''} {extractedData.last_name || extractedData.surname || ''}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-600">ID Number:</span>
                      <p className="font-medium">{extractedData.id_number || 'Not available'}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Date of Birth:</span>
                      <p className="font-medium">{formatDateForDisplay(extractedData.dob || extractedData.date_of_birth)}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Contact:</span>
                      <p className="font-medium">{extractedData.contact_number || 'Not available'}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Matches Section */}
              <div>
                <h3 className="font-semibold text-gray-700 mb-3">
                  Found {matches.length} Potential Match{matches.length > 1 ? 'es' : ''}
                </h3>
                
                <div className="space-y-3">
                  {matches.map((match, idx) => (
                    <div
                      key={match.patient_id}
                      className={`
                        border-2 rounded-lg p-4 cursor-pointer transition-all
                        ${selectedMatch?.patient_id === match.patient_id
                          ? 'border-teal-500 bg-teal-50'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }
                      `}
                      onClick={() => setSelectedMatch(match)}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                            <User className="w-5 h-5 text-teal-600" />
                          </div>
                          <div>
                            <h4 className="font-semibold text-gray-900">
                              {match.first_name} {match.last_name}
                            </h4>
                            <p className="text-sm text-gray-500">Patient ID: {match.patient_id.substring(0, 8)}...</p>
                          </div>
                        </div>
                        <Badge className={`${getConfidenceColor(match.confidence_score)} border`}>
                          {getConfidenceLabel(match.confidence_score)} ({Math.round(match.confidence_score * 100)}%)
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="flex items-center gap-2">
                          <CreditCard className="w-4 h-4 text-gray-400" />
                          <span className="text-gray-600">ID:</span>
                          <span className="font-medium">{match.id_number}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-gray-400" />
                          <span className="text-gray-600">DOB:</span>
                          <span className="font-medium">{match.dob}</span>
                        </div>
                        {match.contact_number && (
                          <div className="flex items-center gap-2">
                            <Phone className="w-4 h-4 text-gray-400" />
                            <span className="text-gray-600">Phone:</span>
                            <span className="font-medium">{match.contact_number}</span>
                          </div>
                        )}
                        {match.last_visit && (
                          <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4 text-gray-400" />
                            <span className="text-gray-600">Last Visit:</span>
                            <span className="font-medium">{match.last_visit}</span>
                          </div>
                        )}
                      </div>

                      <div className="mt-2">
                        <span className="text-xs text-gray-500">
                          Match Method: {match.match_method.replace('_', ' ').toUpperCase()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <AlertTriangle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-700 mb-2">No Matching Patients Found</h3>
              <p className="text-gray-600 mb-6">
                We couldn't find any existing patients matching the extracted data.
                Would you like to create a new patient record?
              </p>
              
              {/* Show extracted data */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6 max-w-md mx-auto">
                <div className="text-left space-y-2 text-sm">
                  <div>
                    <span className="text-gray-600">Name:</span>
                    <span className="ml-2 font-medium">
                      {extractedData.first_name || extractedData.first_names || ''} {extractedData.last_name || extractedData.surname || ''}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">ID Number:</span>
                    <span className="ml-2 font-medium">{extractedData.id_number || 'Not available'}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">DOB:</span>
                    <span className="ml-2 font-medium">{extractedData.dob || 'Not available'}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="border-t bg-gray-50 px-6 py-4 flex items-center justify-between">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>

          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => onCreateNew(extractedData)}
              disabled={isLoading}
              className="gap-2"
            >
              <User className="w-4 h-4" />
              Create New Patient
            </Button>

            {matches && matches.length > 0 && (
              <Button
                onClick={() => onConfirmMatch(selectedMatch || matches[0])}
                disabled={isLoading || !selectedMatch}
                className="gap-2 bg-teal-600 hover:bg-teal-700"
              >
                {isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Processing...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Confirm Match
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PatientMatchDialog;
