import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ArrowLeft, KeyRound, CheckCircle, AlertCircle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import api from '@/services/api';

/**
 * ChangePassword — lets a logged-in user rotate their password.
 * Calls POST /api/auth/change-password (verifies current, sets new bcrypt hash).
 * Server enforces: 401 on wrong current, 400 on too-short / unchanged.
 */
const ChangePassword = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const clientCheck = () => {
    if (newPwd.length < 8) return 'New password must be at least 8 characters.';
    if (newPwd !== confirmPwd) return 'New password and confirmation do not match.';
    if (newPwd === currentPwd) return 'New password must differ from current password.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const err = clientCheck();
    if (err) {
      toast({ title: 'Validation', description: err, variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/auth/change-password', {
        current_password: currentPwd,
        new_password: newPwd,
      });
      setSuccess(true);
      toast({ title: 'Password changed', description: 'Your password has been updated.' });
      setCurrentPwd(''); setNewPwd(''); setConfirmPwd('');
    } catch (error) {
      const detail = error.response?.data?.detail || 'Failed to change password.';
      toast({ title: 'Error', description: detail, variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto py-8 animate-fade-in">
      <Link to="/dashboard" className="inline-flex items-center text-teal-600 hover:text-teal-700 mb-4">
        <ArrowLeft className="w-4 h-4 mr-2" />Back to Dashboard
      </Link>
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <KeyRound className="w-6 h-6 text-teal-600" />
            Change Password
          </CardTitle>
          <p className="text-sm text-slate-600 mt-1">
            Rotate the password you were issued at onboarding. Pick something strong (8+ characters).
          </p>
        </CardHeader>
        <CardContent>
          {success && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-emerald-600 mt-0.5" />
              <p className="text-sm text-emerald-800">
                Password changed successfully. Use your new password the next time you log in.
              </p>
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="current">Current password</Label>
              <Input id="current" type="password" autoComplete="current-password"
                value={currentPwd} onChange={(e) => setCurrentPwd(e.target.value)} required />
            </div>
            <div>
              <Label htmlFor="new">New password</Label>
              <Input id="new" type="password" autoComplete="new-password" minLength={8}
                value={newPwd} onChange={(e) => setNewPwd(e.target.value)} required />
              <p className="text-xs text-slate-500 mt-1">Minimum 8 characters.</p>
            </div>
            <div>
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input id="confirm" type="password" autoComplete="new-password"
                value={confirmPwd} onChange={(e) => setConfirmPwd(e.target.value)} required />
              {confirmPwd && newPwd !== confirmPwd && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />Passwords do not match.
                </p>
              )}
            </div>
            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={submitting || !currentPwd || !newPwd || !confirmPwd}
                className="bg-teal-600 hover:bg-teal-700 text-white">
                {submitting ? 'Changing…' : 'Change password'}
              </Button>
              <Button type="button" variant="outline" onClick={() => navigate('/dashboard')}>
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default ChangePassword;
