import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  DollarSign, 
  TrendingUp, 
  TrendingDown, 
  FileText, 
  Clock, 
  CheckCircle,
  Download,
  Calendar
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const FinancialDashboard = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState({
    from_date: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0],
    to_date: new Date().toISOString().split('T')[0]
  });

  // Financial data
  const [revenueReport, setRevenueReport] = useState(null);
  const [outstandingReport, setOutstandingReport] = useState(null);
  const [allInvoices, setAllInvoices] = useState([]);

  useEffect(() => {
    loadFinancialData();
  }, [dateRange]);

  const loadFinancialData = async () => {
    setLoading(true);
    try {
      // Load revenue report
      const revenueResponse = await axios.get(
        `${BACKEND_URL}/api/reports/revenue?from_date=${dateRange.from_date}&to_date=${dateRange.to_date}`
      );
      setRevenueReport(revenueResponse.data);

      // Load outstanding invoices
      const outstandingResponse = await axios.get(`${BACKEND_URL}/api/reports/outstanding`);
      setOutstandingReport(outstandingResponse.data);

      // Load all invoices for the period
      const invoicesResponse = await axios.get(
        `${BACKEND_URL}/api/invoices?from_date=${dateRange.from_date}&to_date=${dateRange.to_date}&limit=500`
      );
      setAllInvoices(invoicesResponse.data.invoices || []);

    } catch (error) {
      console.error('Error loading financial data:', error);
      toast({
        title: "Error",
        description: "Failed to load financial data",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const exportToCSV = () => {
    if (!revenueReport) return;

    const csvRows = [];
    csvRows.push(['SurgiScan Financial Report']);
    csvRows.push([`Period: ${dateRange.from_date} to ${dateRange.to_date}`]);
    csvRows.push(['']);
    csvRows.push(['Metric', 'Value']);
    csvRows.push(['Total Invoiced', `R ${revenueReport.total_invoiced.toFixed(2)}`]);
    csvRows.push(['Total Paid', `R ${revenueReport.total_paid.toFixed(2)}`]);
    csvRows.push(['Total Outstanding', `R ${revenueReport.total_outstanding.toFixed(2)}`]);
    csvRows.push(['Number of Invoices', revenueReport.invoice_count]);
    csvRows.push(['Number of Payments', revenueReport.payment_count]);
    csvRows.push(['']);
    csvRows.push(['Payment Methods']);
    
    Object.entries(revenueReport.payment_methods || {}).forEach(([method, amount]) => {
      csvRows.push([method.toUpperCase(), `R ${amount.toFixed(2)}`]);
    });

    const csvContent = csvRows.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `financial-report-${dateRange.from_date}-to-${dateRange.to_date}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);

    toast({
      title: "Success",
      description: "Report exported successfully"
    });
  };

  const formatCurrency = (amount) => {
    return `R ${parseFloat(amount).toFixed(2)}`;
  };

  const getPaymentMethodColor = (method) => {
    const colors = {
      cash: 'bg-green-100 text-green-700',
      card: 'bg-blue-100 text-blue-700',
      eft: 'bg-purple-100 text-purple-700',
      medical_aid: 'bg-orange-100 text-orange-700'
    };
    return colors[method] || 'bg-gray-100 text-gray-700';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Financial Dashboard</h1>
            <p className="text-gray-600">Revenue analytics and financial reports</p>
          </div>
          <Button onClick={exportToCSV} variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export Report
          </Button>
        </div>

        {/* Date Range Filter */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <Label>From Date</Label>
                <Input
                  type="date"
                  value={dateRange.from_date}
                  onChange={(e) => setDateRange({...dateRange, from_date: e.target.value})}
                />
              </div>
              <div className="flex-1">
                <Label>To Date</Label>
                <Input
                  type="date"
                  value={dateRange.to_date}
                  onChange={(e) => setDateRange({...dateRange, to_date: e.target.value})}
                />
              </div>
              <Button onClick={loadFinancialData}>
                <Calendar className="w-4 h-4 mr-2" />
                Apply
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Key Metrics Cards */}
      {revenueReport && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Total Invoiced */}
          <Card className="border-l-4 border-l-blue-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Total Invoiced
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-600">
                {formatCurrency(revenueReport.total_invoiced)}
              </div>
              <p className="text-sm text-gray-500 mt-1">
                {revenueReport.invoice_count} invoices
              </p>
            </CardContent>
          </Card>

          {/* Total Paid */}
          <Card className="border-l-4 border-l-green-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Total Paid
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-600">
                {formatCurrency(revenueReport.total_paid)}
              </div>
              <p className="text-sm text-gray-500 mt-1">
                {revenueReport.payment_count} payments
              </p>
            </CardContent>
          </Card>

          {/* Outstanding */}
          <Card className="border-l-4 border-l-orange-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Outstanding
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-orange-600">
                {formatCurrency(revenueReport.total_outstanding)}
              </div>
              <p className="text-sm text-gray-500 mt-1">
                {outstandingReport?.count || 0} unpaid invoices
              </p>
            </CardContent>
          </Card>

          {/* Collection Rate */}
          <Card className="border-l-4 border-l-purple-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Collection Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-purple-600">
                {revenueReport.total_invoiced > 0 
                  ? ((revenueReport.total_paid / revenueReport.total_invoiced) * 100).toFixed(1)
                  : 0}%
              </div>
              <p className="text-sm text-gray-500 mt-1">
                of total invoiced
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Payment Methods Breakdown */}
        {revenueReport && revenueReport.payment_methods && (
          <Card>
            <CardHeader>
              <CardTitle>Payment Methods Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(revenueReport.payment_methods).map(([method, amount]) => {
                  const percentage = revenueReport.total_paid > 0 
                    ? (amount / revenueReport.total_paid) * 100 
                    : 0;
                  
                  return (
                    <div key={method}>
                      <div className="flex items-center justify-between mb-2">
                        <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getPaymentMethodColor(method)}`}>
                          {method.toUpperCase().replace('_', ' ')}
                        </span>
                        <span className="font-semibold">{formatCurrency(amount)}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all"
                          style={{ width: `${percentage}%` }}
                        ></div>
                      </div>
                      <div className="text-right text-sm text-gray-500 mt-1">
                        {percentage.toFixed(1)}%
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Invoice Status Distribution */}
        {allInvoices.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Invoice Status Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {['paid', 'partially_paid', 'unpaid', 'overdue'].map((status) => {
                  const statusInvoices = allInvoices.filter(inv => inv.payment_status === status);
                  const count = statusInvoices.length;
                  const amount = statusInvoices.reduce((sum, inv) => sum + parseFloat(inv.total_amount), 0);
                  const percentage = allInvoices.length > 0 ? (count / allInvoices.length) * 100 : 0;

                  const colors = {
                    paid: 'bg-green-500',
                    partially_paid: 'bg-yellow-500',
                    unpaid: 'bg-orange-500',
                    overdue: 'bg-red-500'
                  };

                  return (
                    <div key={status}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium capitalize">{status.replace('_', ' ')}</span>
                        <div className="text-right">
                          <div className="font-semibold">{formatCurrency(amount)}</div>
                          <div className="text-sm text-gray-500">{count} invoices</div>
                        </div>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`${colors[status]} h-2 rounded-full transition-all`}
                          style={{ width: `${percentage}%` }}
                        ></div>
                      </div>
                      <div className="text-right text-sm text-gray-500 mt-1">
                        {percentage.toFixed(1)}%
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Outstanding Invoices Table */}
      {outstandingReport && outstandingReport.invoices && outstandingReport.invoices.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Outstanding Invoices</span>
              <span className="text-lg font-bold text-orange-600">
                Total: {formatCurrency(outstandingReport.total_outstanding)}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-3 font-semibold">Invoice #</th>
                    <th className="text-left p-3 font-semibold">Date</th>
                    <th className="text-left p-3 font-semibold">Patient</th>
                    <th className="text-center p-3 font-semibold">Status</th>
                    <th className="text-right p-3 font-semibold">Total</th>
                    <th className="text-right p-3 font-semibold">Paid</th>
                    <th className="text-right p-3 font-semibold">Outstanding</th>
                    <th className="text-center p-3 font-semibold">Days Overdue</th>
                  </tr>
                </thead>
                <tbody>
                  {outstandingReport.invoices.map((invoice) => {
                    const invoiceDate = new Date(invoice.invoice_date);
                    const dueDate = invoice.due_date ? new Date(invoice.due_date) : null;
                    const today = new Date();
                    const daysOverdue = dueDate && today > dueDate 
                      ? Math.floor((today - dueDate) / (1000 * 60 * 60 * 24))
                      : 0;

                    return (
                      <tr key={invoice.id} className="border-b hover:bg-gray-50">
                        <td className="p-3">
                          <span className="font-medium text-blue-600">{invoice.invoice_number}</span>
                        </td>
                        <td className="p-3 text-sm">{invoiceDate.toLocaleDateString()}</td>
                        <td className="p-3 text-sm">{invoice.patient_id.slice(0, 8)}</td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                            invoice.payment_status === 'partially_paid'
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-red-100 text-red-700'
                          }`}>
                            {invoice.payment_status.replace('_', ' ').toUpperCase()}
                          </span>
                        </td>
                        <td className="p-3 text-right">{formatCurrency(invoice.total_amount)}</td>
                        <td className="p-3 text-right text-green-600">{formatCurrency(invoice.amount_paid)}</td>
                        <td className="p-3 text-right font-semibold text-orange-600">
                          {formatCurrency(invoice.amount_outstanding)}
                        </td>
                        <td className="p-3 text-center">
                          {daysOverdue > 0 ? (
                            <span className="text-red-600 font-semibold">{daysOverdue} days</span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Period Summary */}
      {revenueReport && (
        <Card className="mt-6 bg-gradient-to-r from-blue-50 to-purple-50">
          <CardContent className="pt-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-sm text-gray-600 mb-1">Invoices Issued</div>
                <div className="text-2xl font-bold text-blue-600">{revenueReport.invoice_count}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Payments Received</div>
                <div className="text-2xl font-bold text-green-600">{revenueReport.payment_count}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Avg Invoice Value</div>
                <div className="text-2xl font-bold text-purple-600">
                  {revenueReport.invoice_count > 0 
                    ? formatCurrency(revenueReport.total_invoiced / revenueReport.invoice_count)
                    : formatCurrency(0)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Avg Payment</div>
                <div className="text-2xl font-bold text-orange-600">
                  {revenueReport.payment_count > 0 
                    ? formatCurrency(revenueReport.total_paid / revenueReport.payment_count)
                    : formatCurrency(0)}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default FinancialDashboard;
