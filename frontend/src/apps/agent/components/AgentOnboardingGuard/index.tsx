/**
 * AgentOnboardingGuard — redirects agents with incomplete onboarding to the correct step.
 */

import React, { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAgentAuth } from '../../contexts/AgentAuthContext';
import { STEP_PATHS } from '@/models/agent';

export interface AgentOnboardingGuardProps {
  children: ReactNode;
}

export const AgentOnboardingGuard: React.FC<AgentOnboardingGuardProps> = ({ children }) => {
  const { agent } = useAgentAuth();

  if (agent && !agent.onboarding_completed) {
    const step = agent.onboarding_step ?? 0;
    const path = STEP_PATHS[step] ?? '/agent/onboarding/go-live';
    return <Navigate to={path} replace />;
  }

  return <>{children}</>;
};
