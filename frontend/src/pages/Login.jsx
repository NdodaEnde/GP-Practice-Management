import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { ScanLine, Lock, Mail, AlertCircle } from 'lucide-react';

const Login = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { login } = useAuth();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = await login(email, password);

      if (result.success) {
        toast({
          title: "Login Successful",
          description: `Welcome back, ${result.user.first_name}!`,
        });

        // Redirect by capability shape, not role. A Type C workspace only
        // bought Module 01 (Digitisation) — they have no EHR, so we land
        // them on the Digitisation Workspace, not the Healthcare dashboard.
        const caps = result.user.capabilities || [];
        const hasDigitisation = caps.includes('digitisation_upload');
        const hasEhr = caps.includes('patient_ehr_basic');

        // Capability-based landing only — never the legacy /digitization
        // or /document-upload screens. Digitisation-only tenants land on
        // the unified engine; full-practice tenants land on the EHR home
        // (whose nav now includes the SAME unified digitisation engine).
        if (hasEhr) {
          navigate('/dashboard');
        } else if (hasDigitisation) {
          navigate('/digitisation');
        } else {
          navigate('/dashboard');
        }
      } else {
        setError(result.error || 'Login failed');
        toast({
          title: "Login Failed",
          description: result.error || 'Invalid credentials',
          variant: "destructive"
        });
      }
    } catch (err) {
      setError('An unexpected error occurred');
      toast({
        title: "Error",
        description: "An unexpected error occurred",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = (role) => {
    if (role === 'admin') {
      setEmail('admin@surgiscan.com');
    } else if (role === 'validator') {
      setEmail('validator@surgiscan.com');
    } else if (role === 'uploader') {
      setEmail('uploader@surgiscan.com');
    }
    setPassword('password123');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo and Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-900 mb-4 shadow-sm">
            <ScanLine className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-blue-900 tracking-tight mb-1">SurgiScan</h1>
          <p className="text-slate-600 text-sm">Sign in to your practice</p>
        </div>

        {/* Login Card */}
        <Card className="shadow-xl">
          <CardHeader>
            <CardTitle className="text-2xl text-center">Sign In</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your.email@example.com"
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {/* Submit Button */}
              <Button
                type="submit"
                className="w-full bg-blue-900 hover:bg-blue-800 text-white"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Signing in...
                  </>
                ) : (
                  'Sign In'
                )}
              </Button>
            </form>

            {/* Demo Accounts */}
            <div className="mt-6 pt-6 border-t">
              <p className="text-sm text-gray-600 text-center mb-3">Demo Accounts (Development Only)</p>
              <div className="space-y-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start text-xs"
                  onClick={() => handleDemoLogin('admin')}
                >
                  <span className="font-semibold mr-2">Admin:</span> admin@surgiscan.com
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start text-xs"
                  onClick={() => handleDemoLogin('validator')}
                >
                  <span className="font-semibold mr-2">Validator:</span> validator@surgiscan.com
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start text-xs"
                  onClick={() => handleDemoLogin('uploader')}
                >
                  <span className="font-semibold mr-2">Uploader:</span> uploader@surgiscan.com
                </Button>
              </div>
              <p className="text-xs text-gray-500 text-center mt-2">
                Password for all demo accounts: <code className="bg-gray-100 px-2 py-1 rounded">password123</code>
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <p className="text-center text-sm text-slate-500 mt-6">
          © {new Date().getFullYear()} SurgiScan. POPIA-compliant. Built in South Africa.
        </p>
      </div>
    </div>
  );
};

export default Login;
