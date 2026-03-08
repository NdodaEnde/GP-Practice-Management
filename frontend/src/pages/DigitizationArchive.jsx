import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';
import {
  FileText,
  Calendar,
  Eye,
  Download,
  Search,
  Filter,
  CheckCircle,
  Clock,
  AlertCircle,
  User,
  RefreshCw,
  FileUp,
  Upload
} from 'lucide-react';

const DigitizationArchive = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [documents, setDocuments] = useState([]);
  const [filteredDocuments, setFilteredDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [patientFilter, setPatientFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(20);
  
  // Statistics
  const [stats, setStats] = useState({
    total: 0,
    parsed: 0,
    extracted: 0,
    approved: 0,
    pending_validation: 0
  });

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    filterDocuments();
  }, [searchQuery, statusFilter, patientFilter, dateFrom, dateTo, documents]);

  useEffect(() => {
    calculateStats();
  }, [filteredDocuments]);

  const fetchDocuments = async () => {
    try {
      setIsLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const response = await axios.get(`${backendUrl}/api/gp/documents`, {
        params: {
          limit: 200 // Get more documents for better filtering
        }
      });

      setDocuments(response.data.documents || []);
      
      toast({
        title: "Documents Loaded",
        description: `Found ${response.data.total} documents`,
      });
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
    if (statusFilter) {
      filtered = filtered.filter(doc => doc.status === statusFilter);
    }

    // Patient filter
    if (patientFilter) {
      filtered = filtered.filter(doc => 
        doc.patient_name?.toLowerCase().includes(patientFilter.toLowerCase()) ||
        doc.patient_id?.includes(patientFilter)
      );
    }

    // Search filter (filename)
    if (searchQuery) {
      filtered = filtered.filter(doc =>
        doc.filename?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Date range filter
    if (dateFrom) {
      filtered = filtered.filter(doc => 
        new Date(doc.upload_date) >= new Date(dateFrom)
      );
    }
    if (dateTo) {
      filtered = filtered.filter(doc => 
        new Date(doc.upload_date) <= new Date(dateTo)
      );
    }

    setFilteredDocuments(filtered);
  };

  const calculateStats = () => {
    const newStats = {
      total: filteredDocuments.length,
      parsed: filteredDocuments.filter(d => d.status === 'parsed').length,
      extracted: filteredDocuments.filter(d => d.status === 'extracted').length,
      approved: filteredDocuments.filter(d => d.status === 'approved').length,
      pending_validation: filteredDocuments.filter(d => d.status === 'pending_validation').length,
    };
    setStats(newStats);
  };

  const handleViewDocument = (document) => {
    // Navigate to validation review page
    navigate(`/document-validation/${document.id}`);
  };

  const handleExportData = async (document, format = 'json') => {
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      // Get parsed document data
      const response = await axios.get(
        `${backendUrl}/api/gp/parsed-document/${document.parsed_doc_id}`
      );

      const data = response.data;
      
      // Create export based on format
      let exportData;
      let filename;
      let mimeType;

      if (format === 'json') {
        exportData = JSON.stringify(data, null, 2);
        filename = `${document.filename}_export.json`;
        mimeType = 'application/json';
      } else if (format === 'csv') {
        // Convert demographics to CSV
        const demographics = data.structured_extraction?.demographics || data.extracted_data?.demographics || {};
        const csvRows = [];
        csvRows.push('Field,Value');
        Object.entries(demographics).forEach(([key, value]) => {
          csvRows.push(`${key},"${value || ''}"`);
        });
        exportData = csvRows.join('\n');
        filename = `${document.filename}_demographics.csv`;
        mimeType = 'text/csv';
      }

      // Create download
      const blob = new Blob([exportData], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);

      toast({
        title: "Export Successful",
        description: `Document exported as ${filename}`,
      });
    } catch (error) {
      console.error('Error exporting document:', error);
      toast({
        title: "Export Failed",
        description: "Could not export document data",
        variant: "destructive"
      });
    }
  };

  const handleBulkExport = async () => {
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      // Get all parsed documents
      const exportData = [];
      
      for (const doc of filteredDocuments) {
        if (doc.parsed_doc_id) {
          try {
            const response = await axios.get(
              `${backendUrl}/api/gp/parsed-document/${doc.parsed_doc_id}`
            );
            exportData.push({
              document_id: doc.id,
              filename: doc.filename,
              upload_date: doc.upload_date,
              status: doc.status,
              patient_name: doc.patient_name,
              data: response.data
            });
          } catch (err) {
            console.error(`Error fetching document ${doc.id}:`, err);
          }
        }
      }

      // Create JSON export
      const jsonData = JSON.stringify(exportData, null, 2);
      const blob = new Blob([jsonData], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `bulk_export_${new Date().toISOString().split('T')[0]}.json`;
      link.click();
      URL.revokeObjectURL(url);

      toast({
        title: "Bulk Export Complete",
        description: `Exported ${exportData.length} documents`,
      });
    } catch (error) {
      console.error('Error in bulk export:', error);
      toast({
        title: "Bulk Export Failed",
        description: "Could not complete bulk export",
        variant: "destructive"
      });
    }
  };

  const getStatusColor = (status) => {
    const statusColors = {
      'uploaded': 'bg-gray-100 text-gray-800',
      'parsing': 'bg-blue-100 text-blue-800',
      'parsed': 'bg-yellow-100 text-yellow-800',
      'extracting': 'bg-orange-100 text-orange-800',
      'extracted': 'bg-purple-100 text-purple-800',
      'pending_validation': 'bg-amber-100 text-amber-800',
      'approved': 'bg-green-100 text-green-800',
      'rejected': 'bg-red-100 text-red-800',
      'error': 'bg-red-200 text-red-900'
    };
    return statusColors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (status) => {
    const icons = {
      'uploaded': <FileUp className="w-3 h-3" />,
      'parsing': <RefreshCw className="w-3 h-3 animate-spin" />,
      'parsed': <Clock className="w-3 h-3" />,
      'extracting': <RefreshCw className="w-3 h-3 animate-spin" />,
      'extracted': <FileText className="w-3 h-3" />,
      'pending_validation': <AlertCircle className="w-3 h-3" />,
      'approved': <CheckCircle className="w-3 h-3" />,
      'rejected': <AlertCircle className="w-3 h-3" />,
      'error': <AlertCircle className="w-3 h-3" />
    };
    return icons[status] || <FileText className="w-3 h-3" />;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-ZA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Pagination
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentDocuments = filteredDocuments.slice(indexOfFirstItem, indexOfLastItem);
  const totalPages = Math.ceil(filteredDocuments.length / itemsPerPage);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Document Archive</h1>
              <p className="text-gray-600">Comprehensive digitization document management and export</p>
            </div>
            
            <div className="flex gap-2">
              <Button
                onClick={fetchDocuments}
                variant="outline"
                className="gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
              <Button
                onClick={() => navigate('/document-upload')}
                className="gap-2 bg-teal-600 hover:bg-teal-700"
              >
                <Upload className="w-4 h-4" />
                Upload New
              </Button>
            </div>
          </div>

          {/* Statistics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
                  <p className="text-sm text-gray-600">Total Documents</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-yellow-600">{stats.parsed}</p>
                  <p className="text-sm text-gray-600">Parsed</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-purple-600">{stats.extracted}</p>
                  <p className="text-sm text-gray-600">Extracted</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-600">{stats.pending_validation}</p>
                  <p className="text-sm text-gray-600">Pending</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">{stats.approved}</p>
                  <p className="text-sm text-gray-600">Approved</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Search and Filters */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Search & Filter</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Search by filename */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Search Filename
                </label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <Input
                    placeholder="Search documents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>

              {/* Status filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Status
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  <option value="">All Status</option>
                  <option value="parsed">Parsed</option>
                  <option value="extracted">Extracted</option>
                  <option value="pending_validation">Pending Validation</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="error">Error</option>
                </select>
              </div>

              {/* Patient filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Patient
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <Input
                    placeholder="Patient name or ID..."
                    value={patientFilter}
                    onChange={(e) => setPatientFilter(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>

              {/* Date from */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  From Date
                </label>
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </div>

              {/* Date to */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  To Date
                </label>
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </div>

              {/* Clear filters */}
              <div className="flex items-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setSearchQuery('');
                    setStatusFilter('');
                    setPatientFilter('');
                    setDateFrom('');
                    setDateTo('');
                  }}
                  className="w-full"
                >
                  Clear Filters
                </Button>
              </div>
            </div>

            {/* Bulk actions */}
            {filteredDocuments.length > 0 && (
              <div className="mt-4 pt-4 border-t flex justify-between items-center">
                <p className="text-sm text-gray-600">
                  Showing {currentDocuments.length} of {filteredDocuments.length} documents
                </p>
                <Button
                  onClick={handleBulkExport}
                  variant="outline"
                  className="gap-2"
                >
                  <Download className="w-4 h-4" />
                  Export All ({filteredDocuments.length})
                </Button>
              </div>
            )}
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
        ) : currentDocuments.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-700 mb-2">No Documents Found</h3>
                <p className="text-gray-600 mb-4">
                  {searchQuery || statusFilter || patientFilter || dateFrom || dateTo
                    ? 'Try adjusting your filters'
                    : 'No documents have been uploaded yet'}
                </p>
                <Button
                  onClick={() => navigate('/document-upload')}
                  className="gap-2 bg-teal-600 hover:bg-teal-700"
                >
                  <Upload className="w-4 h-4" />
                  Upload First Document
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid gap-3">
              {currentDocuments.map((doc) => (
                <Card key={doc.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className="w-10 h-10 bg-teal-100 rounded-lg flex items-center justify-center flex-shrink-0">
                          <FileText className="w-5 h-5 text-teal-600" />
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <h3 className="font-semibold text-gray-900 truncate">{doc.filename}</h3>
                            <Badge className={`${getStatusColor(doc.status)} flex items-center gap-1 flex-shrink-0`}>
                              {getStatusIcon(doc.status)}
                              {doc.status}
                            </Badge>
                          </div>
                          
                          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-600">
                            <div className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {formatDate(doc.upload_date)}
                            </div>
                            
                            {doc.patient_name && (
                              <div className="flex items-center gap-1">
                                <User className="w-3 h-3" />
                                {doc.patient_name}
                              </div>
                            )}
                            
                            {doc.pages_count && (
                              <span>{doc.pages_count} pages</span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-2 flex-shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleViewDocument(doc)}
                          className="gap-1"
                        >
                          <Eye className="w-3 h-3" />
                          View
                        </Button>
                        
                        {doc.parsed_doc_id && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleExportData(doc, 'json')}
                            className="gap-1"
                          >
                            <Download className="w-3 h-3" />
                            JSON
                          </Button>
                        )}
                        
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
                            window.open(`${backendUrl}/api/gp/document/${doc.id}/view`, '_blank');
                          }}
                          className="gap-1"
                        >
                          <Download className="w-3 h-3" />
                          PDF
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <Card className="mt-6">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-600">
                      Page {currentPage} of {totalPages}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                        disabled={currentPage === totalPages}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default DigitizationArchive;
