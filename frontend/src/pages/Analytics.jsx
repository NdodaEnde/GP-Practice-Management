import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Activity, DollarSign, TrendingUp, Calendar, FileText, Pill, HeartPulse } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { analyticsAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

const Analytics = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    total_patients: 0,
    total_encounters: 0,
    total_revenue: 0,
  });

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      setLoading(true);
      const response = await analyticsAPI.getSummary();
      setStats(response.data);
    } catch (error) {
      console.error('Error loading analytics:', error);
      toast({
        title: 'Error',
        description: 'Failed to load analytics',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  // Mock data for analytics charts
  const patientGrowthData = [
    { month: 'Jul', patients: 45 },
    { month: 'Aug', patients: 58 },
    { month: 'Sep', patients: 72 },
    { month: 'Oct', patients: 89 },
    { month: 'Nov', patients: 105 },
    { month: 'Dec', patients: 128 },
    { month: 'Jan', patients: 156 },
  ];

  const encountersByTypeData = [
    { type: 'General Consultation', value: 245 },
    { type: 'Follow-up', value: 189 },
    { type: 'Chronic Disease Management', value: 142 },
    { type: 'Minor Procedures', value: 78 },
    { type: 'Vaccination', value: 56 },
  ];

  const revenueData = [
    { month: 'Jul', revenue: 45000 },
    { month: 'Aug', revenue: 52000 },
    { month: 'Sep', revenue: 48000 },
    { month: 'Oct', revenue: 61000 },
    { month: 'Nov', revenue: 58000 },
    { month: 'Dec', revenue: 67000 },
    { month: 'Jan', revenue: 73000 },
  ];

  const topDiagnosesData = [
    { diagnosis: 'Hypertension', count: 89 },
    { diagnosis: 'Type 2 Diabetes', count: 76 },
    { diagnosis: 'Upper Respiratory Infection', count: 64 },
    { diagnosis: 'Asthma', count: 52 },
    { diagnosis: 'Anxiety Disorder', count: 41 },
  ];

  // Chart Options
  const patientGrowthChart = {
    title: {
      text: 'Patient Growth Trend',
      textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    xAxis: {
      type: 'category',
      data: patientGrowthData.map(d => d.month)
    },
    yAxis: {
      type: 'value',
      name: 'Patients'
    },
    series: [{
      data: patientGrowthData.map(d => d.patients),
      type: 'line',
      smooth: true,
      itemStyle: { color: '#0891b2' },
      areaStyle: { color: 'rgba(8, 145, 178, 0.1)' }
    }]
  };

  const encountersByTypeChart = {
    title: {
      text: 'Encounters by Type',
      textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' }
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle'
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      data: encountersByTypeData.map((item, idx) => ({
        value: item.value,
        name: item.type,
        itemStyle: {
          color: ['#0891b2', '#14b8a6', '#06b6d4', '#22d3ee', '#67e8f9'][idx]
        }
      }))
    }]
  };

  const revenueChart = {
    title: {
      text: 'Revenue Trend',
      textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' }
    },
    tooltip: {
      trigger: 'axis',
      formatter: 'R{c0}'
    },
    xAxis: {
      type: 'category',
      data: revenueData.map(d => d.month)
    },
    yAxis: {
      type: 'value',
      name: 'Revenue (ZAR)',
      axisLabel: {
        formatter: 'R{value}'
      }
    },
    series: [{
      data: revenueData.map(d => d.revenue),
      type: 'bar',
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#14b8a6' },
          { offset: 1, color: '#0891b2' }
        ])
      }
    }]
  };

  const topDiagnosesChart = {
    title: {
      text: 'Top 5 Diagnoses',
      textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    xAxis: {
      type: 'value',
      name: 'Patients'
    },
    yAxis: {
      type: 'category',
      data: topDiagnosesData.map(d => d.diagnosis).reverse()
    },
    series: [{
      data: topDiagnosesData.map(d => d.count).reverse(),
      type: 'bar',
      itemStyle: { color: '#0891b2' }
    }]
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-16 h-16 border-4 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="analytics-container">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-slate-800 mb-2">Practice Analytics</h1>
        <p className="text-slate-600">Comprehensive insights into your practice performance</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="border-0 shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-600 flex items-center gap-2">
              <Users className="w-4 h-4" />
              Total Patients
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-800">{stats.total_patients}</div>
            <p className="text-xs text-teal-600 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" />
              +12% from last month
            </p>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-600 flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Total Encounters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-800">{stats.total_encounters}</div>
            <p className="text-xs text-teal-600 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" />
              +8% from last month
            </p>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-600 flex items-center gap-2">
              <DollarSign className="w-4 h-4" />
              Monthly Revenue
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-800">R{stats.total_revenue.toFixed(0)}</div>
            <p className="text-xs text-teal-600 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" />
              +15% from last month
            </p>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-600 flex items-center gap-2">
              <HeartPulse className="w-4 h-4" />
              Active Conditions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-800">342</div>
            <p className="text-xs text-slate-500 mt-1">Chronic disease patients</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-0 shadow-lg">
          <CardContent className="pt-6">
            <ReactECharts option={patientGrowthChart} style={{ height: '350px' }} />
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg">
          <CardContent className="pt-6">
            <ReactECharts option={encountersByTypeChart} style={{ height: '350px' }} />
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-0 shadow-lg">
          <CardContent className="pt-6">
            <ReactECharts option={revenueChart} style={{ height: '350px' }} />
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg">
          <CardContent className="pt-6">
            <ReactECharts option={topDiagnosesChart} style={{ height: '350px' }} />
          </CardContent>
        </Card>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-teal-600" />
              Appointment Stats
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Average per day</span>
              <span className="font-bold text-slate-800">18</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">No-show rate</span>
              <span className="font-bold text-red-600">5.2%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Cancellation rate</span>
              <span className="font-bold text-amber-600">8.7%</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <Pill className="w-5 h-5 text-teal-600" />
              Prescription Stats
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Total prescriptions</span>
              <span className="font-bold text-slate-800">1,247</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Avg per encounter</span>
              <span className="font-bold text-slate-800">2.3</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Refill requests</span>
              <span className="font-bold text-teal-600">156</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <FileText className="w-5 h-5 text-teal-600" />
              Documentation Stats
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Documents digitized</span>
              <span className="font-bold text-slate-800">842</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Pending validation</span>
              <span className="font-bold text-amber-600">23</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Completion rate</span>
              <span className="font-bold text-emerald-600">97.3%</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Analytics;
