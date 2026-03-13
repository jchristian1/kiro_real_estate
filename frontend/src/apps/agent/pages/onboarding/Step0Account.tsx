/**
 * Step 0 — Account Creation (redirects to signup page).
 * If agent is already logged in, skip to profile.
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAgentAuth } from '../../contexts/AgentAuthContext';

export const Step0Account: React.FC = () => {
  const { agent } = useAgentAuth();
  // If already authenticated, skip account creation
  if (agent) return <Navigate to="/agent/onboarding/profile" replace />;
  return <Navigate to="/agent/signup" replace />;
};
