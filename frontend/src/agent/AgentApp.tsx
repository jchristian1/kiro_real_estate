/**
 * Agent App — root component for the agent-facing application.
 * Shares the same design system (tokens, ThemeContext, CSS vars) as the admin panel.
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '../contexts/ThemeContext';
import { ToastProvider } from '../contexts/ToastContext';
import { ToastContainer } from '../components/ToastContainer';
import { AgentAuthProvider } from './contexts/AgentAuthContext';
import { AgentAuthGuard } from './components/AgentAuthGuard';
import { AgentOnboardingGuard } from './components/AgentOnboardingGuard';
import { AgentLayout } from './components/AgentLayout';

// Pages
import { AgentLoginPage } from './pages/AgentLoginPage';
import { AgentSignupPage } from './pages/AgentSignupPage';
import { OnboardingWizard } from './pages/onboarding/OnboardingWizard';
import { AgentDashboardPage } from './pages/AgentDashboardPage';
import { AgentLeadsPage } from './pages/AgentLeadsPage';
import { AgentLeadDetailPage } from './pages/AgentLeadDetailPage';
import { AgentSettingsLayout } from './pages/settings/AgentSettingsLayout';
import { TemplatesSettingsPage } from './pages/settings/TemplatesSettingsPage';
import { AutomationSettingsPage } from './pages/settings/AutomationSettingsPage';
import { AccountSettingsPage } from './pages/settings/AccountSettingsPage';
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
  <ThemeProvider>
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
                <OnboardingWizard />
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
              <Route path="settings" element={<AgentSettingsLayout />}>
                <Route index element={<Navigate to="templates" replace />} />
                <Route path="templates" element={<TemplatesSettingsPage />} />
                <Route path="automation" element={<AutomationSettingsPage />} />
                <Route path="account" element={<AccountSettingsPage />} />
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
  </ThemeProvider>
);
