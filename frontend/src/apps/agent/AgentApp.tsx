/**
 * Agent App — root component for the agent-facing application.
 * Shares the same design system (tokens, ThemeContext, CSS vars) as the admin panel.
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from '../../shared/contexts/ToastContext';
import { ToastContainer } from './components/ToastContainer';
import { AgentAuthProvider } from './contexts/AgentAuthContext';
import { AgentAuthGuard } from './components/AgentAuthGuard';
import { FirstRunGuard } from './components/FirstRunGuard';
import { AgentLayout } from './components/AgentLayout';

// Pages
import { AgentLoginPage } from './pages/AgentLoginPage';
import { FirstRunPage } from './pages/FirstRunPage';
import { AgentDashboardPage } from './pages/AgentDashboardPage';
import { AgentLeadsPage } from './pages/AgentLeadsPage';
import { AgentLeadDetailPage } from './pages/AgentLeadDetailPage';
import { AgentSettingsLayout } from './pages/settings/AgentSettingsLayout';
import { AccountSettingsPage } from './pages/settings/AccountSettingsPage';
import { TemplatesSettingsPage } from './pages/settings/TemplatesSettingsPage';
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

          {/* First-run profile — auth required, shown when onboarding_completed=false */}
          <Route path="first-run" element={
            <AgentAuthGuard>
              <FirstRunPage />
            </AgentAuthGuard>
          } />

          {/* Main workspace — auth + first-run complete required */}
          <Route element={
            <AgentAuthGuard>
              <FirstRunGuard>
                <AgentLayout />
              </FirstRunGuard>
            </AgentAuthGuard>
          }>
            <Route path="dashboard" element={<AgentDashboardPage />} />
            <Route path="leads" element={<AgentLeadsPage />} />
            <Route path="leads/:id" element={<AgentLeadDetailPage />} />
            <Route path="settings" element={<AgentSettingsLayout />}>
              <Route index element={<Navigate to="account" replace />} />
              <Route path="account" element={<AccountSettingsPage />} />
              <Route path="templates" element={<TemplatesSettingsPage />} />
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
