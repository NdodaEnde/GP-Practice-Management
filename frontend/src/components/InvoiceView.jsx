import React, { useState } from 'react';
import { X, Printer, Download, DollarSign } from 'lucide-react';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent } from '../components/ui/card';
import axios from 'axios';
import { useToast } from '../hooks/use-toast';
import PaymentReceipt from './PaymentReceipt';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const InvoiceView = ({ invoice: initialInvoice, open, onClose, onPaymentRecorded }) => {
  const { toast } = useToast();
  const [invoice, setInvoice] = useState(initialInvoice);
  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const [showSplitPayment, setShowSplitPayment] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [receiptData, setReceiptData] = useState(null);
  const [showReceipt, setShowReceipt] = useState(false);

  // Single payment form
  const [paymentForm, setPaymentForm] = useState({
    payment_date: new Date().toISOString().split('T')[0],
    amount: '',
    payment_method: 'cash',
    reference_number: '',
    notes: ''
  });

  // Split payment form
  const [splitPaymentForm, setSplitPaymentForm] = useState({
    payment_date: new Date().toISOString().split('T')[0],
    patient_amount: '',
    patient_method: 'cash',
    patient_reference: '',
    medical_aid_amount: '',
    medical_aid_reference: '',
    notes: ''
  });

  // Update invoice state when prop changes
  React.useEffect(() => {
    setInvoice(initialInvoice);
  }, [initialInvoice]);

  if (!invoice) return null;

  const refreshInvoice = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/invoices/${invoice.id}`);
      setInvoice(response.data);
      if (onPaymentRecorded) {
        onPaymentRecorded(response.data);
      }
    } catch (error) {
      console.error('Error refreshing invoice:', error);
    }
  };

  const handleSinglePayment = async (e) => {
    e.preventDefault();
    setProcessing(true);

    try {
      const paymentData = {
        invoice_id: invoice.id,
        payment_date: paymentForm.payment_date,
        amount: parseFloat(paymentForm.amount),
        payment_method: paymentForm.payment_method,
        reference_number: paymentForm.reference_number || null,
        notes: paymentForm.notes || null
      };

      const response = await axios.post(`${BACKEND_URL}/api/payments`, paymentData);

      toast({
        title: "Success",
        description: "Payment recorded successfully"
      });

      // Show receipt
      await refreshInvoice();
      const updatedInvoice = await axios.get(`${BACKEND_URL}/api/invoices/${invoice.id}`);
      const lastPayment = updatedInvoice.data.payments[updatedInvoice.data.payments.length - 1];
      
      setReceiptData({ payment: lastPayment, invoice: updatedInvoice.data });
      setShowReceipt(true);

      // Reset form
      setPaymentForm({
        payment_date: new Date().toISOString().split('T')[0],
        amount: '',
        payment_method: 'cash',
        reference_number: '',
        notes: ''
      });
      setShowPaymentForm(false);
    } catch (error) {
      console.error('Error recording payment:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to record payment",
        variant: "destructive"
      });
    } finally {
      setProcessing(false);
    }
  };

  const handleSplitPayment = async (e) => {
    e.preventDefault();
    setProcessing(true);

    try {
      // Record patient payment
      if (splitPaymentForm.patient_amount && parseFloat(splitPaymentForm.patient_amount) > 0) {
        await axios.post(`${BACKEND_URL}/api/payments`, {
          invoice_id: invoice.id,
          payment_date: splitPaymentForm.payment_date,
          amount: parseFloat(splitPaymentForm.patient_amount),
          payment_method: splitPaymentForm.patient_method,
          reference_number: splitPaymentForm.patient_reference || `Patient Co-pay`,
          notes: `Patient portion - ${splitPaymentForm.notes || ''}`
        });
      }

      // Record medical aid payment
      if (splitPaymentForm.medical_aid_amount && parseFloat(splitPaymentForm.medical_aid_amount) > 0) {
        const medAidResponse = await axios.post(`${BACKEND_URL}/api/payments`, {
          invoice_id: invoice.id,
          payment_date: splitPaymentForm.payment_date,
          amount: parseFloat(splitPaymentForm.medical_aid_amount),
          payment_method: 'medical_aid',
          reference_number: splitPaymentForm.medical_aid_reference || `Medical Aid Payment`,
          notes: `Medical aid portion - ${splitPaymentForm.notes || ''}`
        });
      }

      toast({
        title: "Success",
        description: "Split payment recorded successfully"
      });

      // Refresh and show receipt for combined payment
      await refreshInvoice();
      const updatedInvoice = await axios.get(`${BACKEND_URL}/api/invoices/${invoice.id}`);
      const lastPayment = updatedInvoice.data.payments[updatedInvoice.data.payments.length - 1];
      
      setReceiptData({ payment: lastPayment, invoice: updatedInvoice.data });
      setShowReceipt(true);

      // Reset form
      setSplitPaymentForm({
        payment_date: new Date().toISOString().split('T')[0],
        patient_amount: '',
        patient_method: 'cash',
        patient_reference: '',
        medical_aid_amount: '',
        medical_aid_reference: '',
        notes: ''
      });
      setShowSplitPayment(false);
    } catch (error) {
      console.error('Error recording split payment:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to record split payment",
        variant: "destructive"
      });
    } finally {
      setProcessing(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDownload = () => {
    window.print();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto p-0">
        <div className="print:p-8">
          {/* Header with Actions */}
          <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between print:hidden">
            <h2 className="text-xl font-bold">Invoice Details</h2>
            <div className="flex items-center gap-2">
              <Button onClick={handlePrint} size="sm" variant="outline">
                <Printer className="w-4 h-4 mr-2" />
                Print
              </Button>
              <Button onClick={handleDownload} size="sm" variant="outline">
                <Download className="w-4 h-4 mr-2" />
                Download
              </Button>
              <Button onClick={onClose} size="sm" variant="ghost">
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Professional Invoice */}
          <div className="p-8 bg-white">
            {/* Practice Header */}
            <div className="border-b-2 border-blue-600 pb-6 mb-6">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-3xl font-bold text-gray-900 mb-2">SurgiScan Health</h1>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>123 Medical Plaza, Suite 400</p>
                    <p>Johannesburg, Gauteng, 2000</p>
                    <p>South Africa</p>
                    <p className="mt-2">Tel: +27 11 123 4567</p>
                    <p>Email: billing@surgiscan.co.za</p>
                    <p>Practice No: 0123456789</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="bg-blue-600 text-white px-6 py-3 rounded-lg inline-block">
                    <div className="text-sm font-medium">INVOICE</div>
                    <div className="text-2xl font-bold mt-1">{invoice.invoice_number}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Invoice Details Grid */}
            <div className="grid grid-cols-2 gap-6 mb-8">
              {/* Bill To */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase">Bill To:</h3>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="font-semibold text-gray-900">Patient ID: {invoice.patient_id.slice(0, 8)}</p>
                  {invoice.medical_aid_name && (
                    <>
                      <p className="text-sm text-gray-600 mt-2">Medical Aid: {invoice.medical_aid_name}</p>
                      <p className="text-sm text-gray-600">Member No: {invoice.medical_aid_number}</p>
                      {invoice.medical_aid_plan && (
                        <p className="text-sm text-gray-600">Plan: {invoice.medical_aid_plan}</p>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Invoice Info */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase">Invoice Details:</h3>
                <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Invoice Date:</span>
                    <span className="text-sm font-medium">{new Date(invoice.invoice_date).toLocaleDateString('en-ZA')}</span>
                  </div>
                  {invoice.due_date && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Due Date:</span>
                      <span className="text-sm font-medium">{new Date(invoice.due_date).toLocaleDateString('en-ZA')}</span>
                    </div>
                  )}
                  {invoice.encounter_id && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Encounter:</span>
                      <span className="text-sm font-medium">{invoice.encounter_id.slice(0, 8)}</span>
                    </div>
                  )}
                  <div className="flex justify-between pt-2 border-t">
                    <span className="text-sm text-gray-600">Status:</span>
                    <span className={`text-sm font-semibold px-2 py-1 rounded ${
                      invoice.payment_status === 'paid' 
                        ? 'bg-green-100 text-green-700'
                        : invoice.payment_status === 'partially_paid'
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-red-100 text-red-700'
                    }`}>
                      {invoice.payment_status.replace('_', ' ').toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Invoice Items Table */}
            <div className="mb-8">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-gray-100 border-b-2 border-gray-300">
                    <th className="text-left p-3 font-semibold text-gray-700">Description</th>
                    <th className="text-center p-3 font-semibold text-gray-700">Code</th>
                    <th className="text-center p-3 font-semibold text-gray-700">Qty</th>
                    <th className="text-right p-3 font-semibold text-gray-700">Unit Price</th>
                    <th className="text-right p-3 font-semibold text-gray-700">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.items && invoice.items.map((item, index) => (
                    <tr key={index} className="border-b border-gray-200">
                      <td className="p-3">
                        <div>
                          <p className="font-medium text-gray-900">{item.description}</p>
                          <p className="text-xs text-gray-500 capitalize">{item.item_type.replace('_', ' ')}</p>
                        </div>
                      </td>
                      <td className="p-3 text-center text-sm">
                        {item.icd10_code && (
                          <div className="text-xs">
                            <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded">ICD-10: {item.icd10_code}</span>
                          </div>
                        )}
                        {item.nappi_code && (
                          <div className="text-xs mt-1">
                            <span className="bg-green-100 text-green-700 px-2 py-1 rounded">NAPPI: {item.nappi_code}</span>
                          </div>
                        )}
                        {item.procedure_code && (
                          <div className="text-xs mt-1">
                            <span className="bg-purple-100 text-purple-700 px-2 py-1 rounded">Proc: {item.procedure_code}</span>
                          </div>
                        )}
                        {!item.icd10_code && !item.nappi_code && !item.procedure_code && (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="p-3 text-center">{item.quantity}</td>
                      <td className="p-3 text-right">R {parseFloat(item.unit_price).toFixed(2)}</td>
                      <td className="p-3 text-right font-medium">R {parseFloat(item.total_price).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Totals Section */}
            <div className="flex justify-end mb-8">
              <div className="w-80">
                <div className="space-y-2">
                  <div className="flex justify-between py-2">
                    <span className="text-gray-600">Subtotal:</span>
                    <span className="font-medium">R {parseFloat(invoice.subtotal).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-gray-600">VAT (15%):</span>
                    <span className="font-medium">R {parseFloat(invoice.vat_amount).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between py-3 border-t-2 border-gray-300">
                    <span className="text-lg font-bold text-gray-900">Total Amount:</span>
                    <span className="text-lg font-bold text-blue-600">R {parseFloat(invoice.total_amount).toFixed(2)}</span>
                  </div>
                  
                  {/* Payment Information */}
                  {(invoice.amount_paid > 0 || invoice.medical_aid_portion > 0) && (
                    <>
                      <div className="border-t pt-3 mt-3">
                        {invoice.medical_aid_portion > 0 && (
                          <div className="flex justify-between py-1 text-sm">
                            <span className="text-gray-600">Medical Aid Portion:</span>
                            <span className="font-medium text-green-600">R {parseFloat(invoice.medical_aid_portion).toFixed(2)}</span>
                          </div>
                        )}
                        {invoice.patient_portion > 0 && (
                          <div className="flex justify-between py-1 text-sm">
                            <span className="text-gray-600">Patient Co-pay:</span>
                            <span className="font-medium">R {parseFloat(invoice.patient_portion).toFixed(2)}</span>
                          </div>
                        )}
                        <div className="flex justify-between py-2 border-t mt-2">
                          <span className="font-semibold text-gray-700">Amount Paid:</span>
                          <span className="font-semibold text-green-600">R {parseFloat(invoice.amount_paid).toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between py-2">
                          <span className="font-semibold text-gray-700">Amount Outstanding:</span>
                          <span className={`font-semibold ${parseFloat(invoice.amount_outstanding) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                            R {parseFloat(invoice.amount_outstanding).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Payment History */}
            {invoice.payments && invoice.payments.length > 0 && (
              <div className="mb-8 border-t pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Payment History</h3>
                <div className="space-y-2">
                  {invoice.payments.map((payment, index) => (
                    <div key={index} className="flex items-center justify-between bg-gray-50 p-3 rounded">
                      <div>
                        <p className="font-medium text-gray-900">
                          {payment.payment_method.toUpperCase()} - {payment.reference_number || 'N/A'}
                        </p>
                        <p className="text-sm text-gray-600">
                          {new Date(payment.payment_date).toLocaleDateString('en-ZA')}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-green-600">R {parseFloat(payment.amount).toFixed(2)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Notes */}
            {invoice.notes && (
              <div className="border-t pt-6 mb-8">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase">Notes:</h3>
                <p className="text-sm text-gray-600 bg-gray-50 p-4 rounded">{invoice.notes}</p>
              </div>
            )}

            {/* Footer */}
            <div className="border-t pt-6 mt-8">
              <div className="text-center text-sm text-gray-500 space-y-1">
                <p className="font-semibold text-gray-700">Banking Details</p>
                <p>Bank: Standard Bank | Account: SurgiScan Health</p>
                <p>Account No: 123456789 | Branch Code: 051001</p>
                <p className="mt-4 text-xs">
                  Please use invoice number {invoice.invoice_number} as payment reference
                </p>
                <p className="mt-4 text-xs text-gray-400">
                  This invoice was generated electronically and is valid without a signature
                </p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default InvoiceView;
