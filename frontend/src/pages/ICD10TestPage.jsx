import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, Sparkles, Loader2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';

const ICD10TestPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [diagnosisText, setDiagnosisText] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [aiSuggestions, setAiSuggestions] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const { toast } = useToast();

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  // Load stats on mount
  React.useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const response = await axios.get(`${backendUrl}/api/icd10/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const handleKeywordSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery || searchQuery.length < 2) {
      toast({
        title: 'Error',
        description: 'Please enter at least 2 characters',
        variant: 'destructive'
      });
      return;
    }

    try {
      setSearchLoading(true);
      const response = await axios.get(
        `${backendUrl}/api/icd10/search?query=${encodeURIComponent(searchQuery)}&limit=10`
      );
      setSearchResults(response.data);
      toast({
        title: 'Success',
        description: `Found ${response.data.length} results`
      });
    } catch (error) {
      console.error('Search error:', error);
      toast({
        title: 'Error',
        description: 'Search failed',
        variant: 'destructive'
      });
    } finally {
      setSearchLoading(false);
    }
  };

  const handleAISuggest = async (e) => {
    e.preventDefault();
    if (!diagnosisText || diagnosisText.length < 5) {
      toast({
        title: 'Error',
        description: 'Please enter at least 5 characters',
        variant: 'destructive'
      });
      return;
    }

    try {
      setAiLoading(true);
      const response = await axios.get(
        `${backendUrl}/api/icd10/suggest?diagnosis_text=${encodeURIComponent(diagnosisText)}&max_suggestions=5`
      );
      setAiSuggestions(response.data);
      toast({
        title: 'AI Suggestions Ready',
        description: `Got ${response.data.suggestions?.length || 0} suggestions`,
        className: 'bg-purple-50'
      });
    } catch (error) {
      console.error('AI suggest error:', error);
      toast({
        title: 'Error',
        description: 'AI suggestion failed',
        variant: 'destructive'
      });
    } finally {
      setAiLoading(false);
    }
  };

  const quickSearchExamples = [
    'diabetes',
    'hypertension',
    'asthma',
    'pneumonia',
    'covid'
  ];

  const aiExamples = [
    'Patient has high blood sugar and frequent urination',
    'Chest pain with shortness of breath',
    'Persistent cough for 3 weeks with fever',
    'Lower back pain radiating to leg'
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-gradient-to-r from-teal-600 to-blue-600 text-white rounded-lg p-6 shadow-lg">
          <h1 className="text-3xl font-bold mb-2">ICD-10 Code Lookup Test Page</h1>
          <p className="text-teal-50">Test fast keyword search and AI-powered code suggestions</p>
        </div>

        {/* Statistics */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-teal-600">{stats.total_codes.toLocaleString()}</div>
                  <div className="text-sm text-gray-600 mt-1">Total ICD-10 Codes</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-600">{stats.clinical_use_codes.toLocaleString()}</div>
                  <div className="text-sm text-gray-600 mt-1">Clinical Use Codes</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-purple-600">{stats.primary_diagnosis_codes.toLocaleString()}</div>
                  <div className="text-sm text-gray-600 mt-1">Primary Diagnosis Codes</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Keyword Search */}
        <Card className="border-2 border-teal-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="w-5 h-5 text-teal-600" />
              1. Fast Keyword Search
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleKeywordSearch} className="space-y-3">
              <div>
                <Input
                  placeholder="Type disease name or symptoms (e.g., diabetes, chest pain)"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="text-lg"
                />
              </div>
              <div className="flex gap-2 flex-wrap">
                <span className="text-sm text-gray-600">Quick examples:</span>
                {quickSearchExamples.map((example) => (
                  <Button
                    key={example}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSearchQuery(example);
                    }}
                  >
                    {example}
                  </Button>
                ))}
              </div>
              <Button type="submit" disabled={searchLoading} className="w-full">
                {searchLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 mr-2" />
                    Search ICD-10 Codes
                  </>
                )}
              </Button>
            </form>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="mt-4 space-y-2">
                <h3 className="font-semibold text-gray-700">Results ({searchResults.length}):</h3>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {searchResults.map((code) => (
                    <div
                      key={code.code}
                      className="p-3 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100"
                    >
                      <div className="flex items-start gap-3">
                        <Badge className="bg-teal-600 text-white">{code.code}</Badge>
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">{code.who_full_desc}</p>
                          <p className="text-sm text-gray-600 mt-1">
                            Chapter: {code.chapter_desc}
                          </p>
                          {code.group_desc && (
                            <p className="text-xs text-gray-500">Group: {code.group_desc}</p>
                          )}
                        </div>
                        {code.valid_primary && (
                          <Badge variant="outline" className="text-green-700 border-green-700">
                            Primary
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* AI-Powered Suggestions */}
        <Card className="border-2 border-purple-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-600" />
              2. AI-Powered Code Suggestions (GPT-4)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleAISuggest} className="space-y-3">
              <div>
                <textarea
                  placeholder="Describe the patient's condition in natural language..."
                  value={diagnosisText}
                  onChange={(e) => setDiagnosisText(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-base"
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <span className="text-sm text-gray-600">Try these examples:</span>
                {aiExamples.map((example, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setDiagnosisText(example)}
                    className="block w-full text-left px-3 py-2 text-sm bg-purple-50 hover:bg-purple-100 rounded border border-purple-200"
                  >
                    {example}
                  </button>
                ))}
              </div>
              <Button type="submit" disabled={aiLoading} className="w-full bg-purple-600 hover:bg-purple-700">
                {aiLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    AI is thinking...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Get AI Suggestions
                  </>
                )}
              </Button>
            </form>

            {/* AI Suggestions Results */}
            {aiSuggestions && (
              <div className="mt-4 space-y-3">
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                  <p className="text-sm text-purple-800">
                    <strong>AI Response:</strong> {aiSuggestions.ai_response}
                  </p>
                </div>
                
                {aiSuggestions.suggestions && aiSuggestions.suggestions.length > 0 ? (
                  <>
                    <h3 className="font-semibold text-gray-700">
                      Suggested Codes ({aiSuggestions.suggestions.length}):
                    </h3>
                    <div className="space-y-2">
                      {aiSuggestions.suggestions.map((code) => (
                        <div
                          key={code.code}
                          className="p-4 bg-purple-50 border-2 border-purple-300 rounded-lg"
                        >
                          <div className="flex items-start gap-3">
                            <Badge className="bg-purple-600 text-white text-base px-3 py-1">
                              {code.code}
                            </Badge>
                            <div className="flex-1">
                              <p className="font-semibold text-gray-900 text-base">
                                {code.who_full_desc}
                              </p>
                              <p className="text-sm text-gray-600 mt-1">
                                {code.chapter_desc}
                              </p>
                              {code.code_3char_desc && (
                                <p className="text-xs text-gray-500 mt-1">
                                  Category: {code.code_3char_desc}
                                </p>
                              )}
                            </div>
                            {code.valid_primary && (
                              <Badge variant="outline" className="text-green-700 border-green-700">
                                Primary Diagnosis
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-gray-600 text-center py-4">
                    {aiSuggestions.note || 'No suggestions found'}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ICD10TestPage;
