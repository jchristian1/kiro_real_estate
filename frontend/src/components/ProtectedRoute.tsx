/**
 * Protected Route Component
 * 
 * Route guard that redirects unauthenticated users to login page.
 * 
 * Requirements: 6.6
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { getTokens } from '../utils/theme';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { user, loading } = useAuth();
  const { theme } = useTheme();
  const t = getTokens(theme);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: t.bgPage, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: t.textMuted, fontSize: 14 }}>Loading…</div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Render protected content if authenticated
  return <>{children}</>;
};
