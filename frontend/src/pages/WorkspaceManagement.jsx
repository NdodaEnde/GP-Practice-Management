import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import {
  Building2,
  Plus,
  Search,
  Users,
  FileText,
  HardDrive,
  Edit,
  Trash2,
  Mail,
  Phone,
  MapPin,
  Calendar,
  TrendingUp,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react';

const WorkspaceManagement = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  
  const [workspaces, setWorkspaces] = useState([]);
  const [filteredWorkspaces, setFilteredWorkspaces] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Create workspace modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newWorkspace, setNewWorkspace] = useState({
    name: '',
    organization_name: '',
    organization_type: 'gp_practice',
    contact_email: '',
    contact_phone: '',
    contact_person: '',
    address_line1: '',
    city: '',
    province: '',
    postal_code: '',
    subscription_tier: 'free'
  });

  // Stats
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    trial: 0,
    free: 0,
    professional: 0,
    enterprise: 0
  });

  // Check admin access
  useEffect(() => {
    if (user && user.role !== 'admin') {
      toast({
        title: "Access Denied",
        description: "You don't have permission to access workspace management",
        variant: "destructive"
      });
      navigate('/digitization');
    }
  }, [user, navigate]);

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  useEffect(() => {
    filterWorkspaces();
  }, [searchQuery, workspaces]);

  useEffect(() => {
    calculateStats();
  }, [filteredWorkspaces]);

  const fetchWorkspaces = async () => {
    try {
      setIsLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const response = await axios.get(`${backendUrl}/api/workspaces/`);
      
      setWorkspaces(response.data);
      
      toast({
        title: "Workspaces Loaded",
        description: `Found ${response.data.length} workspaces`,
      });
    } catch (error) {
      console.error('Error fetching workspaces:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to load workspaces",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const filterWorkspaces = () => {
    let filtered = workspaces;

    if (searchQuery) {
      filtered = filtered.filter(ws =>
        ws.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ws.organization_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ws.contact_email.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredWorkspaces(filtered);
  };

  const calculateStats = () => {
    const newStats = {
      total: filteredWorkspaces.length,
      active: filteredWorkspaces.filter(ws => ws.is_active).length,
      trial: filteredWorkspaces.filter(ws => ws.is_trial).length,
      free: filteredWorkspaces.filter(ws => ws.subscription_tier === 'free').length,
      professional: filteredWorkspaces.filter(ws => ws.subscription_tier === 'professional').length,
      enterprise: filteredWorkspaces.filter(ws => ws.subscription_tier === 'enterprise').length
    };
    setStats(newStats);
  };

  const handleCreateWorkspace = async (e) => {
    e.preventDefault();
    
    // Validation
    if (!newWorkspace.name || !newWorkspace.organization_name || !newWorkspace.contact_email || !newWorkspace.contact_person) {
      toast({
        title: "Validation Error",
        description: "Please fill in all required fields",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsCreating(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const response = await axios.post(`${backendUrl}/api/workspaces/`, newWorkspace);
      
      toast({
        title: "Workspace Created",
        description: `${newWorkspace.name} has been created successfully`,
      });
      
      // Reset form and close modal
      setNewWorkspace({
        name: '',
        organization_name: '',
        organization_type: 'gp_practice',
        contact_email: '',
        contact_phone: '',
        contact_person: '',
        address_line1: '',
        city: '',
        province: '',
        postal_code: '',
        subscription_tier: 'free'
      });
      setShowCreateModal(false);
      
      // Refresh workspaces list
      fetchWorkspaces();
    } catch (error) {
      console.error('Error creating workspace:', error);
      toast({
        title: "Creation Failed",
        description: error.response?.data?.detail || "Failed to create workspace",
        variant: "destructive"
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteWorkspace = async (workspaceId, workspaceName) => {
    if (!window.confirm(`Are you sure you want to deactivate ${workspaceName}?`)) {
      return;
    }

    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      await axios.delete(`${backendUrl}/api/workspaces/${workspaceId}`);
      
      toast({
        title: "Workspace Deactivated",
        description: `${workspaceName} has been deactivated`,
      });
      
      fetchWorkspaces();
    } catch (error) {
      console.error('Error deleting workspace:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to deactivate workspace",
        variant: "destructive"
      });
    }
  };

  const getSubscriptionColor = (tier) => {
    const colors = {
      'free': 'bg-gray-100 text-gray-800',
      'basic': 'bg-blue-100 text-blue-800',
      'professional': 'bg-purple-100 text-purple-800',
      'enterprise': 'bg-orange-100 text-orange-800'
    };
    return colors[tier] || 'bg-gray-100 text-gray-800';
  };

  const getOrgTypeLabel = (type) => {
    const labels = {
      'gp_practice': 'GP Practice',
      'occupational_health': 'Occupational Health',
      'hospital': 'Hospital',
      'clinic': 'Clinic'
    };
    return labels[type] || type;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-ZA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Workspace Management</h1>
              <p className="text-gray-600">Manage client organizations and their subscriptions</p>
            </div>
            
            <Button
              onClick={() => setShowCreateModal(true)}
              className="gap-2 bg-teal-600 hover:bg-teal-700"
            >
              <Plus className="w-4 h-4" />
              Create Workspace
            </Button>
          </div>

          {/* Statistics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
                  <p className="text-sm text-gray-600">Total</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">{stats.active}</p>
                  <p className="text-sm text-gray-600">Active</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-600">{stats.trial}</p>
                  <p className="text-sm text-gray-600">Trial</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-600">{stats.free}</p>
                  <p className="text-sm text-gray-600">Free</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-purple-600">{stats.professional}</p>
                  <p className="text-sm text-gray-600">Professional</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-orange-600">{stats.enterprise}</p>
                  <p className="text-sm text-gray-600">Enterprise</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Search */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <Input
                placeholder="Search workspaces by name, organization, or email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </CardContent>
        </Card>

        {/* Workspaces List */}
        {isLoading ? (
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
              </div>
            </CardContent>
          </Card>
        ) : filteredWorkspaces.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <Building2 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-700 mb-2">No Workspaces Found</h3>
                <p className="text-gray-600 mb-4">
                  {searchQuery
                    ? 'Try adjusting your search'
                    : 'Create your first workspace to get started'}
                </p>
                <Button
                  onClick={() => setShowCreateModal(true)}
                  className="gap-2 bg-teal-600 hover:bg-teal-700"
                >
                  <Plus className="w-4 h-4" />
                  Create First Workspace
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {filteredWorkspaces.map((ws) => (
              <Card key={ws.id} className="hover:shadow-lg transition-shadow">
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 flex-1 min-w-0">
                      <div className="w-16 h-16 bg-gradient-to-br from-teal-500 to-cyan-600 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Building2 className="w-8 h-8 text-white" />
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <h3 className="text-xl font-bold text-gray-900">{ws.name}</h3>
                          <Badge className={getSubscriptionColor(ws.subscription_tier)}>
                            {ws.subscription_tier}
                          </Badge>
                          {ws.is_active ? (
                            <Badge className="bg-green-100 text-green-800">
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Active
                            </Badge>
                          ) : (
                            <Badge className="bg-red-100 text-red-800">
                              <XCircle className="w-3 h-3 mr-1" />
                              Inactive
                            </Badge>
                          )}
                          {ws.is_trial && (
                            <Badge className="bg-amber-100 text-amber-800">
                              Trial
                            </Badge>
                          )}
                        </div>
                        
                        <p className="text-gray-700 font-medium mb-3">
                          {ws.organization_name} • {getOrgTypeLabel(ws.organization_type)}
                        </p>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-gray-600 mb-3">
                          <div className="flex items-center gap-2">
                            <Mail className="w-4 h-4 text-gray-400" />
                            {ws.contact_email}
                          </div>
                          {ws.contact_phone && (
                            <div className="flex items-center gap-2">
                              <Phone className="w-4 h-4 text-gray-400" />
                              {ws.contact_phone}
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            <Users className="w-4 h-4 text-gray-400" />
                            {ws.user_count || 0} / {ws.max_users} users
                          </div>
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-gray-400" />
                            0 / {ws.max_documents} documents
                          </div>
                          <div className="flex items-center gap-2">
                            <HardDrive className="w-4 h-4 text-gray-400" />
                            {ws.storage_quota_gb} GB storage
                          </div>
                          <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4 text-gray-400" />
                            Created {formatDate(ws.created_at)}
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                          <MapPin className="w-3 h-3" />
                          <span>Contact: {ws.contact_person}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2 flex-shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDeleteWorkspace(ws.id, ws.name)}
                        className="gap-1 text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="w-3 h-3" />
                        Deactivate
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Create Workspace Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto">
            <Card className="w-full max-w-2xl my-8">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Plus className="w-5 h-5" />
                  Create New Workspace
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCreateWorkspace} className="space-y-4">
                  {/* Workspace Name */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Workspace Name *
                    </label>
                    <Input
                      value={newWorkspace.name}
                      onChange={(e) => setNewWorkspace({...newWorkspace, name: e.target.value})}
                      placeholder="e.g., ABC Medical Clinic"
                      required
                    />
                  </div>

                  {/* Organization Name */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Organization Name *
                    </label>
                    <Input
                      value={newWorkspace.organization_name}
                      onChange={(e) => setNewWorkspace({...newWorkspace, organization_name: e.target.value})}
                      placeholder="e.g., ABC Medical Clinic (Pty) Ltd"
                      required
                    />
                  </div>

                  {/* Organization Type & Subscription */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Organization Type *
                      </label>
                      <select
                        value={newWorkspace.organization_type}
                        onChange={(e) => setNewWorkspace({...newWorkspace, organization_type: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-teal-500"
                        required
                      >
                        <option value="gp_practice">GP Practice</option>
                        <option value="occupational_health">Occupational Health</option>
                        <option value="hospital">Hospital</option>
                        <option value="clinic">Clinic</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Subscription Tier *
                      </label>
                      <select
                        value={newWorkspace.subscription_tier}
                        onChange={(e) => setNewWorkspace({...newWorkspace, subscription_tier: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-teal-500"
                        required
                      >
                        <option value="free">Free (10 users, 1K docs)</option>
                        <option value="basic">Basic (25 users, 5K docs)</option>
                        <option value="professional">Professional (50 users, 10K docs)</option>
                        <option value="enterprise">Enterprise (Unlimited)</option>
                      </select>
                    </div>
                  </div>

                  {/* Contact Person & Email */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Contact Person *
                      </label>
                      <Input
                        value={newWorkspace.contact_person}
                        onChange={(e) => setNewWorkspace({...newWorkspace, contact_person: e.target.value})}
                        placeholder="Dr. Jane Smith"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Contact Email *
                      </label>
                      <Input
                        type="email"
                        value={newWorkspace.contact_email}
                        onChange={(e) => setNewWorkspace({...newWorkspace, contact_email: e.target.value})}
                        placeholder="contact@clinic.com"
                        required
                      />
                    </div>
                  </div>

                  {/* Phone */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Contact Phone
                    </label>
                    <Input
                      type="tel"
                      value={newWorkspace.contact_phone}
                      onChange={(e) => setNewWorkspace({...newWorkspace, contact_phone: e.target.value})}
                      placeholder="+27 11 123 4567"
                    />
                  </div>

                  {/* Address */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Address
                    </label>
                    <Input
                      value={newWorkspace.address_line1}
                      onChange={(e) => setNewWorkspace({...newWorkspace, address_line1: e.target.value})}
                      placeholder="123 Medical Street"
                      className="mb-2"
                    />
                  </div>

                  {/* City, Province, Postal Code */}
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        City
                      </label>
                      <Input
                        value={newWorkspace.city}
                        onChange={(e) => setNewWorkspace({...newWorkspace, city: e.target.value})}
                        placeholder="Johannesburg"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Province
                      </label>
                      <Input
                        value={newWorkspace.province}
                        onChange={(e) => setNewWorkspace({...newWorkspace, province: e.target.value})}
                        placeholder="Gauteng"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Postal Code
                      </label>
                      <Input
                        value={newWorkspace.postal_code}
                        onChange={(e) => setNewWorkspace({...newWorkspace, postal_code: e.target.value})}
                        placeholder="2000"
                      />
                    </div>
                  </div>

                  {/* Buttons */}
                  <div className="flex gap-2 pt-4 border-t">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setShowCreateModal(false);
                        setNewWorkspace({
                          name: '',
                          organization_name: '',
                          organization_type: 'gp_practice',
                          contact_email: '',
                          contact_phone: '',
                          contact_person: '',
                          address_line1: '',
                          city: '',
                          province: '',
                          postal_code: '',
                          subscription_tier: 'free'
                        });
                      }}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      disabled={isCreating}
                      className="flex-1 bg-teal-600 hover:bg-teal-700"
                    >
                      {isCreating ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                          Creating...
                        </>
                      ) : (
                        'Create Workspace'
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkspaceManagement;
