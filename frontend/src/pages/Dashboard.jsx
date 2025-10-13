import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, Activity, DollarSign, FileText, TrendingUp, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { analyticsAPI } from '@/services/api';

const Dashboard = () => {
  const [stats, setStats] = useState({
    total_patients: 0,
    total_encounters: 0,
    total_invoices: 0,
    total_revenue: 0,
    recent_encounters: []
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const response = await analyticsAPI.getSummary();
      setStats(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      title: 'Total Patients',
      value: stats.total_patients,
      icon: Users,
      color: 'from-blue-500 to-cyan-500',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Total Encounters',
      value: stats.total_encounters,
      icon: Activity,
      color: 'from-teal-500 to-emerald-500',
      bgColor: 'bg-teal-50',
    },
    {
      title: 'Total Revenue',
      value: `R${stats.total_revenue.toFixed(2)}`,
      icon: DollarSign,
      color: 'from-violet-500 to-purple-500',
      bgColor: 'bg-violet-50',
    },
    {
      title: 'Pending Invoices',
      value: stats.total_invoices,
      icon: FileText,
      color: 'from-orange-500 to-amber-500',
      bgColor: 'bg-orange-50',
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in" data-testid="dashboard-container">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-slate-800 mb-2">Dashboard</h1>
        <p className="text-slate-600">Welcome to your GP practice management system</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <Card 
              key={index} 
              className="relative overflow-hidden border-0 shadow-lg hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
              data-testid={`stat-card-${stat.title.toLowerCase().replace(' ', '-')}`}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-slate-600">
                  {stat.title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-3xl font-bold text-slate-800">{stat.value}</p>
                  </div>
                  <div className={`w-16 h-16 rounded-2xl ${stat.bgColor} flex items-center justify-center`}>
                    <Icon className={`w-8 h-8 bg-gradient-to-br ${stat.color} bg-clip-text text-transparent`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Quick Actions */}
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-xl font-bold text-slate-800">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link to="/patients">
              <Button 
                className="w-full h-24 bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
                data-testid="quick-action-register-patient"
              >
                <div className="flex flex-col items-center gap-2">
                  <Users className="w-6 h-6" />
                  <span className="font-semibold">Register New Patient</span>
                </div>
              </Button>
            </Link>
            <Link to="/patients">
              <Button 
                className="w-full h-24 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
                data-testid="quick-action-view-patients"
              >
                <div className="flex flex-col items-center gap-2">
                  <FileText className="w-6 h-6" />
                  <span className="font-semibold">View Patient Registry</span>
                </div>
              </Button>
            </Link>
            <Link to="/billing">
              <Button 
                className="w-full h-24 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
                data-testid="quick-action-billing"
              >
                <div className="flex flex-col items-center gap-2">
                  <DollarSign className="w-6 h-6" />
                  <span className="font-semibold">Manage Billing</span>
                </div>
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Recent Encounters */}
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            Recent Encounters
          </CardTitle>
        </CardHeader>
        <CardContent>
          {stats.recent_encounters && stats.recent_encounters.length > 0 ? (
            <div className="space-y-3">
              {stats.recent_encounters.map((encounter) => (
                <div
                  key={encounter.id}
                  className="flex items-center justify-between p-4 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors duration-200"
                  data-testid={`recent-encounter-${encounter.id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center text-white font-semibold">
                      <Activity className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-800">Encounter #{encounter.id.slice(0, 8)}</p>
                      <p className="text-sm text-slate-600">
                        {encounter.chief_complaint || 'General consultation'}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-slate-600">
                      {new Date(encounter.encounter_date).toLocaleDateString()}
                    </p>
                    <span className={`inline-block px-3 py-1 text-xs font-medium rounded-full ${
                      encounter.status === 'completed' 
                        ? 'bg-emerald-100 text-emerald-700' 
                        : 'bg-amber-100 text-amber-700'
                    }`}>
                      {encounter.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Activity className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">No recent encounters</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Dashboard;
