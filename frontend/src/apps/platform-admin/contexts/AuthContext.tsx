/**
 * Authentication Context for Gmail Lead Sync Web UI
 * 
 * Provides authentication state management and functions for:
 * - User login with username/password
 * - User logout with session invalidation
 * - Session persistence across page reloads
 * - Automatic redirect to login on authentication errors
 * 
 * Uses HTTP-only cookies for session management (backend handles this).
 * 
 * Requirements: 6.6, 23.3
 */

import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { flushSync } from 'react-dom';
import axios, { AxiosError } from 'axios';

// API base URL from environment variable
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// User type matching backend UserResponse model
export interface User {
  id: number;
  username: string;
  role: string;
  company_id: number | null;
}

// Authentication context state
interface AuthContextState {
  user: User | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

// Create context with undefined default (will be provided by AuthProvider)
const AuthContext = createContext<AuthContextState | undefined>(undefined);

// Props for AuthProvider component
interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Authentication Provider Component
 * 
 * Manages authentication state and provides login/logout functions.
 * Automatically checks for existing session on mount.
 * 
 * @param children - Child components to wrap with auth context
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const errorRef = useRef<string | null>(null);

  const setError = (msg: string | null) => {
    errorRef.current = msg;
  };

  /**
   * Configure axios to include credentials (cookies) in all requests
   */
  useEffect(() => {
    axios.defaults.withCredentials = true;
  }, []);

  /**
   * Check for existing session on mount
   * Calls /auth/me endpoint to validate session and get user info
   */
  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await axios.get<User>(`${API_BASE_URL}/auth/me`);
        setUser(response.data);
        setError(null);
      } catch {
        // No valid session - user needs to login
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    checkSession();
  }, []);

  /**
   * Login function
   * 
   * Authenticates user with username and password.
   * On success, sets user state and clears any errors.
   * On failure, sets error message.
   * 
   * @param username - Username to authenticate
   * @param password - Password to authenticate
   * @throws Error if login fails
   */
  const login = async (username: string, password: string): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post<{ user: User }>(
        `${API_BASE_URL}/auth/login`,
        { username, password }
      );

      setUser(response.data.user);
      setError(null);
      setLoading(false);
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string }>;
      const errorMessage = axiosError.response?.data?.message || 'Login failed. Please try again.';
      flushSync(() => {
        setUser(null);
        setError(errorMessage);
        setLoading(false);
      });
      throw new Error(errorMessage);
    }
  };

  /**
   * Logout function
   * 
   * Invalidates session on backend and clears user state.
   * Always clears user state even if backend call fails.
   */
  const logout = async (): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      await axios.post(`${API_BASE_URL}/auth/logout`);
    } catch (err) {
      // Log error but don't throw - we still want to clear local state
      console.error('Logout error:', err);
    } finally {
      setUser(null);
      setLoading(false);
    }
  };

  /**
   * Clear error message
   */
  const clearError = () => {
    setError(null);
  };

  const value: AuthContextState = {
    user,
    loading,
    error: errorRef.current,
    login,
    logout,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Custom hook to use authentication context
 * 
 * Must be used within an AuthProvider component.
 * 
 * @returns Authentication context state and functions
 * @throws Error if used outside AuthProvider
 */
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = (): AuthContextState => {
  const context = useContext(AuthContext);
  
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
};

/**
 * Axios interceptor to handle authentication errors globally
 * 
 * Redirects to login page on 401 Unauthorized responses.
 * Should be set up in the main app component.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const setupAuthInterceptor = (onUnauthorized: () => void) => {
  axios.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      if (error.response?.status === 401) {
        // Session expired or invalid - redirect to login
        onUnauthorized();
      }
      return Promise.reject(error);
    }
  );
};
