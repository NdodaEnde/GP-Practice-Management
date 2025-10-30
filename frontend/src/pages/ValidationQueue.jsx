import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription 
} from '../components/ui/card';
import { Button } from '../components/ui/button';
import { 
  CheckCircle, 
  XCircle,
  Eye,
  Clock,
  TrendingUp,
  AlertCircle,
  FileText,
  User
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const DEMO_WORKSPACE = 'demo-gp-workspace-001';

const ValidationQueue = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadQueue();
    loadStats();
  }, []);

  const loadQueue = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `${BACKEND_URL}/api/validation/queue?workspace_id=${DEMO_WORKSPACE}&limit=50`
      );
      setQueue(response.data.extractions || []);
    } catch (error) {
      console.error('Failed to load validation queue:', error);
      setQueue([]); // Set to empty array on error
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to load validation queue"
      });
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/validation/stats?workspace_id=${DEMO_WORKSPACE}`
      );
      setStats(response.data.stats);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const handleApprove = async (extractionId) => {
    try {
      await axios.post(`${BACKEND_URL}/api/validation/approve`, {
        extraction_id: extractionId,
        validated_by: 'current-user',  // TODO: Get from auth context
        notes: 'Approved from queue'
      });

      toast({
        title: "Extraction Approved ✅",
        description: "Data has been validated and committed"
      });

      // Reload queue
      loadQueue();
      loadStats();
    } catch (error) {
      console.error('Failed to approve:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to approve extraction"
      });
    }
  };

  const handleReject = async (extractionId) => {
    const reason = prompt('Rejection reason:');
    if (!reason) return;

    try {
      await axios.post(`${BACKEND_URL}/api/validation/reject`, {
        extraction_id: extractionId,
        rejection_reason: reason,
        validated_by: 'current-user'  // TODO: Get from auth context
      });

      toast({
        title: "Extraction Rejected",
        description: "Marked as rejected"
      });

      // Reload queue
      loadQueue();
      loadStats();
    } catch (error) {
      console.error('Failed to reject:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to reject extraction"
      });
    }
  };

  const handleReview = (extraction) => {
    // Navigate to the validation review page
    navigate(`/validation/${extraction.id}`);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const getConfidenceColor = (score) => {
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Validation Queue</h1>
        <p className="text-gray-600">
          Review extracted data before committing to structured tables
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Pending</p>
                  <p className="text-3xl font-bold text-yellow-600">
                    {stats.pending_validation}
                  </p>
                </div>
                <Clock className="w-8 h-8 text-yellow-500 opacity-50" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Approved</p>
                  <p className="text-3xl font-bold text-green-600">
                    {stats.approved}
                  </p>
                </div>
                <CheckCircle className="w-8 h-8 text-green-500 opacity-50" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Rejected</p>
                  <p className="text-3xl font-bold text-red-600">
                    {stats.rejected}
                  </p>
                </div>
                <XCircle className="w-8 h-8 text-red-500 opacity-50" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Approval Rate</p>
                  <p className="text-3xl font-bold text-blue-600">
                    {(stats.approval_rate * 100).toFixed(0)}%
                  </p>
                </div>
                <TrendingUp className="w-8 h-8 text-blue-500 opacity-50" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Validation Queue */}
      <Card>
        <CardHeader>
          <CardTitle>Pending Validations ({queue?.length || 0})</CardTitle>
          <CardDescription>
            Documents awaiting human review
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading...</div>
          ) : !queue || queue.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <CheckCircle className="w-16 h-16 mx-auto mb-4 opacity-30" />
              <p className="text-lg font-medium">No pending validations</p>
              <p className="text-sm mt-2">All extractions have been reviewed</p>
            </div>
          ) : (
            <div className="space-y-3">
              {queue.map((extraction) => (
                <div
                  key={extraction.id}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <FileText className="w-5 h-5 text-blue-500" />
                        <div>
                          <p className="font-medium">
                            Document ID: {extraction.document_id?.substring(0, 8)}...
                          </p>
                          <p className="text-sm text-gray-500">
                            Extracted: {formatDate(extraction.extraction_datetime)}
                          </p>
                        </div>
                      </div>

                      {/* Quick Stats */}
                      <div className="flex gap-4 text-sm text-gray-600 mt-3">
                        <div>
                          <span className="font-medium">Fields Extracted:</span> {extraction.fields_extracted || 0}
                        </div>
                        <div>
                          <span className="font-medium">Records Created:</span> {extraction.records_created || 0}
                        </div>
                        {extraction.processing_time_ms && (
                          <div>
                            <span className="font-medium">Processing Time:</span> {extraction.processing_time_ms}ms
                          </div>
                        )}
                      </div>

                      {/* Confidence Scores */}
                      {extraction.confidence_scores && Object.keys(extraction.confidence_scores).length > 0 && (
                        <div className="mt-3">
                          <p className="text-sm font-medium mb-2">Confidence Scores:</p>
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(extraction.confidence_scores).map(([section, score]) => (
                              <span
                                key={section}
                                className={`text-xs px-2 py-1 rounded ${
                                  score >= 0.8 ? 'bg-green-100 text-green-700' :
                                  score >= 0.6 ? 'bg-yellow-100 text-yellow-700' :
                                  'bg-red-100 text-red-700'
                                }`}
                              >
                                {section}: {(score * 100).toFixed(0)}%
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Population Errors */}
                      {extraction.population_errors && extraction.population_errors.length > 0 && (
                        <div className="mt-3">
                          <div className="flex items-center gap-2 text-sm text-orange-700">
                            <AlertCircle className="w-4 h-4" />
                            <span>{extraction.population_errors.length} warning(s) during processing</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 ml-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleReview(extraction)}
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        Review
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleApprove(extraction.id)}
                        className="text-green-600 hover:text-green-700"
                      >
                        <CheckCircle className="w-4 h-4 mr-1" />
                        Approve
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleReject(extraction.id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <XCircle className="w-4 h-4 mr-1" />
                        Reject
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Review Modal - TODO: Create detailed review component */}
      {showReviewModal && selectedExtraction && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <CardTitle>Extraction Review</CardTitle>
              <Button
                variant="ghost"
                onClick={() => setShowReviewModal(false)}
                className="absolute top-4 right-4"
              >
                ✕
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Document Info */}
                {selectedExtraction.document && (
                  <div>
                    <h3 className="font-medium mb-2">Document</h3>
                    <p className="text-sm text-gray-600">
                      Filename: {selectedExtraction.document.filename}
                    </p>
                  </div>
                )}

                {/* Template Info */}
                {selectedExtraction.template && (
                  <div>
                    <h3 className="font-medium mb-2">Template Used</h3>
                    <p className="text-sm text-gray-600">
                      {selectedExtraction.template.template_name}
                    </p>
                  </div>
                )}

                {/* Extracted Data */}
                <div>
                  <h3 className="font-medium mb-2">Extracted Data</h3>
                  <pre className="bg-gray-50 p-4 rounded text-xs overflow-x-auto">
                    {JSON.stringify(selectedExtraction.extraction.structured_extraction, null, 2)}
                  </pre>
                </div>

                {/* Tables Populated */}
                {selectedExtraction.extraction.tables_populated && (
                  <div>
                    <h3 className="font-medium mb-2">Tables Populated</h3>
                    <pre className="bg-gray-50 p-4 rounded text-xs">
                      {JSON.stringify(selectedExtraction.extraction.tables_populated, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-4">
                  <Button
                    onClick={() => {
                      handleApprove(selectedExtraction.extraction.id);
                      setShowReviewModal(false);
                    }}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Approve
                  </Button>
                  <Button
                    onClick={() => {
                      handleReject(selectedExtraction.extraction.id);
                      setShowReviewModal(false);
                    }}
                    variant="destructive"
                  >
                    <XCircle className="w-4 h-4 mr-2" />
                    Reject
                  </Button>
                  <Button
                    onClick={() => setShowReviewModal(false)}
                    variant="outline"
                  >
                    Close
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ValidationQueue;
