import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { gpAPI } from '../services/gp';
import { useToast } from '@/hooks/use-toast';
import {
  Upload,
  FileText,
  Stethoscope,
  CheckCircle,
  AlertCircle,
  Loader2,
  Clock,
  X
} from 'lucide-react';

const GPPatientUpload = ({ onProcessingComplete }) => {
  const [uploadState, setUploadState] = useState({
    file: null,
    status: 'idle', // 'idle' | 'uploading' | 'processing' | 'success' | 'error'
    progress: 0,
    error: null,
    result: null
  });
  const [patientIdInput, setPatientIdInput] = useState('');
  const [useTemplates, setUseTemplates] = useState(true); // NEW: Enable template-driven extraction by default
  const { toast } = useToast();

  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setUploadState({
        file,
        status: 'idle',
        progress: 0,
        error: null,
        result: null
      });
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff']
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const processFile = async () => {
    if (!uploadState.file) return;

    setUploadState(prev => ({ ...prev, status: 'uploading', progress: 10 }));

    try {
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadState(prev => {
          if (prev.status === 'uploading' && prev.progress < 90) {
            return { ...prev, progress: prev.progress + 10 };
          }
          return prev;
        });
      }, 500);

      // Switch to processing state
      setTimeout(() => {
        setUploadState(prev => ({ ...prev, status: 'processing', progress: 95 }));
      }, 2000);

      const result = await gpAPI.uploadPatientFile(
        uploadState.file,
        patientIdInput || undefined,
        'full'
      );

      clearInterval(progressInterval);

      if (result.success) {
        console.log('=== GPPatientUpload Debug ===');
        console.log('1. Upload result:', result);
        console.log('2. result.data:', result.data);
        console.log('3. result.data.chunks:', result.data?.chunks);
        console.log('4. Chunks length:', result.data?.chunks?.length);
        
        setUploadState(prev => ({
          ...prev,
          status: 'success',
          progress: 100,
          result
        }));

        toast({
          title: "Processing Complete! 🎉",
          description: `Patient file processed successfully`,
        });

        // Call parent callback
        if (onProcessingComplete) {
          onProcessingComplete(result);
        }
      } else {
        throw new Error(result.message || 'Processing failed');
      }

    } catch (error) {
      setUploadState(prev => ({
        ...prev,
        status: 'error',
        progress: 0,
        error: error.message || 'Processing failed'
      }));

      toast({
        variant: "destructive",
        title: "Processing Failed",
        description: error.message || 'An error occurred while processing the file',
      });
    }
  };

  const resetUpload = () => {
    setUploadState({
      file: null,
      status: 'idle',
      progress: 0,
      error: null,
      result: null
    });
    setPatientIdInput('');
  };

  const getStatusIcon = () => {
    switch (uploadState.status) {
      case 'uploading':
        return <Loader2 className="w-5 h-5 animate-spin text-blue-500" />;
      case 'processing':
        return <Stethoscope className="w-5 h-5 animate-pulse text-blue-500" />;
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Upload className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusMessage = () => {
    switch (uploadState.status) {
      case 'uploading':
        return 'Uploading file...';
      case 'processing':
        return 'Processing with AI - this may take up to 2-3 minutes...';
      case 'success':
        return 'Processing complete!';
      case 'error':
        return 'Processing failed';
      default:
        return 'Ready to process';
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center justify-center gap-2">
          <Stethoscope className="w-8 h-8 text-teal-600" />
          GP Patient File Digitization
        </h1>
        <p className="text-gray-600 mt-2">
          Upload patient files to extract medical information with AI
        </p>
      </div>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Upload Patient File
          </CardTitle>
          <CardDescription>
            Upload PDF or image files containing patient medical records
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Patient ID Input */}
          <div className="space-y-2">
            <Label htmlFor="patient-id">Patient ID (Optional)</Label>
            <Input
              id="patient-id"
              placeholder="Enter existing patient ID or leave blank for new patient"
              value={patientIdInput}
              onChange={(e) => setPatientIdInput(e.target.value)}
              disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
            />
          </div>

          {/* File Drop Zone */}
          <div
            {...getRootProps()}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
              transition-colors duration-200
              ${isDragActive ? 'border-teal-500 bg-teal-50' : 'border-gray-300 hover:border-gray-400'}
              ${uploadState.status === 'uploading' || uploadState.status === 'processing' ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input {...getInputProps()} />

            {uploadState.file ? (
              <div className="space-y-4">
                <div className="flex items-center justify-center gap-3">
                  <FileText className="w-12 h-12 text-teal-500" />
                  <div className="text-left">
                    <p className="font-semibold text-gray-900">{uploadState.file.name}</p>
                    <p className="text-sm text-gray-500">
                      {(uploadState.file.size / 1024 / 1024).toFixed(1)} MB
                    </p>
                  </div>
                  {uploadState.status === 'idle' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        resetUpload();
                      }}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>

                {/* Status */}
                <div className="flex items-center justify-center gap-2">
                  {getStatusIcon()}
                  <span className="text-sm font-medium">{getStatusMessage()}</span>
                </div>

                {/* Progress Bar */}
                {(uploadState.status === 'uploading' || uploadState.status === 'processing') && (
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-teal-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadState.progress}%` }}
                    />
                  </div>
                )}

                {/* Error Message */}
                {uploadState.error && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{uploadState.error}</AlertDescription>
                  </Alert>
                )}

                {/* Success Message */}
                {uploadState.result && (
                  <Alert className="border-green-200 bg-green-50">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <AlertDescription className="text-green-800">
                      <div className="space-y-1">
                        <p><strong>Processing Complete!</strong></p>
                        <p className="text-sm">File processed successfully</p>
                      </div>
                    </AlertDescription>
                  </Alert>
                )}

                {/* Action Buttons */}
                <div className="flex gap-3 justify-center">
                  {uploadState.status === 'idle' && (
                    <Button onClick={processFile} className="gap-2 bg-teal-600 hover:bg-teal-700">
                      <Stethoscope className="w-4 h-4" />
                      Process Patient File
                    </Button>
                  )}

                  {uploadState.status === 'error' && (
                    <Button onClick={resetUpload} variant="outline">
                      Try Again
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <Upload className="w-16 h-16 text-gray-400 mx-auto" />
                <div>
                  <h3 className="text-xl font-semibold text-gray-700">
                    Drop patient file here
                  </h3>
                  <p className="text-gray-500 mt-1">
                    or click to browse
                  </p>
                </div>
                <div className="flex flex-wrap justify-center gap-2 text-xs text-gray-400">
                  <span className="px-2 py-1 bg-gray-100 rounded">PDF</span>
                  <span className="px-2 py-1 bg-gray-100 rounded">JPG</span>
                  <span className="px-2 py-1 bg-gray-100 rounded">PNG</span>
                  <span className="px-2 py-1 bg-gray-100 rounded">TIFF</span>
                  <span className="px-2 py-1 bg-gray-100 rounded">Max 50MB</span>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card className="bg-teal-50 border-teal-200">
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                <Clock className="w-5 h-5 text-teal-600" />
              </div>
            </div>
            <div>
              <h4 className="font-semibold text-teal-900 mb-2">Processing Information</h4>
              <ul className="text-sm text-teal-800 space-y-1">
                <li>• AI processing typically takes 2-3 minutes</li>
                <li>• Extracts demographics, chronic conditions, medications, and vitals</li>
                <li>• Supports handwritten and typed medical records</li>
                <li>• Results are presented for validation before saving</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default GPPatientUpload;
