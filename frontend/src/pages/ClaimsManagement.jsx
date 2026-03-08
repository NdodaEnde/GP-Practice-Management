import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { 
  FileText, 
  Send, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Download,
  AlertCircle,
  TrendingUp,
  DollarSign,
  Filter
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const ClaimsManagement = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [claims, setClaims] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [filters, setFilters] = useState({
    status: '',
    medical_aid: ''
  });

  // Create claim dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [claimForm, setClaimForm] = useState({
    medical_aid_name: '',
    medical_aid_number: '',
    medical_aid_plan: '',
    primary_diagnosis_code: '',
    primary_diagnosis_description: '',
    secondary_diagnosis_codes: '',
    notes: ''
  });

  // Update claim status dialog
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [statusUpdate, setStatusUpdate] = useState({
    status: '',
    approved_amount: '',
    paid_amount: '',
    rejection_reason: '',
    rejection_code: ''
  });

  useEffect(() => {
    loadClaims();
    loadInvoices();
  }, [filters]);

  const loadClaims = async () => {
    setLoading(true);
    try {
      let url = `${BACKEND_URL}/api/claims?limit=200`;
      if (filters.status) url += `&status=${filters.status}`;
      if (filters.medical_aid) url += `&medical_aid=${encodeURIComponent(filters.medical_aid)}`;

      const response = await axios.get(url);
      setClaims(response.data.claims || []);
    } catch (error) {
      console.error('Error loading claims:', error);
      toast({
        title: "Error",
        description: "Failed to load claims",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const loadInvoices = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/invoices?limit=100`);
      setInvoices(response.data.invoices || []);
    } catch (error) {
      console.error('Error loading invoices:', error);
    }
  };

  const handleCreateClaim = async (e) => {
    e.preventDefault();
    
    try {
      const claimData = {
        invoice_id: selectedInvoice.id,
        medical_aid_name: claimForm.medical_aid_name,
        medical_aid_number: claimForm.medical_aid_number,
        medical_aid_plan: claimForm.medical_aid_plan || null,
        claim_amount: parseFloat(selectedInvoice.total_amount),
        primary_diagnosis_code: claimForm.primary_diagnosis_code,
        primary_diagnosis_description: claimForm.primary_diagnosis_description,
        secondary_diagnosis_codes: claimForm.secondary_diagnosis_codes 
          ? claimForm.secondary_diagnosis_codes.split(',').map(c => c.trim())
          : null,
        notes: claimForm.notes || null
      };

      await axios.post(`${BACKEND_URL}/api/claims`, claimData);

      toast({
        title: "Success",
        description: "Claim created successfully"
      });

      setCreateDialogOpen(false);
      setSelectedInvoice(null);
      setClaimForm({
        medical_aid_name: '',
        medical_aid_number: '',
        medical_aid_plan: '',
        primary_diagnosis_code: '',
        primary_diagnosis_description: '',
        secondary_diagnosis_codes: '',
        notes: ''
      });
      loadClaims();
    } catch (error) {
      console.error('Error creating claim:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to create claim",
        variant: "destructive"
      });
    }
  };

  const handleUpdateClaimStatus = async (e) => {
    e.preventDefault();
    
    if (!selectedClaim) return;

    try {
      let url = `${BACKEND_URL}/api/claims/${selectedClaim.id}/status?status=${statusUpdate.status}`;
      
      if (statusUpdate.approved_amount) {
        url += `&approved_amount=${statusUpdate.approved_amount}`;
      }
      if (statusUpdate.paid_amount) {
        url += `&paid_amount=${statusUpdate.paid_amount}`;
      }
      if (statusUpdate.rejection_reason) {
        url += `&rejection_reason=${encodeURIComponent(statusUpdate.rejection_reason)}`;
      }
      if (statusUpdate.rejection_code) {
        url += `&rejection_code=${encodeURIComponent(statusUpdate.rejection_code)}`;
      }

      await axios.patch(url);

      toast({
        title: "Success",
        description: "Claim status updated successfully"
      });

      setStatusDialogOpen(false);
      setSelectedClaim(null);
      setStatusUpdate({
        status: '',
        approved_amount: '',
        paid_amount: '',
        rejection_reason: '',
        rejection_code: ''
      });
      loadClaims();
    } catch (error) {
      console.error('Error updating claim status:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to update claim status",
        variant: "destructive"
      });
    }
  };

  const exportClaimToCSV = (claim) => {
    const csvRows = [];
    csvRows.push(['Medical Aid Claim Submission']);
    csvRows.push(['']);
    csvRows.push(['Claim Information']);
    csvRows.push(['Claim Number', claim.claim_number]);
    csvRows.push(['Claim Date', claim.claim_date]);
    csvRows.push(['Invoice Number', claim.invoice_id]);
    csvRows.push(['']);
    csvRows.push(['Medical Aid Details']);
    csvRows.push(['Medical Aid Name', claim.medical_aid_name]);
    csvRows.push(['Member Number', claim.medical_aid_number]);
    csvRows.push(['Plan', claim.medical_aid_plan || 'N/A']);
    csvRows.push(['']);
    csvRows.push(['Diagnosis Information']);
    csvRows.push(['Primary ICD-10 Code', claim.primary_diagnosis_code]);
    csvRows.push(['Primary Diagnosis', claim.primary_diagnosis_description]);
    if (claim.secondary_diagnosis_codes && claim.secondary_diagnosis_codes.length > 0) {
      csvRows.push(['Secondary Codes', claim.secondary_diagnosis_codes.join(', ')]);
    }
    csvRows.push(['']);
    csvRows.push(['Financial']);
    csvRows.push(['Claim Amount', `R ${parseFloat(claim.claim_amount).toFixed(2)}`]);
    csvRows.push(['Status', claim.status]);

    const csvContent = csvRows.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `claim-${claim.claim_number}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);

    toast({
      title: "Success",
      description: "Claim exported successfully"
    });
  };

  const exportAllClaimsToCSV = () => {
    const csvRows = [];
    csvRows.push(['Claim Number', 'Date', 'Medical Aid', 'Member No', 'ICD-10', 'Amount', 'Status']);
    
    claims.forEach(claim => {
      csvRows.push([
        claim.claim_number,
        claim.claim_date,
        claim.medical_aid_name,
        claim.medical_aid_number,
        claim.primary_diagnosis_code,
        parseFloat(claim.claim_amount).toFixed(2),
        claim.status
      ]);
    });

    const csvContent = csvRows.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `all-claims-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);

    toast({
      title: "Success",
      description: "Claims exported successfully"
    });
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'approved':
      case 'paid':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'rejected':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'submitted':
        return <Send className="w-5 h-5 text-blue-500" />;
      case 'partially_approved':
        return <AlertCircle className="w-5 h-5 text-yellow-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'approved':
      case 'paid':
        return 'bg-green-100 text-green-700';
      case 'rejected':
        return 'bg-red-100 text-red-700';
      case 'submitted':
        return 'bg-blue-100 text-blue-700';
      case 'partially_approved':
        return 'bg-yellow-100 text-yellow-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  // Calculate statistics
  const stats = {
    total: claims.length,
    draft: claims.filter(c => c.status === 'draft').length,
    submitted: claims.filter(c => c.status === 'submitted').length,
    approved: claims.filter(c => c.status === 'approved' || c.status === 'paid').length,
    rejected: claims.filter(c => c.status === 'rejected').length,
    totalAmount: claims.reduce((sum, c) => sum + parseFloat(c.claim_amount), 0),
    approvedAmount: claims.filter(c => c.approved_amount).reduce((sum, c) => sum + parseFloat(c.approved_amount), 0)
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Claims Management</h1>
            <p className="text-gray-600">Submit and track medical aid claims</p>
          </div>
          <div className="flex gap-3">
            <Button onClick={exportAllClaimsToCSV} variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export All
            </Button>
            <Button onClick={() => setCreateDialogOpen(true)} className="bg-blue-600 hover:bg-blue-700">
              <FileText className="w-4 h-4 mr-2" />
              Create Claim
            </Button>
          </div>
        </div>

        {/* Statistics Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Total Claims</p>
                  <p className="text-2xl font-bold">{stats.total}</p>
                </div>
                <FileText className="w-8 h-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Submitted</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.submitted}</p>
                </div>
                <Send className="w-8 h-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Approved</p>
                  <p className="text-2xl font-bold text-green-600">{stats.approved}</p>
                </div>
                <CheckCircle className="w-8 h-8 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Rejected</p>
                  <p className="text-2xl font-bold text-red-600">{stats.rejected}</p>
                </div>
                <XCircle className="w-8 h-8 text-red-500" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <Label>Filter by Status</Label>
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({...filters, status: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">All Statuses</option>
                  <option value="draft">Draft</option>
                  <option value="submitted">Submitted</option>
                  <option value="approved">Approved</option>
                  <option value="partially_approved">Partially Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="paid">Paid</option>
                </select>
              </div>
              <div className="flex-1">
                <Label>Filter by Medical Aid</Label>
                <Input
                  placeholder="e.g., Discovery Health"
                  value={filters.medical_aid}
                  onChange={(e) => setFilters({...filters, medical_aid: e.target.value})}
                />
              </div>
              <Button onClick={loadClaims}>
                <Filter className="w-4 h-4 mr-2" />
                Apply
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Claims List */}
      <Card>
        <CardHeader>
          <CardTitle>Claims List</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : claims.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg">No claims found</p>
              <Button onClick={() => setCreateDialogOpen(true)} className="mt-4">
                Create Your First Claim
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {claims.map((claim) => (
                <div
                  key={claim.id}
                  className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        {getStatusIcon(claim.status)}
                        <h3 className="font-semibold text-lg">{claim.claim_number}</h3>
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(claim.status)}`}>
                          {claim.status.replace('_', ' ').toUpperCase()}
                        </span>
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-gray-600">Medical Aid:</span>
                          <p className="font-medium">{claim.medical_aid_name}</p>
                        </div>
                        <div>
                          <span className="text-gray-600">Member No:</span>
                          <p className="font-medium">{claim.medical_aid_number}</p>
                        </div>
                        <div>
                          <span className="text-gray-600">ICD-10:</span>
                          <p className="font-medium">{claim.primary_diagnosis_code}</p>
                        </div>
                        <div>
                          <span className="text-gray-600">Claim Amount:</span>
                          <p className="font-medium text-blue-600">R {parseFloat(claim.claim_amount).toFixed(2)}</p>
                        </div>
                        <div>
                          <span className="text-gray-600">Claim Date:</span>
                          <p className="font-medium">{new Date(claim.claim_date).toLocaleDateString()}</p>
                        </div>
                        {claim.submission_date && (
                          <div>
                            <span className="text-gray-600">Submitted:</span>
                            <p className="font-medium">{new Date(claim.submission_date).toLocaleDateString()}</p>
                          </div>
                        )}
                        {claim.approved_amount && (
                          <div>
                            <span className="text-gray-600">Approved Amount:</span>
                            <p className="font-medium text-green-600">R {parseFloat(claim.approved_amount).toFixed(2)}</p>
                          </div>
                        )}
                        {claim.rejection_reason && (
                          <div className="col-span-2">
                            <span className="text-gray-600">Rejection Reason:</span>
                            <p className="font-medium text-red-600">{claim.rejection_reason}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-2 ml-4">
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => exportClaimToCSV(claim)}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                      <Button 
                        size="sm" 
                        onClick={() => {
                          setSelectedClaim(claim);
                          setStatusUpdate({
                            status: '',
                            approved_amount: '',
                            paid_amount: '',
                            rejection_reason: '',
                            rejection_code: ''
                          });
                          setStatusDialogOpen(true);
                        }}
                      >
                        Update Status
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Claim Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Medical Aid Claim</DialogTitle>
          </DialogHeader>
          
          <form onSubmit={handleCreateClaim} className="space-y-4">
            {/* Select Invoice */}
            <div>
              <Label>Select Invoice *</Label>
              <select
                required
                value={selectedInvoice?.id || ''}
                onChange={(e) => {
                  const invoice = invoices.find(inv => inv.id === e.target.value);
                  setSelectedInvoice(invoice);
                  if (invoice) {
                    setClaimForm({
                      ...claimForm,
                      medical_aid_name: invoice.medical_aid_name || '',
                      medical_aid_number: invoice.medical_aid_number || '',
                      medical_aid_plan: invoice.medical_aid_plan || ''
                    });
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="">-- Select an invoice --</option>
                {invoices.filter(inv => inv.medical_aid_name).map((invoice) => (
                  <option key={invoice.id} value={invoice.id}>
                    {invoice.invoice_number} - R {parseFloat(invoice.total_amount).toFixed(2)} - {invoice.medical_aid_name}
                  </option>
                ))}
              </select>
            </div>

            {selectedInvoice && (
              <>
                {/* Medical Aid Details */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Medical Aid Name *</Label>
                    <Input
                      required
                      value={claimForm.medical_aid_name}
                      onChange={(e) => setClaimForm({...claimForm, medical_aid_name: e.target.value})}
                      placeholder="e.g., Discovery Health"
                    />
                  </div>
                  <div>
                    <Label>Member Number *</Label>
                    <Input
                      required
                      value={claimForm.medical_aid_number}
                      onChange={(e) => setClaimForm({...claimForm, medical_aid_number: e.target.value})}
                      placeholder="Member number"
                    />
                  </div>
                  <div className="col-span-2">
                    <Label>Plan</Label>
                    <Input
                      value={claimForm.medical_aid_plan}
                      onChange={(e) => setClaimForm({...claimForm, medical_aid_plan: e.target.value})}
                      placeholder="e.g., Executive Plan"
                    />
                  </div>
                </div>

                {/* Diagnosis Information */}
                <div>
                  <Label>Primary ICD-10 Diagnosis Code *</Label>
                  <Input
                    required
                    value={claimForm.primary_diagnosis_code}
                    onChange={(e) => setClaimForm({...claimForm, primary_diagnosis_code: e.target.value})}
                    placeholder="e.g., Z00.0"
                  />
                </div>
                <div>
                  <Label>Primary Diagnosis Description *</Label>
                  <Input
                    required
                    value={claimForm.primary_diagnosis_description}
                    onChange={(e) => setClaimForm({...claimForm, primary_diagnosis_description: e.target.value})}
                    placeholder="e.g., General medical examination"
                  />
                </div>
                <div>
                  <Label>Secondary ICD-10 Codes (comma-separated)</Label>
                  <Input
                    value={claimForm.secondary_diagnosis_codes}
                    onChange={(e) => setClaimForm({...claimForm, secondary_diagnosis_codes: e.target.value})}
                    placeholder="e.g., I10, E11.9"
                  />
                </div>

                {/* Claim Amount (read-only) */}
                <div>
                  <Label>Claim Amount</Label>
                  <Input
                    value={`R ${parseFloat(selectedInvoice.total_amount).toFixed(2)}`}
                    disabled
                    className="bg-gray-50"
                  />
                </div>

                {/* Notes */}
                <div>
                  <Label>Notes</Label>
                  <Textarea
                    rows={3}
                    value={claimForm.notes}
                    onChange={(e) => setClaimForm({...claimForm, notes: e.target.value})}
                    placeholder="Additional claim notes..."
                  />
                </div>

                {/* Submit */}
                <div className="flex justify-end gap-3 pt-4">
                  <Button type="button" variant="outline" onClick={() => setCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" className="bg-blue-600 hover:bg-blue-700">
                    Create Claim
                  </Button>
                </div>
              </>
            )}
          </form>
        </DialogContent>
      </Dialog>

      {/* Update Status Dialog */}
      <Dialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Claim Status</DialogTitle>
          </DialogHeader>
          
          {selectedClaim && (
            <form onSubmit={handleUpdateClaimStatus} className="space-y-4">
              <div className="bg-gray-50 p-3 rounded">
                <p className="text-sm text-gray-600">Claim Number</p>
                <p className="font-semibold">{selectedClaim.claim_number}</p>
              </div>

              <div>
                <Label>New Status *</Label>
                <select
                  required
                  value={statusUpdate.status}
                  onChange={(e) => setStatusUpdate({...statusUpdate, status: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">-- Select status --</option>
                  <option value="submitted">Submitted</option>
                  <option value="approved">Approved</option>
                  <option value="partially_approved">Partially Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="paid">Paid</option>
                </select>
              </div>

              {(statusUpdate.status === 'approved' || statusUpdate.status === 'partially_approved') && (
                <div>
                  <Label>Approved Amount</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={statusUpdate.approved_amount}
                    onChange={(e) => setStatusUpdate({...statusUpdate, approved_amount: e.target.value})}
                    placeholder="Approved amount"
                  />
                </div>
              )}

              {statusUpdate.status === 'paid' && (
                <div>
                  <Label>Paid Amount</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={statusUpdate.paid_amount}
                    onChange={(e) => setStatusUpdate({...statusUpdate, paid_amount: e.target.value})}
                    placeholder="Paid amount"
                  />
                </div>
              )}

              {statusUpdate.status === 'rejected' && (
                <>
                  <div>
                    <Label>Rejection Code</Label>
                    <Input
                      value={statusUpdate.rejection_code}
                      onChange={(e) => setStatusUpdate({...statusUpdate, rejection_code: e.target.value})}
                      placeholder="e.g., INV001"
                    />
                  </div>
                  <div>
                    <Label>Rejection Reason</Label>
                    <Textarea
                      rows={3}
                      value={statusUpdate.rejection_reason}
                      onChange={(e) => setStatusUpdate({...statusUpdate, rejection_reason: e.target.value})}
                      placeholder="Reason for rejection..."
                    />
                  </div>
                </>
              )}

              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setStatusDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" className="bg-blue-600 hover:bg-blue-700">
                  Update Status
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ClaimsManagement;
