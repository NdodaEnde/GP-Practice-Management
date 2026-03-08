import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
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
import { 
  Upload, 
  FileText, 
  CheckCircle, 
  AlertCircle,
  Loader2,
  X,
  Package,
  TrendingUp
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BatchUpload = () => {
  const { toast } = useToast();
  const [files, setFiles] = useState([]);
  const [patientId, setPatientId] = useState('');
  const [batchId, setBatchId] = useState(null);
  const [batchStatus, setBatchStatus] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusPolling, setStatusPolling] = useState(null);

  const onDrop = useCallback((acceptedFiles) => {
    // Filter out duplicates and add new files
    const newFiles = acceptedFiles.filter(
      newFile => !files.some(existingFile => existingFile.name === newFile.name)
    );
    
    setFiles(prev => [...prev, ...newFiles]);
    
    toast({
      title: "Files Added",
      description: `Added ${newFiles.length} file(s). Total: ${files.length + newFiles.length}`,
    });
  }, [files, toast]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.jpg', '.jpeg', '.png', '.tiff']
    },
    maxSize: 50 * 1024 * 1024, // 50MB per file
    disabled: isProcessing
  });

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleBatchUpload = async () => {
    if (files.length === 0) {
      toast({
        variant: "destructive",
        title: "No Files",
        description: "Please add files to upload",
      });
      return;
    }

    if (files.length > 50) {
      toast({
        variant: "destructive",
        title: "Too Many Files",
        description: "Maximum 50 files per batch. Please remove some files.",
      });
      return;
    }

    setIsProcessing(true);

    try {
      // Start batch upload
      const result = await gpAPI.batchUpload(
        files,
        patientId || undefined
      );

      if (result.success) {
        setBatchId(result.batchId);
        
        toast({
          title: "Batch Upload Started! 🚀",
          description: `Processing ${files.length} files in background...`,
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
        description: error.message || 'An error occurred during batch upload',
      });
      setIsProcessing(false);
    }
  };

  const startStatusPolling = (batchId) => {
    const interval = setInterval(async () => {
      try {
        const statusResult = await gpAPI.getBatchStatus(batchId);
        
        if (statusResult.success) {
          setBatchStatus(statusResult.data);
          
          // Stop polling if batch is complete
          if (statusResult.data.status === 'completed') {
            clearInterval(interval);
            setStatusPolling(null);
            setIsProcessing(false);
            
            const progress = statusResult.data.progress;
            toast({
              title: "Batch Complete! ✅",
              description: `Completed: ${progress.completed}, Failed: ${progress.failed}`,
            });
          }
        }
      } catch (error) {
        console.error('Status polling error:', error);
      }
    }, 2000); // Poll every 2 seconds

    setStatusPolling(interval);
  };

  const resetBatch = () => {
    if (statusPolling) {
      clearInterval(statusPolling);
      setStatusPolling(null);
    }
    setFiles([]);
    setBatchId(null);
    setBatchStatus(null);
    setIsProcessing(false);
    setPatientId('');
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (statusPolling) {
        clearInterval(statusPolling);
      }
    };
  }, [statusPolling]);

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

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center justify-center gap-2">
          <Package className="w-8 h-8 text-blue-600" />
          Batch Document Upload
        </h1>
        <p className="text-gray-600 mt-2">
          Upload multiple patient files at once (up to 50 files)
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Section */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="w-5 h-5" />
                Upload Files
              </CardTitle>
              <CardDescription>
                Add multiple PDF or image files for batch processing
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Patient ID Input */}
              <div className="space-y-2">
                <Label htmlFor="patient-id">Patient ID (Optional)</Label>
                <Input
                  id="patient-id"
                  placeholder="Enter patient ID for all files"
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                  disabled={isProcessing}
                />
              </div>

              {/* Dropzone */}
              <div
                {...getRootProps()}
                className={`
                  border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
                  transition-colors duration-200
                  ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
                  ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}
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
              {files.length > 0 && (
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Files ({files.length})</Label>
                    {!isProcessing && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setFiles([])}
                      >
                        Clear All
                      </Button>
                    )}
                  </div>
                  <div className="max-h-64 overflow-y-auto space-y-2 border rounded-lg p-3">
                    {files.map((file, index) => (
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
                        {!isProcessing && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeFile(index)}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Button */}
              <div className="flex gap-3">
                {!isProcessing ? (
                  <Button
                    onClick={handleBatchUpload}
                    disabled={files.length === 0}
                    className="flex-1 bg-blue-600 hover:bg-blue-700"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Start Batch Upload ({files.length} files)
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
        </div>

        {/* Progress Section */}
        <div className="lg:col-span-1">
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
                  <p className="text-xs mt-1">Upload files to start processing</p>
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
                      {batchStatus.files?.map((file, index) => (
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
        </div>
      </div>
    </div>
  );
};

export default BatchUpload;
