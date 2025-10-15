import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';
import {
  Search,
  UserPlus,
  CheckCircle,
  Clock,
  Users,
  AlertCircle
} from 'lucide-react';

const ReceptionCheckIn = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [reasonForVisit, setReasonForVisit] = useState('');
  const [priority, setPriority] = useState('normal');
  const [isCheckingIn, setIsCheckingIn] = useState(false);
  const [queueStats, setQueueStats] = useState(null);

  useEffect(() => {
    fetchQueueStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchQueueStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchQueueStats = async () => {
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      const response = await axios.get(`${backendUrl}/api/queue/stats`);
      setQueueStats(response.data.stats);
    } catch (error) {
      console.error('Error fetching queue stats:', error);
    }
  };

  const searchPatients = async () => {
    if (!searchQuery.trim()) return;
    
    try {
      setIsSearching(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      console.log('Searching for:', searchQuery);
      console.log('API URL:', `${backendUrl}/api/patients?search=${encodeURIComponent(searchQuery)}`);
      
      const response = await axios.get(
        `${backendUrl}/api/patients?search=${encodeURIComponent(searchQuery)}`
      );

      console.log('Search response:', response.data);
      setSearchResults(response.data || []);
    } catch (error) {
      console.error('Error searching patients:', error);
      toast({
        title: "Error",
        description: "Failed to search patients",
        variant: "destructive"
      });
    } finally {
      setIsSearching(false);
    }
  };

  const handleCheckIn = async () => {
    if (!selectedPatient) {
      toast({
        title: "Error",
        description: "Please select a patient",
        variant: "destructive"
      });
      return;
    }

    if (!reasonForVisit.trim()) {
      toast({
        title: "Error",
        description: "Please enter reason for visit",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsCheckingIn(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const response = await axios.post(
        `${backendUrl}/api/queue/check-in`,
        {
          patient_id: selectedPatient.id,
          reason_for_visit: reasonForVisit,
          priority: priority
        }
      );

      toast({
        title: "Success",
        description: `${response.data.patient_name} checked in - Queue #${response.data.queue_number}`,
      });

      // Reset form
      setSelectedPatient(null);
      setReasonForVisit('');
      setPriority('normal');
      setSearchQuery('');
      setSearchResults([]);
      
      // Refresh stats
      fetchQueueStats();
    } catch (error) {
      console.error('Error checking in patient:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to check in patient",
        variant: "destructive"
      });
    } finally {
      setIsCheckingIn(false);
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'emergency':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'urgent':
        return 'bg-orange-100 text-orange-800 border-orange-300';
      default:
        return 'bg-green-100 text-green-800 border-green-300';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Reception Check-In</h1>
          <p className="text-gray-600">Check in patients and manage the queue</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Check-in Panel */}
          <div className="lg:col-span-2 space-y-6">
            {/* Patient Search */}
            <Card>
              <CardHeader>
                <CardTitle>Find Patient</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-3 mb-4">
                  <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <Input
                      placeholder="Search by name, ID number, or phone..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && searchPatients()}
                      className="pl-10"
                    />
                  </div>
                  <Button onClick={searchPatients} disabled={isSearching}>
                    {isSearching ? 'Searching...' : 'Search'}
                  </Button>
                  <Button variant="outline" onClick={() => navigate('/patients')}>
                    <UserPlus className="w-4 h-4 mr-2" />
                    New Patient
                  </Button>
                </div>

                {/* Search Results */}
                {searchResults.length > 0 && (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {searchResults.map((patient) => (
                      <div
                        key={patient.id}
                        className={`
                          p-4 border-2 rounded-lg cursor-pointer transition-all
                          ${selectedPatient?.id === patient.id
                            ? 'border-teal-500 bg-teal-50'
                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                          }
                        `}
                        onClick={() => setSelectedPatient(patient)}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="font-semibold text-gray-900">
                              {patient.first_name} {patient.last_name}
                            </h4>
                            <p className="text-sm text-gray-600">
                              ID: {patient.id_number} • DOB: {patient.dob}
                            </p>
                          </div>
                          {selectedPatient?.id === patient.id && (
                            <CheckCircle className="w-6 h-6 text-teal-600" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {searchQuery && searchResults.length === 0 && !isSearching && (
                  <div className="text-center py-8 text-gray-500">
                    <AlertCircle className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                    <p>No patients found. Try a different search or register a new patient.</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Check-in Form */}
            {selectedPatient && (
              <Card>
                <CardHeader>
                  <CardTitle>Check-In Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-teal-50 border border-teal-200 rounded-lg">
                    <h4 className="font-semibold text-gray-900 mb-1">Selected Patient</h4>
                    <p className="text-gray-700">
                      {selectedPatient.first_name} {selectedPatient.last_name}
                    </p>
                    <p className="text-sm text-gray-600">ID: {selectedPatient.id_number}</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Reason for Visit *
                    </label>
                    <Textarea
                      placeholder="e.g., Routine check-up, Flu symptoms, Follow-up consultation..."
                      value={reasonForVisit}
                      onChange={(e) => setReasonForVisit(e.target.value)}
                      rows={3}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Priority
                    </label>
                    <div className="flex gap-3">
                      {['normal', 'urgent', 'emergency'].map((p) => (
                        <button
                          key={p}
                          onClick={() => setPriority(p)}
                          className={`
                            flex-1 px-4 py-3 rounded-lg border-2 font-medium capitalize transition-all
                            ${priority === p
                              ? getPriorityColor(p) + ' border-current'
                              : 'border-gray-200 hover:border-gray-300 bg-white text-gray-700'
                            }
                          `}
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>

                  <Button
                    onClick={handleCheckIn}
                    disabled={isCheckingIn || !reasonForVisit.trim()}
                    className="w-full bg-teal-600 hover:bg-teal-700 text-white h-12 text-lg"
                  >
                    {isCheckingIn ? (
                      <>
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                        Checking In...
                      </>
                    ) : (
                      <>
                        <CheckCircle className="w-5 h-5 mr-2" />
                        Check In Patient
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Queue Stats Sidebar */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  Today's Queue
                </CardTitle>
              </CardHeader>
              <CardContent>
                {queueStats ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                      <span className="text-sm font-medium text-gray-700">Total Check-ins</span>
                      <span className="text-2xl font-bold text-blue-600">{queueStats.total_checked_in}</span>
                    </div>
                    
                    <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                      <span className="text-sm font-medium text-gray-700">Waiting</span>
                      <span className="text-2xl font-bold text-yellow-600">{queueStats.waiting}</span>
                    </div>
                    
                    <div className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                      <span className="text-sm font-medium text-gray-700">In Progress</span>
                      <span className="text-2xl font-bold text-orange-600">{queueStats.in_progress}</span>
                    </div>
                    
                    <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                      <span className="text-sm font-medium text-gray-700">Completed</span>
                      <span className="text-2xl font-bold text-green-600">{queueStats.completed}</span>
                    </div>

                    <div className="pt-3 border-t">
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Clock className="w-4 h-4" />
                        <span>Avg Wait Time: <strong>{queueStats.average_wait_time_minutes} min</strong></span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => navigate('/queue/display')}
                >
                  <Users className="w-4 h-4 mr-2" />
                  View Queue Display
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => navigate('/queue/workstation')}
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Workstation Dashboard
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReceptionCheckIn;
