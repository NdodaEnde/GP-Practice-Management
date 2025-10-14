import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';
import {
  ArrowLeft,
  FileText,
  Calendar,
  Eye,
  Download,
  Search,
  Filter,
  CheckCircle,
  Clock,
  Link as LinkIcon
} from 'lucide-react';

const DocumentArchive = () => {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [documents, setDocuments] = useState([]);
  const [filteredDocuments, setFilteredDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [showViewer, setShowViewer] = useState(false);

  useEffect(() => {
    if (patientId) {
      fetchDocuments();
    }
  }, [patientId]);

  useEffect(() => {
    filterDocuments();
  }, [searchQuery, statusFilter, documents]);

  const fetchDocuments = async () => {
    try {
      setIsLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const response = await axios.get(
        `${backendUrl}/api/documents/patient/${patientId}`
      );

      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast({
        title: "Error",
        description: "Failed to load documents",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const filterDocuments = () => {
    let filtered = documents;

    // Status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(doc => doc.status === statusFilter);
    }

    // Search filter
    if (searchQuery) {
      filtered = filtered.filter(doc =>
        doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredDocuments(filtered);
  };

  const handleViewDocument = async (document) => {
    try {
      // Log access
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      await axios.post(
        `${backendUrl}/api/documents/${document.document_id}/log-access`,
        {
          document_id: document.document_id,
          access_type: 'view',
          user_id: 'current_user',
          ip_address: null
        }
      );

      setSelectedDocument(document);
      setShowViewer(true);
    } catch (error) {
      console.error('Error logging document access:', error);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'linked':
        return 'bg-green-100 text-green-800';
      case 'validated':
        return 'bg-blue-100 text-blue-800';
      case 'uploaded':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'linked':
        return <LinkIcon className="w-4 h-4" />;
      case 'validated':
        return <CheckCircle className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-ZA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <Button
            variant="ghost"
            onClick={() => navigate(-1)}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Patient
          </Button>
          
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Document Archive</h1>
          <p className="text-gray-600">View and manage patient documents (40-year retention)</p>
        </div>

        {/* Search and Filter */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <Input
                  placeholder="Search documents by filename..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              
              <div className="flex items-center gap-2">
                <Filter className="w-5 h-5 text-gray-400" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  <option value="all">All Status</option>
                  <option value="linked">Linked to EHR</option>
                  <option value="validated">Validated</option>
                  <option value="uploaded">Uploaded</option>
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Documents List */}
        {isLoading ? (
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
              </div>
            </CardContent>
          </Card>
        ) : filteredDocuments.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-700 mb-2">No Documents Found</h3>
                <p className="text-gray-600">
                  {searchQuery || statusFilter !== 'all'
                    ? 'Try adjusting your filters'
                    : 'No documents have been uploaded for this patient yet'}
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {filteredDocuments.map((doc) => (
              <Card key={doc.document_id} className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4 flex-1">
                      <div className="w-12 h-12 bg-teal-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <FileText className="w-6 h-6 text-teal-600" />
                      </div>
                      
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-gray-900">{doc.filename}</h3>
                          <Badge className={`${getStatusColor(doc.status)} flex items-center gap-1`}>
                            {getStatusIcon(doc.status)}
                            {doc.status}
                          </Badge>
                        </div>
                        
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <div className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            Uploaded: {formatDate(doc.upload_date)}
                          </div>
                          
                          {doc.validated_at && (
                            <div className="flex items-center gap-1">
                              <CheckCircle className="w-4 h-4" />
                              Validated: {formatDate(doc.validated_at)}
                            </div>
                          )}
                          
                          {doc.linked_at && (
                            <div className="flex items-center gap-1">
                              <LinkIcon className="w-4 h-4" />
                              Linked: {formatDate(doc.linked_at)}
                            </div>
                          )}
                        </div>

                        {doc.encounter_id && (
                          <div className="mt-2">
                            <span className="text-xs text-gray-500">
                              Encounter: {doc.encounter_id.substring(0, 8)}...
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleViewDocument(doc)}
                        className="gap-2"
                      >
                        <Eye className="w-4 h-4" />
                        View
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
                          window.open(`${backendUrl}/api/gp/document/${doc.document_id}/view`, '_blank');
                        }}
                        className="gap-2"
                      >
                        <Download className="w-4 h-4" />
                        PDF
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Summary */}
        <Card className="mt-6 bg-gray-50">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between text-sm text-gray-600">
              <span>Total Documents: <strong>{documents.length}</strong></span>
              <span>Showing: <strong>{filteredDocuments.length}</strong></span>
              <span className="text-xs">
                Documents retained for 40 years as per South African medical regulations
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Document Viewer Modal - TODO: Implement detailed viewer */}
      {showViewer && selectedDocument && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-xl font-bold">Document Viewer</h2>
              <Button variant="ghost" onClick={() => setShowViewer(false)}>
                Close
              </Button>
            </div>
            <div className="p-6">
              <p className="text-gray-600">
                Detailed document viewer with PDF, extracted data, and audit trail coming next...
              </p>
              <p className="text-sm text-gray-500 mt-2">
                Document ID: {selectedDocument.document_id}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentArchive;
