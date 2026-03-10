/**
 * AgentAuthGuard — redirects unauthenticated users to /agent/login.
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAgentAuth } from '../contexts/AgentAuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { getTokens } from '../../utils/theme';

export const AgentAuthGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { agent, loading } = useAgentAuth();
  const { theme } = useTheme();
  const t = getTokens(theme);

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: t.bgPage, color: t.textMuted, fontSize: 14,
      }}>
        Loading…
      </div>
    );
  }

  if (!agent) return <Navigate to="/agent/login" replace />;
  return <>{children}</>;
};
