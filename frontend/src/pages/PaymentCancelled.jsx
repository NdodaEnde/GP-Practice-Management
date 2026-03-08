import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { XCircle } from 'lucide-react';

const PaymentCancelled = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <Card className="max-w-md w-full">
        <CardHeader>
          <CardTitle className="flex items-center justify-center gap-3 text-orange-600">
            <XCircle className="w-12 h-12" />
            <span className="text-2xl">Payment Cancelled</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="text-center">
            <p className="text-gray-600 mb-4">
              Your payment was cancelled or could not be completed.
            </p>
            <p className="text-sm text-gray-500">
              No charges have been made to your account.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <Button 
              onClick={() => navigate('/billing')}
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              Return to Invoices
            </Button>
            <Button 
              onClick={() => window.history.back()}
              variant="outline"
              className="w-full"
            >
              Go Back
            </Button>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4">
            <p className="text-sm text-gray-700 text-center">
              <strong>Need help?</strong> Contact our billing department at billing@surgiscan.co.za
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PaymentCancelled;
