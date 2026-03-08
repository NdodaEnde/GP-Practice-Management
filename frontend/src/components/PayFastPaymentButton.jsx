import React, { useState } from 'react';
import { Button } from './ui/button';
import { DollarSign, CreditCard } from 'lucide-react';
import axios from 'axios';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const PayFastPaymentButton = ({ invoice, customerEmail, customerPhone, onPaymentInitiated }) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  const handlePayment = async () => {
    setLoading(true);

    try {
      // Call backend to initiate payment
      const response = await axios.post(`${BACKEND_URL}/api/payfast/initiate`, {
        invoice_id: invoice.id,
        amount: parseFloat(invoice.amount_outstanding),
        customer_email: customerEmail,
        customer_phone: customerPhone || '0000000000',
        invoice_number: invoice.invoice_number
      });

      if (response.data.success) {
        // Create a form and submit it to PayFast
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = response.data.payment_url;
        form.target = '_blank'; // Open in new tab

        // Add all payment data as hidden fields
        Object.entries(response.data.payment_data).forEach(([key, value]) => {
          const input = document.createElement('input');
          input.type = 'hidden';
          input.name = key;
          input.value = value;
          form.appendChild(input);
        });

        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);

        toast({
          title: "Payment Initiated",
          description: "Redirecting to PayFast payment page..."
        });

        if (onPaymentInitiated) {
          onPaymentInitiated(response.data.payment_id);
        }
      }
    } catch (error) {
      console.error('Error initiating payment:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to initiate payment",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      onClick={handlePayment}
      disabled={loading || !invoice.amount_outstanding || parseFloat(invoice.amount_outstanding) <= 0}
      className="bg-green-600 hover:bg-green-700"
    >
      <CreditCard className="w-4 h-4 mr-2" />
      {loading ? 'Processing...' : `Pay R ${parseFloat(invoice.amount_outstanding).toFixed(2)} Online`}
    </Button>
  );
};

export default PayFastPaymentButton;
