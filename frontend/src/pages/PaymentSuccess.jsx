import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { CheckCircle } from 'lucide-react';

const PaymentSuccess = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    // Log payment success
    console.log('Payment successful!', Object.fromEntries(searchParams));
  }, [searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <Card className="max-w-md w-full">
        <CardHeader>
          <CardTitle className="flex items-center justify-center gap-3 text-green-600">
            <CheckCircle className="w-12 h-12" />
            <span className="text-2xl">Payment Successful!</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="text-center">
            <p className="text-gray-600 mb-4">
              Your payment has been processed successfully.
            </p>
            <p className="text-sm text-gray-500 mb-4">
              You will receive a payment confirmation email shortly.
            </p>
            
            {/* Display payment details if available */}
            {searchParams.get('pf_payment_id') && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 mt-4">
                <p className="text-sm text-gray-700">
                  <strong>Payment Reference:</strong>
                </p>
                <p className="text-sm text-gray-600 font-mono mt-1">
                  {searchParams.get('pf_payment_id')}
                </p>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <Button 
              onClick={() => navigate('/billing')}
              className="w-full bg-green-600 hover:bg-green-700"
            >
              View Invoices
            </Button>
            <Button 
              onClick={() => navigate('/financial-dashboard')}
              variant="outline"
              className="w-full"
            >
              View Financial Dashboard
            </Button>
          </div>

          <div className="text-center">
            <p className="text-xs text-gray-400 mt-4">
              Note: It may take a few moments for the payment to reflect in your account.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PaymentSuccess;
