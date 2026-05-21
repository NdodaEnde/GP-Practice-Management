import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Upload, Eye, Trash2, Download, Filter,
  Search, CheckCircle, Clock, AlertCircle, FileCheck,
  RefreshCw, Loader2, RotateCcw, Activity, Play, PlayCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';

const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds when documents are processing

const DigitisedDocuments = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [watcherStatus, setWatcherStatus] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const refreshTimer = useRef(null);
  const [filters, setFilters] = useState({
    status: '',
    search: '',
    dateFrom: '',
    dateTo: ''
  });

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  const fetchDocuments = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      if (filters.search) params.append('search', filters.search);
      if (filters.dateFrom) params.append('date_from', filters.dateFrom);
      if (filters.dateTo) params.append('date_to', filters.dateTo);

      const response = await axios.get(`${backendUrl}/api/gp/documents?${params.toString()}`);
      setDocuments(response.data.documents || []);
    } catch (error) {
      if (!silent) {
        console.error('Error fetching documents:', error);
        toast({
          title: 'Error',
          description: 'Failed to load documents',
          variant: 'destructive'
        });
      }
    } finally {
      setLoading(false);
    }
  }, [filters, backendUrl]);

  const fetchWatcherStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${backendUrl}/api/gp/watcher/status`);
      setWatcherStatus(response.data);
    } catch (error) {
      // Watcher status is non-critical, silently fail
    }
  }, [backendUrl]);

  // Initial load
  useEffect(() => {
    fetchDocuments();
    fetchWatcherStatus();
  }, [filters]);

  // Auto-refresh when documents are being processed
  useEffect(() => {
    if (refreshTimer.current) {
      clearInterval(refreshTimer.current);
      refreshTimer.current = null;
    }

    const hasProcessing = documents.some(doc =>
      ['queued_for_processing', 'parsing', 'extracting'].includes(doc.status)
    );

    if (autoRefresh && hasProcessing) {
      refreshTimer.current = setInterval(() => {
        fetchDocuments(true);
        fetchWatcherStatus();
      }, AUTO_REFRESH_INTERVAL);
    }

    return () => {
      if (refreshTimer.current) {
        clearInterval(refreshTimer.current);
      }
    };
  }, [documents, autoRefresh, fetchDocuments, fetchWatcherStatus]);

  const handleQueueProcessing = async (docId) => {
    try {
      await axios.post(`${backendUrl}/api/gp/documents/${docId}/queue-processing`);
      toast({
        title: 'Processing Queued',
        description: 'Document queued for parsing and extraction'
      });
      fetchDocuments();
    } catch (error) {
      console.error('Error queuing document:', error);
      toast({
        title: 'Error',
        description: 'Failed to queue document for processing',
        variant: 'destructive'
      });
    }
  };

  const handleQueueAllUploaded = async () => {
    const uploadedCount = documents.filter(d => d.status === 'uploaded').length;
    if (uploadedCount === 0) {
      toast({ title: 'No documents', description: 'No uploaded documents to process' });
      return;
    }
    if (!window.confirm(`This will process ${uploadedCount} document(s) and consume extraction credits. Continue?`)) return;

    try {
      const response = await axios.post(`${backendUrl}/api/gp/documents/queue-all-uploaded`);
      toast({
        title: 'Processing Queued',
        description: response.data.message
      });
      fetchDocuments();
    } catch (error) {
      toast({ title: 'Error', description: 'Failed to queue documents', variant: 'destructive' });
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      uploaded: { color: 'bg-blue-100 text-blue-700', icon: Clock, label: 'Awaiting Processing' },
      queued_for_processing: { color: 'bg-amber-100 text-amber-700', icon: Clock, label: 'Queued' },
      parsing: { color: 'bg-yellow-100 text-yellow-700', icon: Loader2, label: 'Parsing...', animate: true },
      parsed: { color: 'bg-green-100 text-green-700', icon: CheckCircle, label: 'Parsed' },
      extracting: { color: 'bg-purple-100 text-purple-700', icon: Loader2, label: 'Extracting...', animate: true },
      extracted: { color: 'bg-teal-100 text-teal-700', icon: FileCheck, label: 'Ready for Review' },
      validated: { color: 'bg-indigo-100 text-indigo-700', icon: CheckCircle, label: 'Validated' },
      approved: { color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle, label: 'Approved' },
      error: { color: 'bg-red-100 text-red-700', icon: AlertCircle, label: 'Error' }
    };

    const config = statusConfig[status] || statusConfig.uploaded;
    const Icon = config.icon;

    return (
      <Badge className={`${config.color} flex items-center gap-1`}>
        <Icon className={`w-3 h-3 ${config.animate ? 'animate-spin' : ''}`} />
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

  const handleReprocess = async (docId) => {
    try {
      await axios.post(`${backendUrl}/api/gp/documents/${docId}/reprocess`);
      toast({
        title: 'Reprocessing',
        description: 'Document queued for reprocessing'
      });
      fetchDocuments();
    } catch (error) {
      console.error('Error reprocessing document:', error);
      toast({
        title: 'Error',
        description: 'Failed to reprocess document',
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

  const hasProcessing = documents.some(doc =>
    ['uploaded', 'parsing', 'extracting'].includes(doc.status)
  );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-3">
            <FileText className="w-8 h-8 text-teal-600" />
            Digitised Documents
          </h1>
          <p className="text-slate-600 mt-1">
            Documents are auto-detected from storage. Click "Process" to parse and extract.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {documents.some(d => d.status === 'uploaded') && (
            <Button
              onClick={handleQueueAllUploaded}
              variant="outline"
              size="sm"
              className="border-amber-600 text-amber-600 hover:bg-amber-50"
            >
              <PlayCircle className="w-4 h-4 mr-1" />
              Process All ({documents.filter(d => d.status === 'uploaded').length})
            </Button>
          )}
          <Button
            onClick={() => { fetchDocuments(); fetchWatcherStatus(); }}
            variant="outline"
            size="sm"
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            Refresh
          </Button>
          <Button
            onClick={() => navigate('/gp/digitization')}
            className="bg-teal-600 hover:bg-teal-700 text-white"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload New
          </Button>
        </div>
      </div>

      {/* Processing Queue Status */}
      {watcherStatus && (
        <Card className="mb-6 border-slate-200">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Activity className={`w-4 h-4 ${watcherStatus.watcher_running ? 'text-green-500' : 'text-red-500'}`} />
                  <span className="text-sm font-medium text-slate-700">
                    Auto-processing {watcherStatus.watcher_running ? 'active' : 'inactive'}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-sm text-slate-600">
                  {watcherStatus.pending_processing > 0 && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-blue-500" />
                      {watcherStatus.pending_processing} queued
                    </span>
                  )}
                  {watcherStatus.currently_processing > 0 && (
                    <span className="flex items-center gap-1">
                      <Loader2 className="w-3.5 h-3.5 text-yellow-500 animate-spin" />
                      {watcherStatus.currently_processing} processing
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                    {watcherStatus.completed} complete
                  </span>
                  {watcherStatus.errors > 0 && (
                    <span className="flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                      {watcherStatus.errors} errors
                    </span>
                  )}
                </div>
              </div>
              {hasProcessing && (
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  Auto-refreshing
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

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
                <option value="uploaded">Awaiting Processing</option>
                <option value="queued_for_processing">Queued</option>
                <option value="parsing">Parsing</option>
                <option value="parsed">Parsed</option>
                <option value="extracted">Ready for Review</option>
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
              <p className="text-sm mt-2">
                Drop files into Supabase Storage or upload here — they'll be processed automatically
              </p>
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
                        {doc.source === 'storage_watcher' && (
                          <Badge className="bg-slate-100 text-slate-600 text-xs">Auto-detected</Badge>
                        )}
                      </div>
                      <div className="text-sm text-slate-600 space-y-1">
                        <div className="flex items-center gap-4">
                          <span>
                            {new Date(doc.upload_date || doc.created_at).toLocaleString()}
                          </span>
                          {doc.patient_name && (
                            <span>
                              Patient: <span className="font-medium">{doc.patient_name}</span>
                            </span>
                          )}
                          {doc.file_size && (
                            <span>
                              {(doc.file_size / 1024).toFixed(1)} KB
                            </span>
                          )}
                          {doc.pages_count && (
                            <span>{doc.pages_count} pages</span>
                          )}
                        </div>
                        {doc.error_message && (
                          <div className="text-red-600 text-xs mt-1">
                            Error: {doc.error_message}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {doc.status === 'uploaded' && (
                        <Button
                          size="sm"
                          onClick={() => handleQueueProcessing(doc.id)}
                          className="bg-teal-600 hover:bg-teal-700 text-white"
                        >
                          <Play className="w-4 h-4 mr-1" />
                          Process
                        </Button>
                      )}
                      {['extracted', 'validated', 'approved', 'parsed'].includes(doc.status) && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleViewDocument(doc.id)}
                          className="border-teal-600 text-teal-600 hover:bg-teal-50"
                        >
                          <Eye className="w-4 h-4 mr-1" />
                          Review
                        </Button>
                      )}
                      {doc.status === 'error' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleReprocess(doc.id)}
                          className="border-orange-600 text-orange-600 hover:bg-orange-50"
                        >
                          <RotateCcw className="w-4 h-4 mr-1" />
                          Retry
                        </Button>
                      )}
                      {['parsing', 'extracting', 'queued_for_processing'].includes(doc.status) && (
                        <Button size="sm" variant="outline" disabled>
                          <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                          Processing
                        </Button>
                      )}
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
