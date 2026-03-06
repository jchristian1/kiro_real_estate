/**
 * Main Application Component
 * 
 * Sets up routing structure with protected routes.
 * 
 * Requirements: 6.6
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { RoleRoute } from './components/RoleRoute';
import { DashboardLayout } from './components/DashboardLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { AgentsPage } from './pages/AgentsPage';
import { CompaniesPage } from './pages/CompaniesPage';
import { LeadSourcesPage } from './pages/LeadSourcesPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { LeadsPage } from './pages/LeadsPage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { SettingsPage } from './pages/SettingsPage';
import { AgentLeadsPage } from './pages/agent/AgentLeadsPage';
import { AgentLeadDetailPage } from './pages/agent/AgentLeadDetailPage';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public route */}
          <Route path="/login" element={<LoginPage />} />
          
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
            {/* Dashboard - accessible to all authenticated users */}
            <Route path="/dashboard" element={<DashboardPage />} />
            
            {/* Admin-only routes */}
            <Route
              path="/agents"
              element={
                <RoleRoute role="admin">
                  <AgentsPage />
                </RoleRoute>
              }
            />
            <Route
              path="/companies"
              element={
                <RoleRoute role="admin">
                  <CompaniesPage />
                </RoleRoute>
              }
            />
            <Route
              path="/lead-sources"
              element={
                <RoleRoute role="admin">
                  <LeadSourcesPage />
                </RoleRoute>
              }
            />
            <Route
              path="/templates"
              element={
                <RoleRoute role="admin">
                  <TemplatesPage />
                </RoleRoute>
              }
            />
            <Route
              path="/leads"
              element={
                <RoleRoute role="admin">
                  <LeadsPage />
                </RoleRoute>
              }
            />
            <Route
              path="/audit-logs"
              element={
                <RoleRoute role="admin">
                  <AuditLogsPage />
                </RoleRoute>
              }
            />
            
            {/* Settings - accessible to all authenticated users */}
            <Route path="/settings" element={<SettingsPage />} />
            
            {/* Agent-specific routes */}
            <Route
              path="/agent/leads"
              element={
                <RoleRoute role="agent">
                  <AgentLeadsPage />
                </RoleRoute>
              }
            />
            <Route
              path="/agent/leads/:id"
              element={
                <RoleRoute role="agent">
                  <AgentLeadDetailPage />
                </RoleRoute>
              }
            />
          </Route>
          
          {/* Catch-all redirect to dashboard */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
