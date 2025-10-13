import React, { useState } from 'react';
import GPPatientUpload from '../components/GPPatientUpload';
import GPValidationInterface from '../components/GPValidationInterface';

const GPPatientDigitization = () => {
  const [currentStep, setCurrentStep] = useState('upload'); // 'upload' | 'validation'
  const [patientData, setPatientData] = useState(null);

  const handleProcessingComplete = (result) => {
    console.log('Processing complete, received result:', result);
    setPatientData(result);
    setCurrentStep('validation');
  };

  const handleBackToUpload = () => {
    setCurrentStep('upload');
    setPatientData(null);
  };

  const handleValidationComplete = () => {
    // Could navigate to patient list or show success message
    console.log('Validation complete!');
    // Reset to upload for now
    setCurrentStep('upload');
    setPatientData(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {currentStep === 'upload' && (
        <GPPatientUpload onProcessingComplete={handleProcessingComplete} />
      )}

      {currentStep === 'validation' && patientData && (
        <GPValidationInterface
          patientData={patientData}
          onBack={handleBackToUpload}
          onValidationComplete={handleValidationComplete}
        />
      )}
    </div>
  );
};

export default GPPatientDigitization;
