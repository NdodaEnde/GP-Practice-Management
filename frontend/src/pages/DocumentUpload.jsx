import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import gpAPI from '../services/gp';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription 
} from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  Upload, 
  FileText, 
  CheckCircle, 
  AlertCircle,
  Loader2,
  X,
  Package,
  TrendingUp,
  Clock,
  Layers,
  File
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const DEMO_WORKSPACE = 'demo-gp-workspace-001';

const DocumentUpload = () => {
  const { toast } = useToast();
  
  // Mode toggle: 'single' or 'batch'
  const [uploadMode, setUploadMode] = useState('single');
  
  // Single file upload state
  const [singleFile, setSingleFile] = useState(null);
  const [singleProgress, setSingleProgress] = useState(0);
  const [singleStatus, setSingleStatus] = useState('idle'); // idle, uploading, processing, success, error
  const [singleResult, setSingleResult] = useState(null);
  
  // Batch upload state
  const [batchFiles, setBatchFiles] = useState([]);
  const [batchId, setBatchId] = useState(null);
  const [batchStatus, setBatchStatus] = useState(null);
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [statusPolling, setStatusPolling] = useState(null);
  
  // Common state
  const [patientId, setPatientId] = useState('');
  const [useTemplates, setUseTemplates] = useState(true);
  const [recentDocuments, setRecentDocuments] = useState([]);

  // Load recent documents on mount
  useEffect(() => {
    loadRecentDocuments();
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (statusPolling) {
        clearInterval(statusPolling);
      }
    };
  }, [statusPolling]);

  const loadRecentDocuments = async () => {
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/gp/documents?workspace_id=${DEMO_WORKSPACE}&limit=10`
      );
      setRecentDocuments(response.data.documents || []);
    } catch (error) {
      console.error('Failed to load recent documents:', error);
    }
  };

  // === SINGLE FILE UPLOAD === //

  const handleSingleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSingleFile(file);
      setSingleStatus('idle');
      setSingleResult(null);
    }
  };

  const handleSingleUpload = async () => {
    if (!singleFile) return;

    setSingleStatus('uploading');
    setSingleProgress(10);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setSingleProgress(prev => (prev < 90 ? prev + 10 : prev));
      }, 500);

      setTimeout(() => {
        setSingleStatus('processing');
        setSingleProgress(95);
      }, 2000);

      // Upload with template
      const result = useTemplates 
        ? await gpAPI.uploadWithTemplate(singleFile, patientId || undefined)
        : await gpAPI.uploadPatientFile(singleFile, patientId || undefined, 'full');

      clearInterval(progressInterval);

      if (result.success) {
        setSingleStatus('success');
        setSingleProgress(100);
        setSingleResult(result);

        const autoPopulation = result.data?.auto_population;
        const recordsCreated = autoPopulation?.records_created || 0;
        const tablesPopulated = Object.keys(autoPopulation?.tables_populated || {});
        
        let description = `File processed successfully`;
        if (useTemplates && recordsCreated > 0) {
          description = `✅ Created ${recordsCreated} records across ${tablesPopulated.length} tables: ${tablesPopulated.join(', ')}`;
        }

        toast({
          title: "Processing Complete! 🎉",
          description,
        });

        // Reload recent documents
        loadRecentDocuments();
      } else {
        throw new Error(result.message || 'Processing failed');
      }

    } catch (error) {
      setSingleStatus('error');
      setSingleProgress(0);
      
      toast({
        variant: "destructive",
        title: "Processing Failed",
        description: error.message || 'An error occurred',
      });
    }
  };

  const resetSingleUpload = () => {
    setSingleFile(null);
    setSingleStatus('idle');
    setSingleProgress(0);
    setSingleResult(null);
  };

  // === BATCH UPLOAD === //

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.filter(
      newFile => !batchFiles.some(existingFile => existingFile.name === newFile.name)
    );
    
    setBatchFiles(prev => [...prev, ...newFiles]);
    
    if (newFiles.length > 0) {
      toast({
        title: "Files Added",
        description: `Added ${newFiles.length} file(s). Total: ${batchFiles.length + newFiles.length}`,
      });
    }
  }, [batchFiles, toast]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.jpg', '.jpeg', '.png', '.tiff']
    },
    maxSize: 50 * 1024 * 1024,
    disabled: batchProcessing
  });

  const removeBatchFile = (index) => {
    setBatchFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleBatchUpload = async () => {
    if (batchFiles.length === 0) {
      toast({
        variant: "destructive",
        title: "No Files",
        description: "Please add files to upload",
      });
      return;
    }

    if (batchFiles.length > 50) {
      toast({
        variant: "destructive",
        title: "Too Many Files",
        description: "Maximum 50 files per batch",
      });
      return;
    }

    setBatchProcessing(true);

    try {
      const result = await gpAPI.batchUpload(batchFiles, patientId || undefined);

      if (result.success) {
        setBatchId(result.batchId);
        
        toast({
          title: "Batch Upload Started! 🚀",
          description: `Processing ${batchFiles.length} files in background...`,
        });

        // Start polling for status
        startStatusPolling(result.batchId);
      } else {
        throw new Error(result.message);
      }
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Upload Failed",
        description: error.message || 'Batch upload failed',
      });
      setBatchProcessing(false);
    }
  };

  const startStatusPolling = (batchId) => {
    const interval = setInterval(async () => {
      try {
        const statusResult = await gpAPI.getBatchStatus(batchId);
        
        if (statusResult.success) {
          setBatchStatus(statusResult.data);
          
          if (statusResult.data.status === 'completed') {
            clearInterval(interval);
            setStatusPolling(null);
            setBatchProcessing(false);
            
            const progress = statusResult.data.progress;
            toast({
              title: "Batch Complete! ✅",
              description: `Completed: ${progress.completed}, Failed: ${progress.failed}`,
            });

            // Reload recent documents
            loadRecentDocuments();
          }
        }
      } catch (error) {
        console.error('Status polling error:', error);
      }
    }, 2000);

    setStatusPolling(interval);
  };

  const resetBatch = () => {
    if (statusPolling) {
      clearInterval(statusPolling);
      setStatusPolling(null);
    }
    setBatchFiles([]);
    setBatchId(null);
    setBatchStatus(null);
    setBatchProcessing(false);
  };

  const getFileStatusIcon = (status) => {
    switch (status) {
      case 'pending':
        return <div className="w-4 h-4 rounded-full bg-gray-300" />;
      case 'processing':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center justify-center gap-2">
          <Upload className="w-8 h-8 text-blue-600" />
          Document Upload
        </h1>
        <p className="text-gray-600 mt-2">
          Upload single documents or batch process multiple files
        </p>
      </div>

      {/* Mode Toggle */}
      <div className="flex justify-center">
        <div className="inline-flex rounded-lg border border-gray-300 bg-gray-50 p-1">
          <button
            onClick={() => setUploadMode('single')}
            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
              uploadMode === 'single'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <File className="w-4 h-4 inline mr-2" />
            Single File
          </button>
          <button
            onClick={() => setUploadMode('batch')}
            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
              uploadMode === 'batch'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Layers className="w-4 h-4 inline mr-2" />
            Batch Upload
          </button>
        </div>
      </div>

      {/* Upload Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>
                {uploadMode === 'single' ? 'Single File Upload' : 'Batch Upload'}
              </CardTitle>
              <CardDescription>
                {uploadMode === 'single' 
                  ? 'Upload and process one document at a time with detailed progress'
                  : 'Upload and process up to 50 files simultaneously'
                }
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Common Settings - Patient ID & Template Toggle */}
              <div className="space-y-4 pb-4 border-b">
                {/* Patient ID */}
                <div className="space-y-2">
                  <Label htmlFor="patient-id-common">Patient ID (Optional)</Label>
                  <Input
                    id="patient-id-common"
                    placeholder={uploadMode === 'single' ? "Enter existing patient ID" : "Enter patient ID for all files"}
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    disabled={
                      singleStatus === 'uploading' || 
                      singleStatus === 'processing' || 
                      batchProcessing
                    }
                  />
                </div>

                {/* Template Toggle - Common for both modes */}
                <div className="flex items-center space-x-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <input
                    type="checkbox"
                    id="use-templates-common"
                    checked={useTemplates}
                    onChange={(e) => setUseTemplates(e.target.checked)}
                    disabled={
                      singleStatus === 'uploading' || 
                      singleStatus === 'processing' || 
                      batchProcessing
                    }
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <Label htmlFor="use-templates-common" className="text-sm font-medium text-blue-900 cursor-pointer">
                    Use Template-Driven Extraction
                    <span className="block text-xs font-normal text-blue-700 mt-1">
                      Auto-populate immunizations, prescriptions, lab results with ICD-10/NAPPI codes
                    </span>
                  </Label>
                </div>
              </div>

              {/* Mode-Specific Upload Interface */}
              {uploadMode === 'single' ? (
                // === SINGLE FILE MODE === //
                <div className="space-y-4">
                  {/* File Input */}
                  <div className="space-y-2">
                    <Label>Select File</Label>
                    <Input
                      type="file"
                      accept=".pdf,image/*"
                      onChange={handleSingleFileSelect}
                      disabled={singleStatus === 'uploading' || singleStatus === 'processing'}
                    />
                    {singleFile && (
                      <p className="text-sm text-gray-600">
                        Selected: {singleFile.name} ({(singleFile.size / 1024 / 1024).toFixed(2)} MB)
                      </p>
                    )}
                  </div>

                {/* Progress */}
                {(singleStatus === 'uploading' || singleStatus === 'processing') && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>{singleStatus === 'uploading' ? 'Uploading...' : 'Processing...'}</span>
                      <span>{singleProgress}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${singleProgress}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Success Message */}
                {singleResult && singleStatus === 'success' && (
                  <Alert className="border-green-200 bg-green-50">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <AlertDescription className="text-green-800">
                      <div className="space-y-2">
                        <p><strong>Processing Complete!</strong></p>
                        
                        {useTemplates && singleResult.data?.auto_population && (
                          <div className="mt-3 pt-3 border-t border-green-200">
                            <p className="text-sm font-semibold mb-2">📊 Auto-Population Results:</p>
                            {singleResult.data.auto_population.records_created > 0 ? (
                              <div className="space-y-1 text-xs">
                                <p>✅ Created <strong>{singleResult.data.auto_population.records_created}</strong> records</p>
                                {Object.entries(singleResult.data.auto_population.tables_populated || {}).map(([table, ids]) => (
                                  <p key={table} className="ml-4">
                                    • <span className="font-medium capitalize">{table.replace('_', ' ')}</span>: {ids.length} record(s)
                                  </p>
                                ))}
                              </div>
                            ) : (
                              <p className="text-xs">ℹ️ No additional records created</p>
                            )}
                          </div>
                        )}
                      </div>
                    </AlertDescription>
                  </Alert>
                )}

                {/* Error Message */}
                {singleStatus === 'error' && (
                  <Alert className="border-red-200 bg-red-50">
                    <AlertCircle className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-800">
                      Processing failed. Please try again.
                    </AlertDescription>
                  </Alert>
                )}

                {/* Actions */}
                <div className="flex gap-3">
                  {singleStatus === 'idle' && (
                    <Button
                      onClick={handleSingleUpload}
                      disabled={!singleFile}
                      className="flex-1 bg-blue-600 hover:bg-blue-700"
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Process File
                    </Button>
                  )}
                  
                  {(singleStatus === 'success' || singleStatus === 'error') && (
                    <Button
                      onClick={resetSingleUpload}
                      variant="outline"
                      className="flex-1"
                    >
                      Upload Another File
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ) : (
            // === BATCH MODE === //
            <Card>
              <CardHeader>
                <CardTitle>Batch Upload</CardTitle>
                <CardDescription>
                  Upload and process up to 50 files simultaneously
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Patient ID */}
                <div className="space-y-2">
                  <Label htmlFor="patient-id-batch">Patient ID (Optional)</Label>
                  <Input
                    id="patient-id-batch"
                    placeholder="Enter patient ID for all files"
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    disabled={batchProcessing}
                  />
                </div>

                {/* Dropzone */}
                <div
                  {...getRootProps()}
                  className={`
                    border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
                    transition-colors duration-200
                    ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
                    ${batchProcessing ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                >
                  <input {...getInputProps()} />
                  <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  {isDragActive ? (
                    <p className="text-blue-600 font-medium">Drop files here...</p>
                  ) : (
                    <div>
                      <p className="text-gray-700 font-medium">
                        Drop files here or click to browse
                      </p>
                      <p className="text-sm text-gray-500 mt-2">
                        PDF, JPG, PNG, TIFF • Up to 50MB per file • Max 50 files
                      </p>
                    </div>
                  )}
                </div>

                {/* File List */}
                {batchFiles.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <Label>Files ({batchFiles.length})</Label>
                      {!batchProcessing && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setBatchFiles([])}
                        >
                          Clear All
                        </Button>
                      )}
                    </div>
                    <div className="max-h-64 overflow-y-auto space-y-2 border rounded-lg p-3">
                      {batchFiles.map((file, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-2 bg-gray-50 rounded"
                        >
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <FileText className="w-4 h-4 text-blue-500 flex-shrink-0" />
                            <span className="text-sm truncate">{file.name}</span>
                            <span className="text-xs text-gray-500 flex-shrink-0">
                              {(file.size / 1024 / 1024).toFixed(1)} MB
                            </span>
                          </div>
                          {!batchProcessing && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeBatchFile(index)}
                            >
                              <X className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3">
                  {!batchProcessing ? (
                    <Button
                      onClick={handleBatchUpload}
                      disabled={batchFiles.length === 0}
                      className="flex-1 bg-blue-600 hover:bg-blue-700"
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Start Batch Upload ({batchFiles.length} files)
                    </Button>
                  ) : (
                    <Button
                      onClick={resetBatch}
                      variant="outline"
                      className="flex-1"
                    >
                      Cancel & Reset
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Progress/Status Panel */}
        <div className="lg:col-span-1">
          {uploadMode === 'single' ? (
            // Single file status card (placeholder for now)
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8 text-gray-500">
                  <div className="text-4xl mb-2">
                    {singleStatus === 'idle' && '📄'}
                    {singleStatus === 'uploading' && '⬆️'}
                    {singleStatus === 'processing' && '⚙️'}
                    {singleStatus === 'success' && '✅'}
                    {singleStatus === 'error' && '❌'}
                  </div>
                  <p className="text-sm font-medium">
                    {singleStatus === 'idle' && 'Ready to upload'}
                    {singleStatus === 'uploading' && 'Uploading...'}
                    {singleStatus === 'processing' && 'Processing...'}
                    {singleStatus === 'success' && 'Complete!'}
                    {singleStatus === 'error' && 'Failed'}
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            // Batch progress panel
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5" />
                  Batch Progress
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!batchStatus ? (
                  <div className="text-center py-8 text-gray-500">
                    <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No active batch</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Overall Progress */}
                    <div>
                      <div className="flex justify-between text-sm mb-2">
                        <span className="font-medium">Overall Progress</span>
                        <span className="text-gray-600">
                          {batchStatus.progress.completed + batchStatus.progress.failed} / {batchStatus.total_files}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{
                            width: `${((batchStatus.progress.completed + batchStatus.progress.failed) / batchStatus.total_files) * 100}%`
                          }}
                        />
                      </div>
                    </div>

                    {/* Status Counts */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-200">
                        <p className="text-xs text-yellow-700">Pending</p>
                        <p className="text-2xl font-bold text-yellow-900">
                          {batchStatus.progress.pending}
                        </p>
                      </div>
                      <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <p className="text-xs text-blue-700">Processing</p>
                        <p className="text-2xl font-bold text-blue-900">
                          {batchStatus.progress.processing}
                        </p>
                      </div>
                      <div className="p-3 bg-green-50 rounded-lg border border-green-200">
                        <p className="text-xs text-green-700">Completed</p>
                        <p className="text-2xl font-bold text-green-900">
                          {batchStatus.progress.completed}
                        </p>
                      </div>
                      <div className="p-3 bg-red-50 rounded-lg border border-red-200">
                        <p className="text-xs text-red-700">Failed</p>
                        <p className="text-2xl font-bold text-red-900">
                          {batchStatus.progress.failed}
                        </p>
                      </div>
                    </div>

                    {/* File Status List */}
                    <div className="space-y-2">
                      <Label className="text-sm font-medium">File Status</Label>
                      <div className="max-h-64 overflow-y-auto space-y-2 border rounded-lg p-2">
                        {batchStatus.files?.map((file) => (
                          <div
                            key={file.file_id}
                            className="flex items-center gap-2 p-2 bg-gray-50 rounded text-sm"
                          >
                            {getFileStatusIcon(file.status)}
                            <span className="flex-1 truncate text-xs">{file.filename}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Recent Documents */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Documents</CardTitle>
          <CardDescription>
            Recently uploaded and processed documents
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentDocuments.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No documents yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recentDocuments.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-blue-500" />
                    <div>
                      <p className="font-medium text-sm">{doc.filename}</p>
                      <p className="text-xs text-gray-500">
                        {formatDate(doc.created_at)} • Status: {doc.status}
                      </p>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${
                    doc.status === 'extracted' ? 'bg-green-100 text-green-700' :
                    doc.status === 'parsed' ? 'bg-blue-100 text-blue-700' :
                    doc.status === 'processing' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {doc.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default DocumentUpload;
