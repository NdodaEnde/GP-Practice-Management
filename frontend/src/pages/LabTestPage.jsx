import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { TestTube, Plus, AlertCircle, TrendingUp, CheckCircle, Clock } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const LabTestPage = () => {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState('');
  const [labOrders, setLabOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  
  // Form states
  const [orderForm, setOrderForm] = useState({
    lab_name: 'PathCare',
    ordering_provider: 'Dr. Smith',
    priority: 'routine',
    indication: ''
  });
  
  const [resultForm, setResultForm] = useState({
    order_id: '',
    test_name: '',
    result_value: '',
    result_numeric: '',
    units: '',
    reference_range: '',
    reference_low: '',
    reference_high: ''
  });

  // Load patients on mount
  useEffect(() => {
    loadPatients();
  }, []);

  // Load orders when patient selected
  useEffect(() => {
    if (selectedPatient) {
      loadPatientOrders();
    }
  }, [selectedPatient]);

  const loadPatients = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/patients`);
      setPatients(response.data || []);
    } catch (error) {
      console.error('Error loading patients:', error);
    }
  };

  const loadPatientOrders = async () => {
    if (!selectedPatient) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/lab-orders/patient/${selectedPatient}`);
      setLabOrders(response.data || []);
      
      // Load results for each order
      const ordersWithResults = await Promise.all(
        response.data.map(async (order) => {
          try {
            const resultsResponse = await axios.get(`${BACKEND_URL}/api/lab-results/order/${order.id}`);
            return { ...order, results: resultsResponse.data || [] };
          } catch (error) {
            return { ...order, results: [] };
          }
        })
      );
      setLabOrders(ordersWithResults);
    } catch (error) {
      showMessage('error', 'Error loading lab orders');
    } finally {
      setLoading(false);
    }
  };

  const createLabOrder = async (e) => {
    e.preventDefault();
    if (!selectedPatient) {
      showMessage('error', 'Please select a patient first');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/lab-orders`, {
        patient_id: selectedPatient,
        ...orderForm
      });
      
      showMessage('success', 'Lab order created successfully!');
      setOrderForm({
        lab_name: 'PathCare',
        ordering_provider: 'Dr. Smith',
        priority: 'routine',
        indication: ''
      });
      loadPatientOrders();
    } catch (error) {
      showMessage('error', error.response?.data?.detail || 'Error creating lab order');
    } finally {
      setLoading(false);
    }
  };

  const addLabResult = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const data = {
        lab_order_id: resultForm.order_id,
        test_name: resultForm.test_name,
        result_value: resultForm.result_value,
        units: resultForm.units,
        reference_range: resultForm.reference_range
      };
      
      if (resultForm.result_numeric) {
        data.result_numeric = parseFloat(resultForm.result_numeric);
      }
      if (resultForm.reference_low) {
        data.reference_low = parseFloat(resultForm.reference_low);
      }
      if (resultForm.reference_high) {
        data.reference_high = parseFloat(resultForm.reference_high);
      }
      
      await axios.post(`${BACKEND_URL}/api/lab-results`, data);
      
      showMessage('success', 'Lab result added successfully!');
      setResultForm({
        order_id: '',
        test_name: '',
        result_value: '',
        result_numeric: '',
        units: '',
        reference_range: '',
        reference_low: '',
        reference_high: ''
      });
      loadPatientOrders();
    } catch (error) {
      showMessage('error', error.response?.data?.detail || 'Error adding lab result');
    } finally {
      setLoading(false);
    }
  };

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 5000);
  };

  const getStatusColor = (status) => {
    const colors = {
      'ordered': 'bg-blue-100 text-blue-800',
      'collected': 'bg-yellow-100 text-yellow-800',
      'received': 'bg-purple-100 text-purple-800',
      'in_progress': 'bg-orange-100 text-orange-800',
      'completed': 'bg-green-100 text-green-800',
      'cancelled': 'bg-gray-100 text-gray-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getAbnormalColor = (flag) => {
    const colors = {
      'normal': 'text-green-600',
      'low': 'text-orange-500',
      'high': 'text-orange-500',
      'critical_low': 'text-red-600 font-bold',
      'critical_high': 'text-red-600 font-bold',
      'abnormal': 'text-orange-500'
    };
    return colors[flag] || 'text-gray-600';
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <TestTube className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Lab Orders & Results</h1>
        </div>
        <p className="text-gray-600">Test laboratory orders, results, and trending system</p>
      </div>

      {/* Message Banner */}
      {message.text && (
        <div className={`mb-6 p-4 rounded-lg ${message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
          {message.text}
        </div>
      )}

      {/* Patient Selection */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Select Patient</h2>
        <select
          value={selectedPatient}
          onChange={(e) => setSelectedPatient(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value="">-- Select a patient --</option>
          {patients.map((patient) => (
            <option key={patient.id} value={patient.id}>
              {patient.first_name} {patient.last_name} ({patient.id_number})
            </option>
          ))}
        </select>
      </div>

      {selectedPatient && (
        <>
          {/* Create Lab Order Form */}
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <Plus className="w-5 h-5" />
              Create New Lab Order
            </h2>
            <form onSubmit={createLabOrder} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Lab Name</label>
                  <select
                    value={orderForm.lab_name}
                    onChange={(e) => setOrderForm({ ...orderForm, lab_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="PathCare">PathCare</option>
                    <option value="Lancet">Lancet</option>
                    <option value="Ampath">Ampath</option>
                    <option value="Vermaak">Vermaak</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Priority</label>
                  <select
                    value={orderForm.priority}
                    onChange={(e) => setOrderForm({ ...orderForm, priority: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="routine">Routine</option>
                    <option value="urgent">Urgent</option>
                    <option value="stat">STAT</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Ordering Provider</label>
                  <input
                    type="text"
                    value={orderForm.ordering_provider}
                    onChange={(e) => setOrderForm({ ...orderForm, ordering_provider: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Indication</label>
                  <input
                    type="text"
                    value={orderForm.indication}
                    onChange={(e) => setOrderForm({ ...orderForm, indication: e.target.value })}
                    placeholder="e.g., Annual check-up, diabetic monitoring"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
              >
                Create Lab Order
              </button>
            </form>
          </div>

          {/* Add Lab Result Form */}
          {labOrders.length > 0 && (
            <div className="bg-white rounded-lg shadow-md p-6 mb-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Plus className="w-5 h-5" />
                Add Lab Result
              </h2>
              <form onSubmit={addLabResult} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Select Order</label>
                    <select
                      value={resultForm.order_id}
                      onChange={(e) => setResultForm({ ...resultForm, order_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      required
                    >
                      <option value="">-- Select lab order --</option>
                      {labOrders.map((order) => (
                        <option key={order.id} value={order.id}>
                          {order.order_number || order.id.substring(0, 8)} - {order.lab_name} ({order.status})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Test Name</label>
                    <input
                      type="text"
                      value={resultForm.test_name}
                      onChange={(e) => setResultForm({ ...resultForm, test_name: e.target.value })}
                      placeholder="e.g., HbA1c, Total Cholesterol"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Result Value</label>
                    <input
                      type="text"
                      value={resultForm.result_value}
                      onChange={(e) => setResultForm({ ...resultForm, result_value: e.target.value })}
                      placeholder="e.g., 7.2"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Numeric Value (for trending)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={resultForm.result_numeric}
                      onChange={(e) => setResultForm({ ...resultForm, result_numeric: e.target.value })}
                      placeholder="7.2"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Units</label>
                    <input
                      type="text"
                      value={resultForm.units}
                      onChange={(e) => setResultForm({ ...resultForm, units: e.target.value })}
                      placeholder="%, mmol/L, mg/dL"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Reference Range</label>
                    <input
                      type="text"
                      value={resultForm.reference_range}
                      onChange={(e) => setResultForm({ ...resultForm, reference_range: e.target.value })}
                      placeholder="e.g., <5.7 or 3.5-5.5"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Reference Low</label>
                    <input
                      type="number"
                      step="0.01"
                      value={resultForm.reference_low}
                      onChange={(e) => setResultForm({ ...resultForm, reference_low: e.target.value })}
                      placeholder="3.5"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Reference High</label>
                    <input
                      type="number"
                      step="0.01"
                      value={resultForm.reference_high}
                      onChange={(e) => setResultForm({ ...resultForm, reference_high: e.target.value })}
                      placeholder="5.5"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300"
                >
                  Add Result
                </button>
              </form>
            </div>
          )}

          {/* Lab Orders List */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Lab Orders & Results</h2>
            
            {loading ? (
              <div className="text-center py-8">
                <Clock className="w-8 h-8 animate-spin mx-auto mb-2 text-blue-600" />
                <p>Loading...</p>
              </div>
            ) : labOrders.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <TestTube className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No lab orders yet. Create one above to get started.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {labOrders.map((order) => (
                  <div key={order.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-3 mb-1">
                          <span className="font-mono text-sm text-gray-500">
                            {order.order_number || order.id.substring(0, 8)}
                          </span>
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(order.status)}`}>
                            {order.status}
                          </span>
                        </div>
                        <h3 className="font-semibold text-lg">{order.lab_name}</h3>
                        <p className="text-sm text-gray-600">
                          Ordered by {order.ordering_provider} • {new Date(order.order_datetime).toLocaleDateString()}
                        </p>
                        {order.indication && (
                          <p className="text-sm text-gray-600 mt-1">
                            <span className="font-medium">Indication:</span> {order.indication}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Results */}
                    {order.results && order.results.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-gray-200">
                        <h4 className="font-semibold mb-2 flex items-center gap-2">
                          <TestTube className="w-4 h-4" />
                          Results ({order.results.length})
                        </h4>
                        <div className="space-y-2">
                          {order.results.map((result) => (
                            <div key={result.id} className="flex items-center justify-between bg-gray-50 p-3 rounded">
                              <div className="flex-1">
                                <span className="font-medium">{result.test_name}</span>
                              </div>
                              <div className="text-right">
                                <span className={`text-lg font-semibold ${getAbnormalColor(result.abnormal_flag)}`}>
                                  {result.result_value} {result.units}
                                </span>
                                {result.reference_range && (
                                  <div className="text-xs text-gray-500">
                                    Ref: {result.reference_range}
                                  </div>
                                )}
                                {result.abnormal_flag !== 'normal' && result.abnormal_flag !== 'unknown' && (
                                  <div className={`text-xs font-medium ${getAbnormalColor(result.abnormal_flag)}`}>
                                    {result.abnormal_flag.toUpperCase().replace('_', ' ')}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default LabTestPage;
