import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { DollarSign, Plus, FileText, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { invoiceAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';
import InvoiceView from '@/components/InvoiceView';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const Billing = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [invoiceViewOpen, setInvoiceViewOpen] = useState(false);

  const encounterId = searchParams.get('encounter');

  const [invoiceData, setInvoiceData] = useState({
    encounter_id: encounterId || '',
    payer_type: 'cash',
    items: [{ description: 'Consultation', quantity: 1, unit_price: 500, total: 500 }],
    total_amount: 500,
    notes: ''
  });

  useEffect(() => {
    loadInvoices();
    if (encounterId) {
      setDialogOpen(true);
    }
  }, []);

  const loadInvoices = async () => {
    try {
      setLoading(true);
      const response = await invoiceAPI.list();
      // Handle new API structure that returns {count, invoices}
      const invoicesList = response.data?.invoices || response.data || [];
      setInvoices(Array.isArray(invoicesList) ? invoicesList : []);
    } catch (error) {
      console.error('Error loading invoices:', error);
      // Initialize as empty array to prevent map error
      setInvoices([]);
      toast({
        title: 'Error',
        description: 'Failed to load invoices',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleViewInvoice = async (invoiceId) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/invoices/${invoiceId}`);
      setSelectedInvoice(response.data);
      setInvoiceViewOpen(true);
    } catch (error) {
      console.error('Error loading invoice details:', error);
      toast({
        title: 'Error',
        description: 'Failed to load invoice details',
        variant: 'destructive'
      });
    }
  };

  const addInvoiceItem = () => {
    setInvoiceData(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0, total: 0 }]
    }));
  };

  const updateInvoiceItem = (index, field, value) => {
    const newItems = [...invoiceData.items];
    newItems[index][field] = value;
    
    // Calculate total for this item
    if (field === 'quantity' || field === 'unit_price') {
      newItems[index].total = newItems[index].quantity * newItems[index].unit_price;
    }
    
    // Calculate total amount
    const totalAmount = newItems.reduce((sum, item) => sum + item.total, 0);
    
    setInvoiceData(prev => ({
      ...prev,
      items: newItems,
      total_amount: totalAmount
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await invoiceAPI.create(invoiceData);
      toast({
        title: 'Success',
        description: 'Invoice created successfully'
      });
      setDialogOpen(false);
      loadInvoices();
      
      // Reset form
      setInvoiceData({
        encounter_id: '',
        payer_type: 'cash',
        items: [{ description: 'Consultation', quantity: 1, unit_price: 500, total: 500 }],
        total_amount: 500,
        notes: ''
      });
    } catch (error) {
      console.error('Error creating invoice:', error);
      toast({
        title: 'Error',
        description: 'Failed to create invoice',
        variant: 'destructive'
      });
    }
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="billing-container">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-slate-800 mb-2">Billing & Invoices</h1>
          <p className="text-slate-600">Manage patient billing and invoices</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button 
              className="bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
              data-testid="create-invoice-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Invoice
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-2xl font-bold text-slate-800">Create New Invoice</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Encounter ID</Label>
                  <Input
                    value={invoiceData.encounter_id}
                    onChange={(e) => setInvoiceData({...invoiceData, encounter_id: e.target.value})}
                    required
                    data-testid="invoice-encounter-id"
                  />
                </div>
                <div>
                  <Label>Payer Type</Label>
                  <Select
                    value={invoiceData.payer_type}
                    onValueChange={(value) => setInvoiceData({...invoiceData, payer_type: value})}
                  >
                    <SelectTrigger data-testid="invoice-payer-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">Cash</SelectItem>
                      <SelectItem value="medical_aid">Medical Aid</SelectItem>
                      <SelectItem value="corporate">Corporate</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Invoice Items</Label>
                  <Button type="button" size="sm" variant="outline" onClick={addInvoiceItem}>
                    <Plus className="w-3 h-3 mr-1" /> Add Item
                  </Button>
                </div>
                {invoiceData.items.map((item, index) => (
                  <div key={index} className="grid grid-cols-12 gap-2 p-3 bg-slate-50 rounded-lg">
                    <div className="col-span-5">
                      <Input
                        placeholder="Description"
                        value={item.description}
                        onChange={(e) => updateInvoiceItem(index, 'description', e.target.value)}
                        data-testid={`item-description-${index}`}
                      />
                    </div>
                    <div className="col-span-2">
                      <Input
                        type="number"
                        placeholder="Qty"
                        value={item.quantity}
                        onChange={(e) => updateInvoiceItem(index, 'quantity', parseFloat(e.target.value))}
                        data-testid={`item-quantity-${index}`}
                      />
                    </div>
                    <div className="col-span-2">
                      <Input
                        type="number"
                        placeholder="Price"
                        value={item.unit_price}
                        onChange={(e) => updateInvoiceItem(index, 'unit_price', parseFloat(e.target.value))}
                        data-testid={`item-price-${index}`}
                      />
                    </div>
                    <div className="col-span-3">
                      <Input
                        value={`R${item.total.toFixed(2)}`}
                        disabled
                        className="bg-white"
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-4 bg-gradient-to-r from-violet-50 to-purple-50 rounded-lg">
                <div className="flex justify-between items-center">
                  <span className="text-lg font-semibold text-slate-800">Total Amount</span>
                  <span className="text-2xl font-bold text-violet-600">R{invoiceData.total_amount.toFixed(2)}</span>
                </div>
              </div>

              <div>
                <Label>Notes</Label>
                <Input
                  value={invoiceData.notes}
                  onChange={(e) => setInvoiceData({...invoiceData, notes: e.target.value})}
                  placeholder="Additional notes..."
                  data-testid="invoice-notes"
                />
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button 
                  type="submit"
                  className="bg-gradient-to-r from-violet-500 to-purple-600 text-white"
                  data-testid="submit-invoice-btn"
                >
                  Create Invoice
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Invoices List */}
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-xl font-bold text-slate-800">Recent Invoices</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : invoices.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 text-lg">No invoices yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {invoices.map((invoice) => (
                <div
                  key={invoice.id}
                  onClick={() => handleViewInvoice(invoice.id)}
                  className="p-5 bg-gradient-to-r from-slate-50 to-violet-50 rounded-lg border border-slate-200 hover:shadow-md hover:border-violet-300 transition-all duration-200 cursor-pointer"
                  data-testid={`invoice-card-${invoice.id}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center text-white">
                        <DollarSign className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-slate-800">
                          {invoice.invoice_number || `Invoice #${invoice.id.slice(0, 8)}`}
                        </h3>
                        <p className="text-sm text-slate-600">
                          {new Date(invoice.invoice_date || invoice.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-bold text-violet-600">R{parseFloat(invoice.total_amount).toFixed(2)}</p>
                      <span className={`inline-block px-3 py-1 text-xs font-medium rounded-full mt-1 ${
                        invoice.payment_status === 'paid'
                          ? 'bg-emerald-100 text-emerald-700'
                          : invoice.payment_status === 'partially_paid'
                          ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}>
                        {invoice.payment_status ? invoice.payment_status.replace('_', ' ').toUpperCase() : invoice.status}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Billing;