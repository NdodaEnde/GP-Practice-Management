import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';
import {
  Users,
  Clock,
  CheckCircle,
  ArrowRight,
  Activity,
  UserCheck,
  AlertCircle,
  RefreshCw,
  FileText,
  Mic,
  ExternalLink
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const WorkstationDashboard = () => {
  const { toast } = useToast();
  
  const [selectedStation, setSelectedStation] = useState('consultation');
  const [queue, setQueue] = useState([]);
  const [activePatient, setActivePatient] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const stations = [
    { id: 'vitals', name: 'Vitals Station', icon: Activity },
    { id: 'consultation', name: 'Consultation', icon: UserCheck },
    { id: 'dispensary', name: 'Dispensary', icon: Users }
  ];

  useEffect(() => {
    fetchQueue();
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchQueue, 5000);
    return () => clearInterval(interval);
  }, [selectedStation]);

  const fetchQueue = async () => {
    try {
      setIsRefreshing(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const response = await axios.get(
        `${backendUrl}/api/queue/current?station=${selectedStation}`
      );

      const queueData = response.data.queue || [];
      setQueue(queueData);
      
      // Find if there's an active patient (in progress at this station)
      const statusMap = {
        'vitals': 'in_vitals',
        'consultation': 'in_consultation',
        'dispensary': 'in_dispensary'
      };
      
      const currentStatus = statusMap[selectedStation];
      const active = queueData.find(entry => entry.status === currentStatus);
      setActivePatient(active || null);
      
    } catch (error) {
      console.error('Error fetching queue:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleCallNext = async () => {
    try {
      setIsLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      // Get the first waiting patient
      const waitingPatients = queue.filter(entry => entry.status === 'waiting');
      
      if (waitingPatients.length === 0) {
        toast({
          title: "No patients waiting",
          description: "There are no patients in the queue",
          variant: "destructive"
        });
        return;
      }
      
      const nextPatient = waitingPatients[0];
      
      // Call the patient to this station
      await axios.post(
        `${backendUrl}/api/queue/${nextPatient.id}/call-next`,
        null,
        { params: { station: selectedStation } }
      );

      toast({
        title: "Patient Called",
        description: `${nextPatient.patient_name} - Queue #${nextPatient.queue_number}`,
      });

      // Refresh queue
      await fetchQueue();
      
    } catch (error) {
      console.error('Error calling next patient:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to call next patient",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCompleteConsultation = async () => {
    if (!activePatient) return;
    
    try {
      setIsLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      // Update status to completed
      await axios.put(
        `${backendUrl}/api/queue/${activePatient.id}/update-status`,
        {
          status: 'completed',
          station: selectedStation,
          notes: `Completed at ${selectedStation}`
        }
      );

      toast({
        title: "Consultation Complete",
        description: `${activePatient.patient_name} has been marked as complete`,
      });

      // Refresh queue
      await fetchQueue();
      
    } catch (error) {
      console.error('Error completing consultation:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to complete consultation",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendToNextStation = async (nextStation) => {
    if (!activePatient) return;
    
    try {
      setIsLoading(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const statusMap = {
        'vitals': 'in_vitals',
        'consultation': 'in_consultation',
        'dispensary': 'in_dispensary'
      };
      
      // Update status to next station
      await axios.put(
        `${backendUrl}/api/queue/${activePatient.id}/update-status`,
        {
          status: statusMap[nextStation],
          station: nextStation,
          notes: `Transferred from ${selectedStation} to ${nextStation}`
        }
      );

      toast({
        title: "Patient Transferred",
        description: `${activePatient.patient_name} sent to ${nextStation}`,
      });

      // Refresh queue
      await fetchQueue();
      
    } catch (error) {
      console.error('Error transferring patient:', error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to transfer patient",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const waitingCount = queue.filter(entry => entry.status === 'waiting').length;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Workstation Dashboard</h1>
          <p className="text-gray-600">Manage your patient queue and consultations</p>
        </div>

        {/* Station Selection */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Select Your Station</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {stations.map((station) => {
                const StationIcon = station.icon;
                return (
                  <button
                    key={station.id}
                    onClick={() => setSelectedStation(station.id)}
                    className={`
                      p-6 rounded-lg border-2 transition-all
                      ${selectedStation === station.id
                        ? 'border-teal-500 bg-teal-50'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                      }
                    `}
                  >
                    <StationIcon className={`w-8 h-8 mx-auto mb-2 ${
                      selectedStation === station.id ? 'text-teal-600' : 'text-gray-600'
                    }`} />
                    <p className={`font-semibold ${
                      selectedStation === station.id ? 'text-teal-900' : 'text-gray-900'
                    }`}>
                      {station.name}
                    </p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Active Patient Card */}
          <div className="lg:col-span-2">
            <Card className="mb-6">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <UserCheck className="w-5 h-5" />
                  Current Patient
                </CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchQueue}
                  disabled={isRefreshing}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </CardHeader>
              <CardContent>
                {activePatient ? (
                  <div className="space-y-4">
                    <div className="p-6 bg-teal-50 border-2 border-teal-200 rounded-lg">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <div className="flex items-center gap-3 mb-2">
                            <div className="w-12 h-12 bg-teal-500 rounded-full flex items-center justify-center text-white font-bold text-xl">
                              {activePatient.queue_number}
                            </div>
                            <div>
                              <h3 className="text-2xl font-bold text-gray-900">
                                {activePatient.patient_name}
                              </h3>
                              <p className="text-sm text-gray-600">
                                Patient ID: {activePatient.patient_id.substring(0, 8)}...
                              </p>
                            </div>
                          </div>
                        </div>
                        {activePatient.priority !== 'normal' && (
                          <Badge className={`
                            ${activePatient.priority === 'emergency' 
                              ? 'bg-red-100 text-red-800' 
                              : 'bg-orange-100 text-orange-800'
                            }
                          `}>
                            {activePatient.priority.toUpperCase()}
                          </Badge>
                        )}
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-start gap-2">
                          <AlertCircle className="w-5 h-5 text-gray-500 mt-0.5" />
                          <div>
                            <p className="text-sm font-medium text-gray-600">Reason for Visit</p>
                            <p className="text-gray-900">{activePatient.reason_for_visit}</p>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Clock className="w-4 h-4" />
                          <span>Wait Time: <strong>{activePatient.wait_time_minutes || 0} minutes</strong></span>
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-3">
                      <Button
                        onClick={handleCompleteConsultation}
                        disabled={isLoading}
                        className="flex-1 bg-green-600 hover:bg-green-700 h-12 text-lg"
                      >
                        <CheckCircle className="w-5 h-5 mr-2" />
                        Complete Consultation
                      </Button>

                      {selectedStation !== 'dispensary' && (
                        <Button
                          variant="outline"
                          onClick={() => handleSendToNextStation(
                            selectedStation === 'vitals' ? 'consultation' : 'dispensary'
                          )}
                          disabled={isLoading}
                          className="h-12"
                        >
                          <ArrowRight className="w-5 h-5 mr-2" />
                          Send to {selectedStation === 'vitals' ? 'Consultation' : 'Dispensary'}
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                    <p className="text-lg font-semibold text-gray-600 mb-2">No Active Patient</p>
                    <p className="text-gray-500 mb-4">Call the next patient from the queue</p>
                    <Button
                      onClick={handleCallNext}
                      disabled={isLoading || waitingCount === 0}
                      className="bg-teal-600 hover:bg-teal-700"
                    >
                      <UserCheck className="w-4 h-4 mr-2" />
                      Call Next Patient
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Waiting Queue */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Users className="w-5 h-5" />
                    Waiting Queue ({waitingCount})
                  </span>
                  <Badge className="bg-yellow-100 text-yellow-800">
                    {waitingCount} waiting
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {waitingCount > 0 ? (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {queue
                      .filter(entry => entry.status === 'waiting')
                      .map((entry) => (
                        <div
                          key={entry.id}
                          className="p-4 bg-gray-50 border rounded-lg hover:bg-gray-100 transition-colors"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 bg-gray-500 rounded-full flex items-center justify-center text-white font-bold">
                                {entry.queue_number}
                              </div>
                              <div>
                                <p className="font-semibold text-gray-900">{entry.patient_name}</p>
                                <p className="text-sm text-gray-600">{entry.reason_for_visit}</p>
                              </div>
                            </div>
                            <div className="text-right text-sm text-gray-500">
                              <Clock className="w-4 h-4 inline mr-1" />
                              {entry.wait_time_minutes || 0}m
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Users className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>No patients waiting</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Stats Sidebar */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  onClick={handleCallNext}
                  disabled={isLoading || waitingCount === 0}
                  className="w-full bg-teal-600 hover:bg-teal-700 h-12"
                >
                  <UserCheck className="w-4 h-4 mr-2" />
                  Call Next Patient
                </Button>
                
                {activePatient && (
                  <>
                    <Button
                      onClick={handleCompleteConsultation}
                      disabled={isLoading}
                      className="w-full bg-green-600 hover:bg-green-700"
                    >
                      <CheckCircle className="w-4 h-4 mr-2" />
                      Complete
                    </Button>
                    
                    {selectedStation !== 'dispensary' && (
                      <Button
                        variant="outline"
                        onClick={() => handleSendToNextStation(
                          selectedStation === 'vitals' ? 'consultation' : 'dispensary'
                        )}
                        disabled={isLoading}
                        className="w-full"
                      >
                        <ArrowRight className="w-4 h-4 mr-2" />
                        Next Station
                      </Button>
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Station Stats</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">Waiting</span>
                  <span className="text-xl font-bold text-yellow-600">{waitingCount}</span>
                </div>
                
                <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">In Progress</span>
                  <span className="text-xl font-bold text-blue-600">
                    {activePatient ? 1 : 0}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkstationDashboard;
