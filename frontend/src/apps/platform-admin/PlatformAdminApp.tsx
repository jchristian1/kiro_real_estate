/**
 * Platform Admin App — root component for the platform-admin panel.
 * Mounted at / in main.tsx.
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { DashboardLayout } from './components/DashboardLayout';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { AgentsPage } from './pages/AgentsPage';
import { CompaniesPage } from './pages/CompaniesPage';
import { LeadSourcesPage } from './pages/LeadSourcesPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { LeadsPage } from './pages/LeadsPage';
import { LeadsLawPage } from './pages/LeadsLawPage/index';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { SettingsPage } from './pages/SettingsPage';
import { PipelinesPage } from './pages/PipelinesPage';
import { FormsPage } from './pages/FormsPage';
import { PublicFormPage } from './pages/PublicFormPage';

const queryClient = new QueryClient();

export const PlatformAdminApp: React.FC = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/public/buyer-qualification/:token" element={<PublicFormPage />} />

        {/* Redirect root to dashboard */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Protected routes */}
        <Route
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/lead-sources" element={<LeadSourcesPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/leads" element={<LeadsLawPage />} />
          <Route path="/audit-logs" element={<AuditLogsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/pipelines" element={<PipelinesPage />} />

          {/* Forms (formerly Buyer Automation) */}
          <Route path="/forms" element={<FormsPage />} />

          {/* Legacy redirects */}
          <Route path="/buyer-leads/:tenantId/*" element={<Navigate to="/forms" replace />} />
        </Route>

        {/* Catch-all redirect to dashboard */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  </QueryClientProvider>
);
