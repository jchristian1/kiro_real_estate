/**
 * FirstRunGuard — redirects agents who have not completed first-run profile setup.
 * Replaces AgentOnboardingGuard (removed in PR A2).
 *
 * Logic: if authenticated and onboarding_completed=false → /agent/first-run
 * Otherwise render children (workspace).
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAgentAuth } from '../contexts/AgentAuthContext';

export const FirstRunGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { agent } = useAgentAuth();

  if (agent && !agent.onboarding_completed) {
    return <Navigate to="/agent/first-run" replace />;
  }

  return <>{children}</>;
};
