/**
 * Role-Based Route Guard
 *
 * Renders children only if the authenticated user has the required role.
 * Redirects admins to /dashboard and agents to /agent/leads if they
 * access a route they are not authorized for.
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface RoleRouteProps {
  role: 'admin' | 'agent';
  children: React.ReactNode;
}

export const RoleRoute: React.FC<RoleRouteProps> = ({ role, children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-gray-600">Cargando...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role !== role) {
    // Redirect to the correct home for their role
    return <Navigate to={user.role === 'admin' ? '/dashboard' : '/agent/leads'} replace />;
  }

  return <>{children}</>;
};
