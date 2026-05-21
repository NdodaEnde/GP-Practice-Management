import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import CapabilityUpsell from '@/components/CapabilityUpsell';

/**
 * ProtectedRoute guards rendered children behind three optional layers:
 *
 *   1. Authentication — redirects to /login if not signed in.
 *   2. Role check (legacy) — denies access if `requiredRole` doesn't match.
 *   3. Capability check (Phase 2) — renders an upsell card if the practice
 *      doesn't have the named capability granted via active entitlements.
 *
 * Capability gating is the v2 model. Role gating remains for the few admin
 * routes that depend on identity rather than entitlement (e.g. workspace
 * management).
 */
const ProtectedRoute = ({
  children,
  requiredRole = null,
  requiredCapability = null,
}) => {
  const { isAuthenticated, loading, user, hasCapability } = useAuth();
  const location = useLocation();

  // Show loading state while checking authentication
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-900 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role if required
  if (requiredRole && user?.role !== requiredRole) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md p-6">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">
            You don't have permission to access this page.
          </p>
          <p className="text-sm text-gray-500">
            Required role: <span className="font-semibold">{requiredRole}</span><br />
            Your role: <span className="font-semibold">{user?.role}</span>
          </p>
        </div>
      </div>
    );
  }

  // Capability check — render upsell rather than denial when missing.
  // The à la carte product model means the doctor knows exactly which
  // Module they would buy to unlock the feature.
  if (requiredCapability && !hasCapability(requiredCapability)) {
    return <CapabilityUpsell capability={requiredCapability} />;
  }

  // Render children if authenticated (and role/capability checks pass)
  return children;
};

export default ProtectedRoute;
