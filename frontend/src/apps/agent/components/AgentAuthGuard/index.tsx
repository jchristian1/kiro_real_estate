/**
 * AgentAuthGuard — redirects unauthenticated users to /agent/login.
 */

import React, { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAgentAuth } from '../../contexts/AgentAuthContext';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';

export interface AgentAuthGuardProps {
  children: ReactNode;
}

export const AgentAuthGuard: React.FC<AgentAuthGuardProps> = ({ children }) => {
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
