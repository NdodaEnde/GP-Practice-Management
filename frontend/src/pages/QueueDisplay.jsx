import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import axios from 'axios';
import {
  Clock,
  Users,
  Activity
} from 'lucide-react';

const QueueDisplay = () => {
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    fetchQueue();
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchQueue, 5000);
    
    // Update clock every second
    const clockInterval = setInterval(() => setCurrentTime(new Date()), 1000);
    
    return () => {
      clearInterval(interval);
      clearInterval(clockInterval);
    };
  }, []);

  const fetchQueue = async () => {
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
      
      const [queueRes, statsRes] = await Promise.all([
        axios.get(`${backendUrl}/api/queue/current`),
        axios.get(`${backendUrl}/api/queue/stats`)
      ]);

      setQueue(queueRes.data.queue || []);
      setStats(statsRes.data.stats);
    } catch (error) {
      console.error('Error fetching queue:', error);
    }
  };

  const getStationColor = (station) => {
    switch (station) {
      case 'vitals':
        return 'bg-blue-500';
      case 'consultation':
        return 'bg-green-500';
      case 'dispensary':
        return 'bg-purple-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusDisplay = (status) => {
    switch (status) {
      case 'waiting':
        return { text: 'Waiting', color: 'text-yellow-600' };
      case 'in_vitals':
        return { text: 'In Vitals', color: 'text-blue-600' };
      case 'in_consultation':
        return { text: 'In Consultation', color: 'text-green-600' };
      case 'in_dispensary':
        return { text: 'In Dispensary', color: 'text-purple-600' };
      default:
        return { text: status, color: 'text-gray-600' };
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-500 to-cyan-600 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-2xl p-8 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">Patient Queue</h1>
              <p className="text-xl text-gray-600">SurgiScan GP Practice</p>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-gray-900">
                {currentTime.toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit' })}
              </div>
              <div className="text-lg text-gray-600">
                {currentTime.toLocaleDateString('en-ZA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </div>
            </div>
          </div>
        </div>

        {/* Stats Bar */}
        {stats && (
          <div className="grid grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
                <Users className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Total Today</p>
                <p className="text-3xl font-bold text-gray-900">{stats.total_checked_in}</p>
              </div>
            </div>
            
            <div className="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4">
              <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center">
                <Clock className="w-8 h-8 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Waiting</p>
                <p className="text-3xl font-bold text-yellow-600">{stats.waiting}</p>
              </div>
            </div>
            
            <div className="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4">
              <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
                <Activity className="w-8 h-8 text-orange-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">In Progress</p>
                <p className="text-3xl font-bold text-orange-600">{stats.in_progress}</p>
              </div>
            </div>
            
            <div className="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                <Users className="w-8 h-8 text-green-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Avg Wait</p>
                <p className="text-3xl font-bold text-green-600">{stats.average_wait_time_minutes}m</p>
              </div>
            </div>
          </div>
        )}

        {/* Queue List */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          <div className="bg-gradient-to-r from-teal-600 to-cyan-600 px-8 py-6">
            <h2 className="text-2xl font-bold text-white">Current Queue</h2>
          </div>
          
          <div className="divide-y">
            {queue.length === 0 ? (
              <div className="text-center py-20">
                <Users className="w-20 h-20 text-gray-300 mx-auto mb-4" />
                <p className="text-2xl font-semibold text-gray-500">No patients in queue</p>
              </div>
            ) : (
              queue.slice(0, 10).map((entry) => {
                const statusInfo = getStatusDisplay(entry.status);
                return (
                  <div key={entry.id} className="px-8 py-6 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-6">
                        <div className={`
                          w-20 h-20 rounded-2xl flex items-center justify-center text-white font-bold text-3xl
                          ${getStationColor(entry.station)}
                        `}>
                          {entry.queue_number}
                        </div>
                        <div>
                          <h3 className="text-2xl font-bold text-gray-900">{entry.patient_name}</h3>
                          <p className="text-lg text-gray-600">{entry.reason_for_visit}</p>
                        </div>
                      </div>
                      
                      <div className="text-right">
                        <Badge className={`${statusInfo.color} text-lg px-4 py-2 font-semibold`}>
                          {statusInfo.text}
                        </Badge>
                        <p className="text-sm text-gray-500 mt-2">
                          Wait: {entry.wait_time_minutes} min
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8 text-white text-lg">
          <p>Auto-refreshing every 5 seconds • For assistance, please contact reception</p>
        </div>
      </div>
    </div>
  );
};

export default QueueDisplay;
