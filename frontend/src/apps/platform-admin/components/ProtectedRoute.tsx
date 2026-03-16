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
import { useT } from '../../../shared/hooks/useT';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { user, loading } = useAuth();
  const t = useT();

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        background: t.bgPage,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <span style={{ color: t.textMuted, fontSize: 14 }}>Loading…</span>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};
