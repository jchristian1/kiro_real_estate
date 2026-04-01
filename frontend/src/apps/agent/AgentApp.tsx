/**
 * Agent App — root component for the agent-facing application.
 * Shares the same design system (tokens, ThemeContext, CSS vars) as the admin panel.
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from '../../shared/contexts/ToastContext';
import { AgentAuthProvider } from './contexts/AgentAuthContext';
import { ToastContainer, AgentAuthGuard, AgentOnboardingGuard, AgentLayout } from './components';

// Pages
import { AgentLoginPage } from './pages/AgentLoginPage';
import { AgentSignupPage } from './pages/AgentSignupPage';
import { OnboardingPage } from './pages/OnboardingPage';
import { AgentDashboardPage } from './pages/AgentDashboardPage';
import { AgentLeadsPage } from './pages/AgentLeadsPage';
import { AgentLeadDetailPage } from './pages/AgentLeadDetailPage';
import { SettingsPage } from './pages/SettingsPage';
import { AccountSettings } from './pages/SettingsPage/components';
import { AgentReportsPage } from './pages/AgentReportsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export const AgentApp: React.FC = () => (
  <QueryClientProvider client={queryClient}>
    <AgentAuthProvider>
      <ToastProvider>
        <ToastContainer />
        <Routes>
            {/* Public */}
            <Route path="login" element={<AgentLoginPage />} />
            <Route path="signup" element={<AgentSignupPage />} />

            {/* Onboarding — auth required, onboarding not yet complete */}
            <Route path="onboarding/*" element={
              <AgentAuthGuard>
                <OnboardingPage />
              </AgentAuthGuard>
            } />

            {/* Main app — auth + onboarding complete required */}
            <Route element={
              <AgentAuthGuard>
                <AgentOnboardingGuard>
                  <AgentLayout />
                </AgentOnboardingGuard>
              </AgentAuthGuard>
            }>
              <Route path="dashboard" element={<AgentDashboardPage />} />
              <Route path="leads" element={<AgentLeadsPage />} />
              <Route path="leads/:id" element={<AgentLeadDetailPage />} />
              <Route path="settings" element={<SettingsPage />}>
                <Route index element={<Navigate to="account" replace />} />
                <Route path="account" element={<AccountSettings />} />
              </Route>
              <Route path="reports" element={<AgentReportsPage />} />
            </Route>

            {/* Default */}
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ToastProvider>
      </AgentAuthProvider>
    </QueryClientProvider>
);
