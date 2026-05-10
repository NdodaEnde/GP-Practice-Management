import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  // Check for existing auth on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('access_token');
      
      if (token) {
        // Verify token with backend
        const response = await axios.get(`${backendUrl}/api/auth/me`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.data.status === 'success') {
          setUser(response.data.user);
          setIsAuthenticated(true);
        } else {
          // Token invalid
          logout();
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      // Token invalid or expired
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${backendUrl}/api/auth/login`, {
        email,
        password
      });

      const { access_token, refresh_token, user: userData } = response.data;

      // Store tokens
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Set user data
      setUser(userData);
      setIsAuthenticated(true);

      return { success: true, user: userData };
    } catch (error) {
      console.error('Login failed:', error);
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed'
      };
    }
  };

  const logout = async () => {
    try {
      const token = localStorage.getItem('access_token');
      
      if (token) {
        // Call logout endpoint (for logging purposes)
        await axios.post(
          `${backendUrl}/api/auth/logout`,
          {},
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local storage
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      
      // Clear state
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  const refreshToken = async () => {
    try {
      const refresh_token = localStorage.getItem('refresh_token');
      
      if (!refresh_token) {
        throw new Error('No refresh token');
      }

      const response = await axios.post(`${backendUrl}/api/auth/refresh`, {
        refresh_token
      });

      const { access_token } = response.data;
      localStorage.setItem('access_token', access_token);

      return access_token;
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
      return null;
    }
  };

  // Capability check — pure JS membership against user.capabilities (hydrated
  // by /api/auth/me). Use this in components to render gated UX:
  //   const { hasCapability } = useAuth();
  //   if (!hasCapability('ai_scribe')) return <UpsellCard ... />;
  const hasCapability = (capabilityId) => {
    return Array.isArray(user?.capabilities) && user.capabilities.includes(capabilityId);
  };

  // Multi-practice support (TRACEABILITY §11). switchWorkspace mints a
  // fresh JWT bound to the target workspace, swaps tokens in localStorage,
  // and rehydrates user state. Caller is expected to refresh page-level
  // data after; the simplest UX is a soft window.location.reload().
  const switchWorkspace = async (workspace_id) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${backendUrl}/api/auth/switch-workspace`,
        { workspace_id },
        { headers: { 'Authorization': `Bearer ${token}` } },
      );
      const { access_token, refresh_token, user: newUser } = response.data;
      localStorage.setItem('access_token',  access_token);
      localStorage.setItem('refresh_token', refresh_token);
      setUser(newUser);
      return { success: true, user: newUser };
    } catch (error) {
      console.error('switchWorkspace failed:', error);
      return {
        success: false,
        error: error.response?.data?.detail || 'Switch failed',
      };
    }
  };

  const value = {
    user,
    loading,
    isAuthenticated,
    login,
    logout,
    refreshToken,
    checkAuth,
    hasCapability,
    switchWorkspace,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Axios interceptor to add auth token to requests
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Axios interceptor to handle 401 errors and refresh token
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(
            `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api/auth/refresh`,
            { refresh_token: refreshToken }
          );

          const { access_token } = response.data;
          localStorage.setItem('access_token', access_token);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return axios(originalRequest);
        } catch (refreshError) {
          // Refresh failed, logout user
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      }
    }

    return Promise.reject(error);
  }
);

export default AuthContext;
