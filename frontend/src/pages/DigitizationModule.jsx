import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import {
  LayoutDashboard,
  Archive,
  Upload,
  ClipboardList,
  Settings,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
  FileText,
  User,
  Calendar,
  BarChart3
} from 'lucide-react';

// Import existing components (we'll reuse them)
import DigitizationArchive from './DigitizationArchive';

const DigitizationModule = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Get active tab from URL or default to 'dashboard'
  const activeTab = searchParams.get('tab') || 'dashboard';
  
  // Statistics state
  const [stats, setStats] = useState({
    total: 0,
    parsed: 0,
    pending_validation: 0,
    extracted: 0,
    approved: 0,
    rejected: 0
  });
  
  const [recentDocuments, setRecentDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // Get user role and name from auth context
  const userRole = user?.role || 'validator';
  const userName = user ? `${user.first_name} ${user.last_name}` : 'User';

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setIsLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      // Fetch all documents
      const response = await axios.get(`${backendUrl}/api/gp/documents`, {
        params: { limit: 100 }
      });

      const docs = response.data.documents || [];
      
      // Calculate statistics
      const newStats = {
        total: docs.length,
        parsed: docs.filter(d => d.status === 'parsed').length,
        pending_validation: docs.filter(d => d.status === 'pending_validation').length,
        extracted: docs.filter(d => d.status === 'extracted').length,
        approved: docs.filter(d => d.status === 'approved').length,
        rejected: docs.filter(d => d.status === 'rejected').length
      };
      
      setStats(newStats);
      
      // Get recent documents (last 5)
      const recent = docs
        .sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date))
        .slice(0, 5);
      
      setRecentDocuments(recent);
      
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      toast({
        title: "Error",
        description: "Failed to load dashboard data",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleTabChange = (value) => {
    setSearchParams({ tab: value });
  };

  const getStatusColor = (status) => {
    const colors = {
      'parsed': 'bg-yellow-100 text-yellow-800',
      'pending_validation': 'bg-amber-100 text-amber-800',
      'extracted': 'bg-purple-100 text-purple-800',
      'approved': 'bg-green-100 text-green-800',
      'rejected': 'bg-red-100 text-red-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    const now = new Date();
    const diffHours = Math.floor((now - date) / (1000 * 60 * 60));
    
    if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else {
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    }
  };

  // Validator Dashboard Component
  const ValidatorDashboard = () => {
    const urgentDocs = recentDocuments.filter(doc => {
      const hoursSinceUpload = Math.floor(
        (new Date() - new Date(doc.upload_date)) / (1000 * 60 * 60)
      );
      return hoursSinceUpload > 24 && doc.status === 'pending_validation';
    });

    return (
      <div className="space-y-6">
        {/* Welcome Banner */}
        <Card className="bg-gradient-to-r from-teal-500 to-cyan-600 text-white">
          <CardContent className="pt-6">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-2xl font-bold mb-1">Welcome back, {userName}!</h2>
                <p className="text-teal-50">Validator Dashboard</p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold">{stats.pending_validation}</p>
                <p className="text-sm text-teal-50">Pending Validation</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Statistics Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-yellow-600">{stats.parsed}</p>
                  <p className="text-sm text-gray-600">Parsed</p>
                </div>
                <Clock className="w-8 h-8 text-yellow-600" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-amber-600">{stats.pending_validation}</p>
                  <p className="text-sm text-gray-600">Pending</p>
                </div>
                <AlertCircle className="w-8 h-8 text-amber-600" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-green-600">{stats.approved}</p>
                  <p className="text-sm text-gray-600">Approved</p>
                </div>
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-red-600">{stats.rejected}</p>
                  <p className="text-sm text-gray-600">Rejected</p>
                </div>
                <AlertCircle className="w-8 h-8 text-red-600" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content - Two Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - 2/3 width */}
          <div className="lg:col-span-2 space-y-6">
            {/* Validation Queue Summary */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ClipboardList className="w-5 h-5" />
                  Validation Queue ({stats.pending_validation} docs)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {urgentDocs.length > 0 && (
                  <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertCircle className="w-4 h-4 text-red-600" />
                      <span className="font-semibold text-red-900">🔴 URGENT ({urgentDocs.length} docs)</span>
                    </div>
                    {urgentDocs.map(doc => (
                      <div key={doc.id} className="text-sm text-red-800 ml-6">
                        • {doc.filename} - {formatDate(doc.upload_date)}
                      </div>
                    ))}
                  </div>
                )}

                <div className="space-y-3">
                  {recentDocuments
                    .filter(doc => doc.status === 'pending_validation' || doc.status === 'parsed')
                    .slice(0, 5)
                    .map(doc => (
                      <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                        <div className="flex items-center gap-3">
                          <FileText className="w-4 h-4 text-gray-600" />
                          <div>
                            <p className="font-medium text-sm">{doc.filename}</p>
                            <p className="text-xs text-gray-500">{formatDate(doc.upload_date)}</p>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          onClick={() => navigate(`/document-validation/${doc.id}`)}
                          className="bg-teal-600 hover:bg-teal-700"
                        >
                          Review
                        </Button>
                      </div>
                    ))}
                </div>

                <Button
                  onClick={() => navigate('/validation-queue')}
                  variant="outline"
                  className="w-full mt-4"
                >
                  View All in Queue →
                </Button>
              </CardContent>
            </Card>

            {/* Recent Activity */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="w-5 h-5" />
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {recentDocuments.slice(0, 5).map(doc => (
                    <div key={doc.id} className="flex items-center justify-between text-sm py-2 border-b last:border-0">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-gray-400" />
                        <span className="truncate max-w-xs">{doc.filename}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-1 rounded ${getStatusColor(doc.status)}`}>
                          {doc.status}
                        </span>
                        <span className="text-xs text-gray-500">{formatDate(doc.upload_date)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Column - 1/3 width */}
          <div className="space-y-6">
            {/* Quick Actions */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">🎯 Quick Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <Button
                    onClick={() => navigate('/validation-queue')}
                    className="w-full justify-start bg-teal-600 hover:bg-teal-700"
                  >
                    <ClipboardList className="w-4 h-4 mr-2" />
                    Go to Queue
                  </Button>
                  <Button
                    onClick={() => navigate('/document-upload')}
                    variant="outline"
                    className="w-full justify-start"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Upload Document
                  </Button>
                  <Button
                    onClick={() => handleTabChange('archive')}
                    variant="outline"
                    className="w-full justify-start"
                  >
                    <Archive className="w-4 h-4 mr-2" />
                    View Archive
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Your Performance */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Your Performance
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Today:</span>
                    <span className="font-semibold">-</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">This Week:</span>
                    <span className="font-semibold">-</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Accuracy:</span>
                    <span className="font-semibold text-green-600">-</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Avg Time:</span>
                    <span className="font-semibold">-</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-4">
                  Performance tracking coming soon
                </p>
              </CardContent>
            </Card>

            {/* Alerts */}
            {urgentDocs.length > 0 && (
              <Card className="border-amber-200 bg-amber-50">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2 text-amber-900">
                    <AlertCircle className="w-4 h-4" />
                    Alerts
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm text-amber-800">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-amber-600 rounded-full"></div>
                      <span>{urgentDocs.length} docs &gt; 24h old</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Digitization Module</h1>
          <p className="text-gray-600">Comprehensive document management and workflow</p>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-flex mb-6">
            <TabsTrigger value="dashboard" className="gap-2">
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="archive" className="gap-2">
              <Archive className="w-4 h-4" />
              Archive
            </TabsTrigger>
            <TabsTrigger value="upload" className="gap-2">
              <Upload className="w-4 h-4" />
              Upload
            </TabsTrigger>
            <TabsTrigger value="queue" className="gap-2">
              <ClipboardList className="w-4 h-4" />
              Queue
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard">
            {isLoading ? (
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <ValidatorDashboard />
            )}
          </TabsContent>

          <TabsContent value="archive">
            <DigitizationArchive />
          </TabsContent>

          <TabsContent value="upload">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <Upload className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-700 mb-2">Upload Documents</h3>
                  <p className="text-gray-600 mb-4">Upload single or batch documents for digitization</p>
                  <div className="flex gap-4 justify-center">
                    <Button
                      onClick={() => navigate('/document-upload')}
                      className="bg-teal-600 hover:bg-teal-700"
                    >
                      Go to Upload Page
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="queue">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <ClipboardList className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-700 mb-2">Validation Queue</h3>
                  <p className="text-gray-600 mb-4">Review and validate pending documents</p>
                  <Button
                    onClick={() => navigate('/validation-queue')}
                    className="bg-teal-600 hover:bg-teal-700"
                  >
                    Go to Validation Queue
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default DigitizationModule;
