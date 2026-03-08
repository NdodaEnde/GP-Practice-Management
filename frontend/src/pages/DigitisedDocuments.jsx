import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  FileText, Upload, Eye, Trash2, Download, Filter, 
  Search, CheckCircle, Clock, AlertCircle, FileCheck 
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';

const DigitisedDocuments = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [filters, setFilters] = useState({
    status: '',
    search: '',
    dateFrom: '',
    dateTo: ''
  });

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  useEffect(() => {
    fetchDocuments();
  }, [filters]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      if (filters.search) params.append('search', filters.search);
      if (filters.dateFrom) params.append('date_from', filters.dateFrom);
      if (filters.dateTo) params.append('date_to', filters.dateTo);

      const response = await axios.get(`${backendUrl}/api/gp/documents?${params.toString()}`);
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast({
        title: 'Error',
        description: 'Failed to load documents',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      uploaded: { color: 'bg-blue-100 text-blue-700', icon: Clock, label: 'Uploaded' },
      parsing: { color: 'bg-yellow-100 text-yellow-700', icon: Clock, label: 'Parsing...' },
      parsed: { color: 'bg-green-100 text-green-700', icon: CheckCircle, label: 'Parsed' },
      extracting: { color: 'bg-purple-100 text-purple-700', icon: Clock, label: 'Extracting...' },
      extracted: { color: 'bg-teal-100 text-teal-700', icon: FileCheck, label: 'Extracted' },
      validated: { color: 'bg-indigo-100 text-indigo-700', icon: CheckCircle, label: 'Validated' },
      approved: { color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle, label: 'Approved' },
      error: { color: 'bg-red-100 text-red-700', icon: AlertCircle, label: 'Error' }
    };

    const config = statusConfig[status] || statusConfig.uploaded;
    const Icon = config.icon;

    return (
      <Badge className={`${config.color} flex items-center gap-1`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </Badge>
    );
  };

  const handleViewDocument = (docId) => {
    navigate(`/gp/documents/${docId}/validate`);
  };

  const handleDeleteDocument = async (docId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) return;

    try {
      await axios.delete(`${backendUrl}/api/gp/documents/${docId}`);
      toast({
        title: 'Success',
        description: 'Document deleted successfully'
      });
      fetchDocuments();
    } catch (error) {
      console.error('Error deleting document:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete document',
        variant: 'destructive'
      });
    }
  };

  const handleBulkExtract = async () => {
    if (selectedDocs.length === 0) {
      toast({
        title: 'No Selection',
        description: 'Please select documents to extract',
        variant: 'destructive'
      });
      return;
    }

    try {
      await axios.post(`${backendUrl}/api/gp/documents/bulk-extract`, selectedDocs);
      toast({
        title: 'Success',
        description: `Extraction queued for ${selectedDocs.length} document(s)`
      });
      setSelectedDocs([]);
      fetchDocuments();
    } catch (error) {
      console.error('Error in bulk extraction:', error);
      toast({
        title: 'Error',
        description: 'Failed to queue extraction',
        variant: 'destructive'
      });
    }
  };

  const toggleSelection = (docId) => {
    setSelectedDocs(prev => 
      prev.includes(docId) 
        ? prev.filter(id => id !== docId)
        : [...prev, docId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedDocs.length === documents.length) {
      setSelectedDocs([]);
    } else {
      setSelectedDocs(documents.map(doc => doc.id));
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-3">
            <FileText className="w-8 h-8 text-teal-600" />
            Digitised Documents
          </h1>
          <p className="text-slate-600 mt-1">Manage and validate scanned patient records</p>
        </div>
        <Button 
          onClick={() => navigate('/gp/digitization')}
          className="bg-teal-600 hover:bg-teal-700 text-white"
        >
          <Upload className="w-4 h-4 mr-2" />
          Upload New
        </Button>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  placeholder="Search by filename..."
                  value={filters.search}
                  onChange={(e) => setFilters({...filters, search: e.target.value})}
                  className="pl-10"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Status</label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({...filters, status: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="">All Statuses</option>
                <option value="uploaded">Uploaded</option>
                <option value="parsed">Parsed</option>
                <option value="extracted">Extracted</option>
                <option value="validated">Validated</option>
                <option value="approved">Approved</option>
                <option value="error">Error</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Date From</label>
              <Input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => setFilters({...filters, dateFrom: e.target.value})}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Date To</label>
              <Input
                type="date"
                value={filters.dateTo}
                onChange={(e) => setFilters({...filters, dateTo: e.target.value})}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {selectedDocs.length > 0 && (
        <Card className="mb-4 bg-teal-50 border-teal-200">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <span className="text-slate-700">
                <strong>{selectedDocs.length}</strong> document(s) selected
              </span>
              <div className="flex gap-2">
                <Button 
                  onClick={handleBulkExtract}
                  variant="outline"
                  className="border-teal-600 text-teal-600 hover:bg-teal-50"
                >
                  Extract Selected
                </Button>
                <Button 
                  onClick={() => setSelectedDocs([])}
                  variant="outline"
                >
                  Clear Selection
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Documents List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Documents ({documents.length})</span>
            {documents.length > 0 && (
              <label className="flex items-center gap-2 text-sm font-normal cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedDocs.length === documents.length}
                  onChange={toggleSelectAll}
                  className="w-4 h-4"
                />
                Select All
              </label>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <FileText className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-lg font-medium">No documents found</p>
              <p className="text-sm mt-2">Upload documents to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className={`p-4 border rounded-lg hover:bg-slate-50 transition-colors ${
                    selectedDocs.includes(doc.id) ? 'bg-teal-50 border-teal-300' : 'border-slate-200'
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <input
                      type="checkbox"
                      checked={selectedDocs.includes(doc.id)}
                      onChange={() => toggleSelection(doc.id)}
                      className="w-5 h-5"
                    />
                    <FileText className="w-8 h-8 text-teal-600 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-semibold text-slate-800">{doc.filename}</h3>
                        {getStatusBadge(doc.status)}
                      </div>
                      <div className="text-sm text-slate-600 space-y-1">
                        <div>
                          Uploaded: {new Date(doc.upload_date).toLocaleString()}
                        </div>
                        {doc.patient_name && (
                          <div>
                            Patient: <span className="font-medium">{doc.patient_name}</span>
                          </div>
                        )}
                        {doc.file_size && (
                          <div>
                            Size: {(doc.file_size / 1024).toFixed(2)} KB
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleViewDocument(doc.id)}
                        className="border-teal-600 text-teal-600 hover:bg-teal-50"
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        View
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="border-red-600 text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default DigitisedDocuments;
