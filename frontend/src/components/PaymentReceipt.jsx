import React, { useState } from 'react';
import { X, Printer } from 'lucide-react';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { Button } from '../components/ui/button';

const PaymentReceipt = ({ payment, invoice, open, onClose }) => {
  if (!payment || !invoice) return null;

  const handlePrint = () => {
    window.print();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto p-0">
        <div className="print:p-8">
          {/* Header with Actions */}
          <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between print:hidden">
            <h2 className="text-xl font-bold">Payment Receipt</h2>
            <div className="flex items-center gap-2">
              <Button onClick={handlePrint} size="sm" variant="outline">
                <Printer className="w-4 h-4 mr-2" />
                Print Receipt
              </Button>
              <Button onClick={onClose} size="sm" variant="ghost">
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Receipt */}
          <div className="p-8 bg-white">
            {/* Header */}
            <div className="border-b-2 border-green-600 pb-6 mb-6">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-3xl font-bold text-gray-900 mb-2">SurgiScan Health</h1>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>123 Medical Plaza, Suite 400</p>
                    <p>Johannesburg, Gauteng, 2000</p>
                    <p>South Africa</p>
                    <p className="mt-2">Tel: +27 11 123 4567</p>
                    <p>Email: billing@surgiscan.co.za</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="bg-green-600 text-white px-6 py-3 rounded-lg inline-block">
                    <div className="text-sm font-medium">PAYMENT RECEIPT</div>
                    <div className="text-2xl font-bold mt-1">{payment.id.slice(0, 13).toUpperCase()}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Receipt Details */}
            <div className="grid grid-cols-2 gap-6 mb-8">
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase">Received From:</h3>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="font-semibold text-gray-900">Patient ID: {invoice.patient_id.slice(0, 8)}</p>
                  {invoice.medical_aid_name && (
                    <>
                      <p className="text-sm text-gray-600 mt-2">Medical Aid: {invoice.medical_aid_name}</p>
                      <p className="text-sm text-gray-600">Member No: {invoice.medical_aid_number}</p>
                    </>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase">Payment Details:</h3>
                <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Payment Date:</span>
                    <span className="text-sm font-medium">{new Date(payment.payment_date).toLocaleDateString('en-ZA')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Payment Method:</span>
                    <span className="text-sm font-medium uppercase">{payment.payment_method.replace('_', ' ')}</span>
                  </div>
                  {payment.reference_number && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Reference:</span>
                      <span className="text-sm font-medium">{payment.reference_number}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Invoice:</span>
                    <span className="text-sm font-medium">{invoice.invoice_number}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Payment Amount */}
            <div className="bg-green-50 border-2 border-green-200 rounded-lg p-6 mb-8">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Amount Received</p>
                  <p className="text-4xl font-bold text-green-600">R {parseFloat(payment.amount).toFixed(2)}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-600 mb-1">Invoice Total</p>
                  <p className="text-lg font-semibold text-gray-900">R {parseFloat(invoice.total_amount).toFixed(2)}</p>
                  <p className="text-sm text-gray-600 mt-2">Amount Paid</p>
                  <p className="text-lg font-semibold text-green-600">R {parseFloat(invoice.amount_paid).toFixed(2)}</p>
                  <p className="text-sm text-gray-600 mt-2">Balance Due</p>
                  <p className="text-lg font-semibold text-orange-600">R {parseFloat(invoice.amount_outstanding).toFixed(2)}</p>
                </div>
              </div>
            </div>

            {/* Payment Notes */}
            {payment.notes && (
              <div className="mb-8">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase">Payment Notes:</h3>
                <p className="text-sm text-gray-600 bg-gray-50 p-4 rounded">{payment.notes}</p>
              </div>
            )}

            {/* Invoice Items Summary */}
            <div className="mb-8">
              <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase">Invoice Items:</h3>
              <div className="space-y-2">
                {invoice.items && invoice.items.slice(0, 5).map((item, index) => (
                  <div key={index} className="flex justify-between text-sm bg-gray-50 p-2 rounded">
                    <span className="text-gray-700">{item.description}</span>
                    <span className="font-medium">R {parseFloat(item.total_price).toFixed(2)}</span>
                  </div>
                ))}
                {invoice.items && invoice.items.length > 5 && (
                  <p className="text-sm text-gray-500 italic">...and {invoice.items.length - 5} more items</p>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="border-t pt-6 mt-8">
              <div className="text-center text-sm text-gray-500 space-y-2">
                <p className="font-semibold text-gray-700 text-lg mb-4">Thank you for your payment!</p>
                <p>This is an official payment receipt from SurgiScan Health</p>
                <p className="text-xs">
                  Receipt generated on {new Date().toLocaleDateString('en-ZA')} at {new Date().toLocaleTimeString('en-ZA')}
                </p>
                <p className="mt-4 text-xs text-gray-400">
                  This receipt was generated electronically and is valid without a signature
                </p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PaymentReceipt;
