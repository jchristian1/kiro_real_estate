/**
 * Agent Auth Context — session cookie-based auth for the agent-facing app.
 * Mirrors the admin AuthContext pattern but targets /api/v1/agent/auth/* endpoints.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { agentApi } from '../api/agentApi';

export interface AgentUser {
  id: number;
  email: string;
  full_name: string;
  onboarding_step: number;
  onboarding_completed: boolean;
}

interface AgentAuthState {
  agent: AgentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAgent: () => Promise<void>;
}

const AgentAuthContext = createContext<AgentAuthState | undefined>(undefined);

export const AgentAuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [agent, setAgent] = useState<AgentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshAgent = async () => {
    try {
      const data = await agentApi.get<AgentUser>('/agent/auth/me');
      setAgent(data);
    } catch {
      setAgent(null);
    }
  };

  useEffect(() => {
    refreshAgent().finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const data = await agentApi.post<AgentUser>('/agent/auth/login', { email, password });
    setAgent(data);
  };

  const signup = async (email: string, password: string) => {
    const data = await agentApi.post<AgentUser>('/agent/auth/signup', { email, password });
    setAgent(data);
  };

  const logout = async () => {
    try { await agentApi.post('/agent/auth/logout', {}); } catch { /* ignore */ }
    setAgent(null);
  };

  return (
    <AgentAuthContext.Provider value={{ agent, loading, login, signup, logout, refreshAgent }}>
      {children}
    </AgentAuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAgentAuth = (): AgentAuthState => {
  const ctx = useContext(AgentAuthContext);
  if (!ctx) throw new Error('useAgentAuth must be used within AgentAuthProvider');
  return ctx;
};
