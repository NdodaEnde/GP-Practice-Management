import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Plus, Trash2, Receipt, DollarSign } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const BillingTestPage = () => {
  const { toast } = useToast();
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState('');
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(false);

  // Invoice form state
  const [invoiceForm, setInvoiceForm] = useState({
    invoice_date: new Date().toISOString().split('T')[0],
    medical_aid_name: '',
    medical_aid_number: '',
    medical_aid_plan: '',
    notes: ''
  });

  // Invoice items
  const [items, setItems] = useState([
    {
      item_type: 'consultation',
      description: '',
      quantity: 1,
      unit_price: 0,
      icd10_code: '',
      nappi_code: '',
      procedure_code: ''
    }
  ]);

  // Payment form state
  const [paymentForm, setPaymentForm] = useState({
    invoice_id: '',
    payment_date: new Date().toISOString().split('T')[0],
    amount: 0,
    payment_method: 'cash',
    reference_number: '',
    notes: ''
  });

  useEffect(() => {
    loadPatients();
  }, []);

  useEffect(() => {
    if (selectedPatient) {
      loadPatientInvoices();
    }
  }, [selectedPatient]);

  const loadPatients = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/patients`);
      setPatients(response.data || []);
    } catch (error) {
      console.error('Error loading patients:', error);
    }
  };

  const loadPatientInvoices = async () => {
    if (!selectedPatient) return;

    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/invoices/patient/${selectedPatient}`);
      setInvoices(response.data.invoices || []);
    } catch (error) {
      console.error('Error loading invoices:', error);
      toast({
        title: "Error",
        description: "Failed to load invoices",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const addItem = () => {
    setItems([...items, {
      item_type: 'consultation',
      description: '',
      quantity: 1,
      unit_price: 0,
      icd10_code: '',
      nappi_code: '',
      procedure_code: ''
    }]);
  };

  const removeItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index, field, value) => {
    const newItems = [...items];
    newItems[index][field] = value;
    setItems(newItems);
  };

  const calculateTotals = () => {
    const subtotal = items.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0);
    const vat = subtotal * 0.15;
    const total = subtotal + vat;
    return { subtotal, vat, total };
  };

  const createInvoice = async (e) => {
    e.preventDefault();
    
    if (!selectedPatient) {
      toast({
        title: "Error",
        description: "Please select a patient",
        variant: "destructive"
      });
      return;
    }

    setLoading(true);
    try {
      const invoiceData = {
        patient_id: selectedPatient,
        invoice_date: invoiceForm.invoice_date,
        items: items.map(item => ({
          item_type: item.item_type,
          description: item.description,
          quantity: parseFloat(item.quantity),
          unit_price: parseFloat(item.unit_price),
          icd10_code: item.icd10_code || null,
          nappi_code: item.nappi_code || null,
          procedure_code: item.procedure_code || null
        })),
        medical_aid_name: invoiceForm.medical_aid_name || null,
        medical_aid_number: invoiceForm.medical_aid_number || null,
        medical_aid_plan: invoiceForm.medical_aid_plan || null,
        notes: invoiceForm.notes || null
      };

      const response = await axios.post(`${BACKEND_URL}/api/invoices`, invoiceData);

      toast({
        title: "Success",
        description: `Invoice ${response.data.invoice_number} created successfully`
      });

      // Reset form
      setItems([{
        item_type: 'consultation',
        description: '',
        quantity: 1,
        unit_price: 0,
        icd10_code: '',
        nappi_code: '',
        procedure_code: ''
      }]);
      setInvoiceForm({
        invoice_date: new Date().toISOString().split('T')[0],
        medical_aid_name: '',
        medical_aid_number: '',
        medical_aid_plan: '',
        notes: ''
      });

      loadPatientInvoices();
    } catch (error) {
      console.error('Error creating invoice:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to create invoice",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const recordPayment = async (e) => {
    e.preventDefault();

    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/payments`, {
        invoice_id: paymentForm.invoice_id,
        payment_date: paymentForm.payment_date,
        amount: parseFloat(paymentForm.amount),
        payment_method: paymentForm.payment_method,
        reference_number: paymentForm.reference_number || null,
        notes: paymentForm.notes || null
      });

      toast({
        title: "Success",
        description: "Payment recorded successfully"
      });

      // Reset form
      setPaymentForm({
        invoice_id: '',
        payment_date: new Date().toISOString().split('T')[0],
        amount: 0,
        payment_method: 'cash',
        reference_number: '',
        notes: ''
      });

      loadPatientInvoices();
    } catch (error) {
      console.error('Error recording payment:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to record payment",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const { subtotal, vat, total } = calculateTotals();

  const getPaymentStatusColor = (status) => {
    switch (status) {
      case 'paid':
        return 'bg-green-100 text-green-800';
      case 'partially_paid':
        return 'bg-yellow-100 text-yellow-800';
      case 'unpaid':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Receipt className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Billing & Invoices</h1>
        </div>
        <p className="text-gray-600">Create invoices, record payments, and manage medical aid claims</p>
      </div>

      {/* Patient Selection */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Select Patient</CardTitle>
        </CardHeader>
        <CardContent>
          <select
            value={selectedPatient}
            onChange={(e) => setSelectedPatient(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">-- Select a patient --</option>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.first_name} {patient.last_name} ({patient.id_number})
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      {selectedPatient && (
        <>
          {/* Create Invoice Form */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Receipt className="w-5 h-5" />
                Create Invoice
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={createInvoice} className="space-y-6">
                {/* Invoice Date and Medical Aid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label>Invoice Date</Label>
                    <Input
                      type="date"
                      value={invoiceForm.invoice_date}
                      onChange={(e) => setInvoiceForm({...invoiceForm, invoice_date: e.target.value})}
                      required
                    />
                  </div>
                  <div>
                    <Label>Medical Aid Name</Label>
                    <Input
                      placeholder="e.g., Discovery Health"
                      value={invoiceForm.medical_aid_name}
                      onChange={(e) => setInvoiceForm({...invoiceForm, medical_aid_name: e.target.value})}
                    />
                  </div>
                  <div>
                    <Label>Medical Aid Number</Label>
                    <Input
                      placeholder="Member number"
                      value={invoiceForm.medical_aid_number}
                      onChange={(e) => setInvoiceForm({...invoiceForm, medical_aid_number: e.target.value})}
                    />
                  </div>
                  <div>
                    <Label>Medical Aid Plan</Label>
                    <Input
                      placeholder="e.g., Executive Plan"
                      value={invoiceForm.medical_aid_plan}
                      onChange={(e) => setInvoiceForm({...invoiceForm, medical_aid_plan: e.target.value})}
                    />
                  </div>
                </div>

                {/* Invoice Items */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label className="text-lg">Invoice Items</Label>
                    <Button type="button" onClick={addItem} size="sm" variant="outline">
                      <Plus className="w-4 h-4 mr-1" />
                      Add Item
                    </Button>
                  </div>

                  {items.map((item, index) => (
                    <Card key={index} className="p-4 border-2">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold">Item {index + 1}</span>
                          {items.length > 1 && (
                            <Button
                              type="button"
                              onClick={() => removeItem(index)}
                              size="sm"
                              variant="ghost"
                              className="text-red-500"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div>
                            <Label>Item Type</Label>
                            <select
                              value={item.item_type}
                              onChange={(e) => updateItem(index, 'item_type', e.target.value)}
                              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                            >
                              <option value="consultation">Consultation</option>
                              <option value="medication">Medication</option>
                              <option value="procedure">Procedure</option>
                              <option value="lab_test">Lab Test</option>
                              <option value="immunization">Immunization</option>
                              <option value="other">Other</option>
                            </select>
                          </div>

                          <div className="md:col-span-2">
                            <Label>Description</Label>
                            <Input
                              placeholder="e.g., General Consultation"
                              value={item.description}
                              onChange={(e) => updateItem(index, 'description', e.target.value)}
                              required
                            />
                          </div>

                          <div>
                            <Label>Quantity</Label>
                            <Input
                              type="number"
                              step="0.01"
                              min="0"
                              value={item.quantity}
                              onChange={(e) => updateItem(index, 'quantity', e.target.value)}
                              required
                            />
                          </div>

                          <div>
                            <Label>Unit Price (R)</Label>
                            <Input
                              type="number"
                              step="0.01"
                              min="0"
                              value={item.unit_price}
                              onChange={(e) => updateItem(index, 'unit_price', e.target.value)}
                              required
                            />
                          </div>

                          <div>
                            <Label>Line Total</Label>
                            <Input
                              value={`R ${(item.quantity * item.unit_price).toFixed(2)}`}
                              disabled
                              className="bg-gray-50"
                            />
                          </div>

                          {/* Medical Codes */}
                          <div>
                            <Label>ICD-10 Code</Label>
                            <Input
                              placeholder="e.g., Z00.0"
                              value={item.icd10_code}
                              onChange={(e) => updateItem(index, 'icd10_code', e.target.value)}
                            />
                          </div>

                          <div>
                            <Label>NAPPI Code</Label>
                            <Input
                              placeholder="e.g., 111111"
                              value={item.nappi_code}
                              onChange={(e) => updateItem(index, 'nappi_code', e.target.value)}
                            />
                          </div>

                          <div>
                            <Label>Procedure Code</Label>
                            <Input
                              placeholder="Tariff code"
                              value={item.procedure_code}
                              onChange={(e) => updateItem(index, 'procedure_code', e.target.value)}
                            />
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>

                {/* Totals Summary */}
                <Card className="bg-blue-50 border-blue-200">
                  <CardContent className="pt-6">
                    <div className="space-y-2">
                      <div className="flex justify-between text-lg">
                        <span>Subtotal:</span>
                        <span className="font-semibold">R {subtotal.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-lg">
                        <span>VAT (15%):</span>
                        <span className="font-semibold">R {vat.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-2xl font-bold border-t border-blue-300 pt-2">
                        <span>Total:</span>
                        <span className="text-blue-700">R {total.toFixed(2)}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Notes */}
                <div>
                  <Label>Notes</Label>
                  <textarea
                    rows={3}
                    placeholder="Additional notes for this invoice..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    value={invoiceForm.notes}
                    onChange={(e) => setInvoiceForm({...invoiceForm, notes: e.target.value})}
                  />
                </div>

                {/* Submit Button */}
                <div className="flex justify-end">
                  <Button type="submit" disabled={loading} className="bg-blue-600 hover:bg-blue-700">
                    <Receipt className="w-4 h-4 mr-2" />
                    {loading ? 'Creating...' : 'Create Invoice'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Patient Invoices List */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Patient Invoices</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : invoices.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Receipt className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No invoices yet</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {invoices.map((invoice) => (
                    <Card key={invoice.id} className="border border-gray-200">
                      <CardContent className="pt-6">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <h3 className="font-semibold text-lg">{invoice.invoice_number}</h3>
                              <span className={`px-2 py-1 rounded text-xs font-semibold ${getPaymentStatusColor(invoice.payment_status)}`}>
                                {invoice.payment_status.replace('_', ' ').toUpperCase()}
                              </span>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm text-gray-600">
                              <div>Date: {new Date(invoice.invoice_date).toLocaleDateString()}</div>
                              <div>Total: R {parseFloat(invoice.total_amount).toFixed(2)}</div>
                              <div>Paid: R {parseFloat(invoice.amount_paid).toFixed(2)}</div>
                              <div>Outstanding: R {parseFloat(invoice.amount_outstanding).toFixed(2)}</div>
                            </div>
                            {invoice.medical_aid_name && (
                              <div className="text-sm text-gray-600 mt-1">
                                Medical Aid: {invoice.medical_aid_name} ({invoice.medical_aid_number})
                              </div>
                            )}
                          </div>
                          {invoice.payment_status !== 'paid' && (
                            <Button
                              size="sm"
                              onClick={() => setPaymentForm({...paymentForm, invoice_id: invoice.id})}
                              className="ml-4"
                            >
                              <DollarSign className="w-4 h-4 mr-1" />
                              Record Payment
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Record Payment Form */}
          {paymentForm.invoice_id && (
            <Card className="mb-6 border-green-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-green-700">
                  <DollarSign className="w-5 h-5" />
                  Record Payment
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={recordPayment} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Payment Date</Label>
                      <Input
                        type="date"
                        value={paymentForm.payment_date}
                        onChange={(e) => setPaymentForm({...paymentForm, payment_date: e.target.value})}
                        required
                      />
                    </div>
                    <div>
                      <Label>Amount (R)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        value={paymentForm.amount}
                        onChange={(e) => setPaymentForm({...paymentForm, amount: e.target.value})}
                        required
                      />
                    </div>
                    <div>
                      <Label>Payment Method</Label>
                      <select
                        value={paymentForm.payment_method}
                        onChange={(e) => setPaymentForm({...paymentForm, payment_method: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      >
                        <option value="cash">Cash</option>
                        <option value="card">Card</option>
                        <option value="eft">EFT</option>
                        <option value="medical_aid">Medical Aid</option>
                      </select>
                    </div>
                    <div>
                      <Label>Reference Number</Label>
                      <Input
                        placeholder="Transaction ref"
                        value={paymentForm.reference_number}
                        onChange={(e) => setPaymentForm({...paymentForm, reference_number: e.target.value})}
                      />
                    </div>
                  </div>
                  <div>
                    <Label>Notes</Label>
                    <textarea
                      rows={2}
                      placeholder="Payment notes..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      value={paymentForm.notes}
                      onChange={(e) => setPaymentForm({...paymentForm, notes: e.target.value})}
                    />
                  </div>
                  <div className="flex justify-end gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setPaymentForm({...paymentForm, invoice_id: ''})}
                    >
                      Cancel
                    </Button>
                    <Button type="submit" disabled={loading} className="bg-green-600 hover:bg-green-700">
                      {loading ? 'Recording...' : 'Record Payment'}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default BillingTestPage;
