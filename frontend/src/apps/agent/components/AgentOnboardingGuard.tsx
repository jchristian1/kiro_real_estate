/**
 * AgentOnboardingGuard — redirects agents with incomplete onboarding to the correct step.
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAgentAuth } from '../contexts/AgentAuthContext';

const STEP_PATHS: Record<number, string> = {
  0: '/agent/onboarding/account',
  1: '/agent/onboarding/profile',
  2: '/agent/onboarding/gmail',
  3: '/agent/onboarding/sources',
  4: '/agent/onboarding/automation',
  5: '/agent/onboarding/templates',
  6: '/agent/onboarding/go-live',
};

export const AgentOnboardingGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { agent } = useAgentAuth();

  if (agent && !agent.onboarding_completed) {
    const step = agent.onboarding_step ?? 0;
    const path = STEP_PATHS[step] ?? '/agent/onboarding/go-live';
    return <Navigate to={path} replace />;
  }

  return <>{children}</>;
};
