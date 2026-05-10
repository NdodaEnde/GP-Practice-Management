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
  const [operationalData, setOperationalData] = useState(null);
  const [clinicalData, setClinicalData] = useState(null);
  const [financialData, setFinancialData] = useState(null);
  const [medicationsData, setMedicationsData] = useState(null);

  useEffect(() => {
    loadAllAnalytics();
  }, []);

  const loadAllAnalytics = async () => {
    try {
      setLoading(true);
      const [summaryRes, operationalRes, clinicalRes, financialRes, medicationsRes] = await Promise.all([
        analyticsAPI.getSummary(),
        analyticsAPI.getOperational(),
        analyticsAPI.getClinical(),
        analyticsAPI.getFinancial(),
        analyticsAPI.getMedications(365).catch(() => ({ data: null })),
      ]);

      setStats(summaryRes.data);
      setOperationalData(operationalRes.data);
      setClinicalData(clinicalRes.data);
      setFinancialData(financialRes.data);
      setMedicationsData(medicationsRes.data);
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

  // Use real data if available, otherwise use mock data
  // Check if we have meaningful data (not empty arrays)
  const patientGrowthData = (operationalData?.patient_growth && operationalData.patient_growth.length > 1)
    ? operationalData.patient_growth.map(item => ({
        month: item.month.substring(5), // Get MM from YYYY-MM
        patients: item.count
      }))
    : [
        { month: 'Jul', patients: 45 },
        { month: 'Aug', patients: 58 },
        { month: 'Sep', patients: 72 },
        { month: 'Oct', patients: 89 },
        { month: 'Nov', patients: 105 },
        { month: 'Dec', patients: 128 },
        { month: 'Jan', patients: 156 },
      ];

  const revenueData = (financialData?.revenue_by_month && financialData.revenue_by_month.length > 0)
    ? financialData.revenue_by_month.map(item => ({
        month: item.month.substring(5),
        revenue: item.revenue
      }))
    : [
        { month: 'Jul', revenue: 45000 },
        { month: 'Aug', revenue: 52000 },
        { month: 'Sep', revenue: 48000 },
        { month: 'Oct', revenue: 61000 },
        { month: 'Nov', revenue: 58000 },
        { month: 'Dec', revenue: 67000 },
        { month: 'Jan', revenue: 73000 },
      ];

  const topDiagnosesData = (clinicalData?.top_diagnoses && clinicalData.top_diagnoses.length > 0)
    ? clinicalData.top_diagnoses
    : [
        { diagnosis: 'Hypertension', count: 89 },
        { diagnosis: 'Type 2 Diabetes', count: 76 },
        { diagnosis: 'Upper Respiratory Infection', count: 64 },
        { diagnosis: 'Asthma', count: 52 },
        { diagnosis: 'Anxiety Disorder', count: 41 },
      ];

  const payerTypeData = financialData?.revenue_by_payer?.map((item, idx) => ({
    type: item.payer_type.replace('_', ' ').toUpperCase(),
    value: item.revenue
  })) || [
    { type: 'Cash', value: 45000 },
    { type: 'Medical Aid', value: 89000 },
    { type: 'Corporate', value: 23000 },
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

  const payerTypeChart = {
    title: {
      text: 'Revenue by Payer Type',
      textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' }
    },
    tooltip: {
      trigger: 'item',
      formatter: 'R{c} ({d}%)'
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
      data: payerTypeData.map((item, idx) => ({
        value: item.value,
        name: item.type,
        itemStyle: {
          color: ['#0891b2', '#14b8a6', '#06b6d4'][idx]
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

  // ATC anatomical-group distribution (donut). Uses real backfilled data
  // from nappi_codes.atc_code (TRACEABILITY 6b/6c).
  const atcAnatomical = medicationsData?.by_atc_anatomical || [];
  const atcClasses    = medicationsData?.by_atc_class || [];
  const atcCoverage   = medicationsData?.atc_coverage_pct ?? 0;

  const atcAnatomicalChart = {
    title: {
      text: 'Prescribing by ATC anatomical group',
      subtext: `Coverage: ${atcCoverage}% of NAPPI-coded items have an ATC class`,
      textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' },
      subtextStyle: { fontSize: 11, color: '#64748b' },
    },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'horizontal', bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '48%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: atcAnatomical.map(g => ({ name: g.group_name, value: g.count })),
    }],
  };

  const atcClassesChart = {
    title: {
      text: 'Top 15 therapeutic classes (ATC level-3)',
      textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params[0];
        const cls = atcClasses[atcClasses.length - 1 - p.dataIndex];
        const sub = cls?.sample_substance ? `<br/><span style="color:#64748b">e.g. ${cls.sample_substance}</span>` : '';
        return `<b>${p.name}</b>: ${p.value} items${sub}`;
      },
    },
    grid: { left: '20%', right: '5%', top: 50, bottom: 20 },
    xAxis: { type: 'value', name: 'Items' },
    yAxis: {
      type: 'category',
      data: atcClasses.map(c => c.atc_class_code).reverse(),
      axisLabel: { fontSize: 11 },
    },
    series: [{
      data: atcClasses.map(c => c.count).reverse(),
      type: 'bar',
      itemStyle: { color: '#0d9488', borderRadius: [0, 4, 4, 0] },
    }],
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
            <div className="text-xs text-teal-600 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" />
              +12% from last month
            </div>
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
            <div className="text-xs text-teal-600 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" />
              +8% from last month
            </div>
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
            <div className="text-xs text-teal-600 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" />
              +15% from last month
            </div>
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
            <ReactECharts option={payerTypeChart} style={{ height: '350px' }} />
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

      {/* Charts Row 3 — ATC drug-class breakdown (TRACEABILITY 6b/6c) */}
      {atcAnatomical.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="atc-class-row">
          <Card className="border-0 shadow-lg">
            <CardContent className="pt-6">
              <ReactECharts option={atcAnatomicalChart} style={{ height: '380px' }} />
            </CardContent>
          </Card>

          <Card className="border-0 shadow-lg">
            <CardContent className="pt-6">
              <ReactECharts option={atcClassesChart} style={{ height: '380px' }} />
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card className="border-0 shadow-lg">
          <CardContent className="pt-6 text-center text-slate-500">
            <Pill className="w-8 h-8 mx-auto mb-2 text-slate-400" />
            <p className="font-medium text-slate-700">Drug-class analytics</p>
            <p className="text-sm">No ATC-coded prescriptions in the last 90 days yet. Codes appear here once prescriptions reference NAPPI rows that have an <code>atc_code</code> assigned.</p>
          </CardContent>
        </Card>
      )}

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
