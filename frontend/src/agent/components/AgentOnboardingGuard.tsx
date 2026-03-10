/**
 * AgentOnboardingGuard — redirects agents with incomplete onboarding to /agent/onboarding.
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAgentAuth } from '../contexts/AgentAuthContext';

export const AgentOnboardingGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { agent } = useAgentAuth();

  if (agent && !agent.onboarding_completed) {
    return <Navigate to="/agent/onboarding" replace />;
  }

  return <>{children}</>;
};
