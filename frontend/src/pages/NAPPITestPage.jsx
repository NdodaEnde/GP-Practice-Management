import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Package, AlertCircle, Info } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

const NAPPITestPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedSchedule, setSelectedSchedule] = useState('');

  // Load stats on mount
  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/nappi/stats`);
      setStats(response.data);
    } catch (err) {
      console.error('Error loading NAPPI stats:', err);
      setError('Database not initialized. Please run the migration first.');
    }
  };

  const handleSearch = async (queryOverride = null) => {
    const searchTerm = queryOverride || searchQuery;
    
    if (!searchTerm.trim() || searchTerm.length < 2) {
      setError('Please enter at least 2 characters');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const params = {
        query: searchTerm,
        limit: 20
      };
      
      if (selectedSchedule) {
        params.schedule = selectedSchedule;
      }

      const response = await axios.get(`${BACKEND_URL}/api/nappi/search`, { params });
      setSearchResults(response.data.results || []);
      
      if (response.data.results.length === 0) {
        setError('No medications found matching your search');
      }
    } catch (err) {
      console.error('Search error:', err);
      setError(err.response?.data?.detail || 'Error searching NAPPI codes. Database may not be initialized.');
    } finally {
      setLoading(false);
    }
  };

  const getScheduleBadgeColor = (schedule) => {
    const colors = {
      'S0': 'bg-green-100 text-green-800',
      'S1': 'bg-blue-100 text-blue-800',
      'S2': 'bg-yellow-100 text-yellow-800',
      'S3': 'bg-orange-100 text-orange-800',
      'S4': 'bg-red-100 text-red-800',
      'S5': 'bg-purple-100 text-purple-800',
      'S6': 'bg-gray-700 text-white',
      'Unscheduled': 'bg-gray-100 text-gray-600'
    };
    return colors[schedule] || 'bg-gray-100 text-gray-600';
  };

  const quickSearches = ['paracetamol', 'ibuprofen', 'amoxicillin', 'panado', 'grandpa', 'metformin'];

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Package className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">NAPPI Code Lookup</h1>
        </div>
        <p className="text-gray-600">
          Search the National Pharmaceutical Product Interface database for South African medications
        </p>
      </div>

      {/* Stats Card */}
      {stats && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Database Statistics</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-3xl font-bold text-blue-600">{stats.total_codes?.toLocaleString()}</div>
              <div className="text-sm text-gray-600">Total Medications</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-green-600">{stats.active_codes?.toLocaleString()}</div>
              <div className="text-sm text-gray-600">Active Products</div>
            </div>
            <div className="col-span-2">
              <div className="text-sm font-semibold text-gray-700 mb-2">By Schedule:</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(stats.by_schedule || {}).map(([schedule, count]) => (
                  <span key={schedule} className={`px-2 py-1 rounded text-xs font-medium ${getScheduleBadgeColor(schedule)}`}>
                    {schedule}: {count}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Database Not Initialized Warning */}
      {!stats && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
          <div className="flex">
            <AlertCircle className="w-5 h-5 text-yellow-400 mr-3" />
            <div>
              <h3 className="text-sm font-medium text-yellow-800">Database Not Initialized</h3>
              <div className="text-sm text-yellow-700 mt-1">
                <p>The NAPPI codes table needs to be created first:</p>
                <ol className="list-decimal ml-5 mt-2 space-y-1">
                  <li>Open Supabase Dashboard → SQL Editor</li>
                  <li>Copy /app/backend/database/nappi_codes_migration.sql</li>
                  <li>Execute the migration</li>
                  <li>Load data: python load_nappi_codes.py nappi_sample_data.csv</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search Section */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Search className="w-5 h-5" />
          Search NAPPI Codes
        </h2>
        
        <div className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Enter brand name, generic name, or ingredient..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <select
              value={selectedSchedule}
              onChange={(e) => setSelectedSchedule(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Schedules</option>
              <option value="S0">S0 - OTC</option>
              <option value="S1">S1 - Pharmacy Medicine</option>
              <option value="S2">S2 - Pharmacy Only</option>
              <option value="S3">S3 - Prescription</option>
              <option value="S4">S4 - Prescription (Restricted)</option>
              <option value="S5">S5 - Controlled Substance</option>
              <option value="S6">S6 - Highly Restricted</option>
            </select>
            <button
              onClick={handleSearch}
              disabled={loading || !searchQuery.trim()}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? 'Searching...' : 'Search'}
              <Search className="w-4 h-4" />
            </button>
          </div>

          {/* Quick Search Buttons */}
          <div className="flex flex-wrap gap-2">
            <span className="text-sm text-gray-600 mr-2">Quick search:</span>
            {quickSearches.map((term) => (
              <button
                key={term}
                onClick={() => { setSearchQuery(term); setTimeout(handleSearch, 100); }}
                className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200"
              >
                {term}
              </button>
            ))}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-red-700">{error}</div>
          </div>
        )}
      </div>

      {/* Results */}
      {searchResults.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">
            Search Results ({searchResults.length} medications)
          </h2>
          
          <div className="space-y-3">
            {searchResults.map((medication) => (
              <div key={medication.nappi_code} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-sm font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded">
                        {medication.nappi_code}
                      </span>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getScheduleBadgeColor(medication.schedule)}`}>
                        {medication.schedule}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-1">
                      {medication.brand_name}
                    </h3>
                    <p className="text-sm text-gray-600 mb-1">
                      <span className="font-medium">Generic:</span> {medication.generic_name}
                    </p>
                    {medication.strength && (
                      <p className="text-sm text-gray-600 mb-1">
                        <span className="font-medium">Strength:</span> {medication.strength}
                      </p>
                    )}
                    {medication.ingredients && (
                      <p className="text-sm text-gray-600">
                        <span className="font-medium">Ingredients:</span> {medication.ingredients}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Info Section */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-900">
            <p className="font-semibold mb-2">About NAPPI Codes</p>
            <p>
              NAPPI (National Pharmaceutical Product Interface) codes are South Africa's standard system 
              for identifying pharmaceutical products. Each code uniquely identifies a specific medication 
              by brand, strength, and dosage form, enabling accurate prescribing and medical aid claims processing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NAPPITestPage;
