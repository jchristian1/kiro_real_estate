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
import { BuyerLeadsLayout } from './pages/buyer-leads/BuyerLeadsLayout';
import { BuyerFormTab } from './pages/buyer-leads/BuyerFormTab';
import { BuyerScoringTab } from './pages/buyer-leads/BuyerScoringTab';
import { LeadStatesTab } from './pages/buyer-leads/LeadStatesTab';
import { SimulationTab } from './pages/buyer-leads/SimulationTab';
import { BuyerAuditTab } from './pages/buyer-leads/BuyerAuditTab';
import { FormVersionEditor } from './pages/buyer-leads/FormVersionEditor';
import { TemplateVersionEditor } from './pages/buyer-leads/TemplateVersionEditor';
import { PublicFormPage } from './pages/PublicFormPage';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public route */}
          <Route path="/login" element={<LoginPage />} />
          {/* Public tokenized form — no auth */}
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
            <Route path="/leads" element={<LeadsPage />} />
            <Route path="/audit-logs" element={<AuditLogsPage />} />
            <Route path="/settings" element={<SettingsPage />} />

            {/* Qualification email template editor — accessed from Templates page */}
            <Route path="/qualification-templates/:tenantId/message-templates/:templateId" element={<TemplateVersionEditor />} />

            {/* Buyer Lead Automation */}
            <Route path="/buyer-leads/:tenantId" element={<BuyerLeadsLayout />}>
              <Route index element={<BuyerFormTab />} />
              <Route path="forms" element={<BuyerFormTab />} />
              <Route path="forms/:formId" element={<FormVersionEditor />} />
              <Route path="scoring" element={<BuyerScoringTab />} />
              <Route path="states" element={<LeadStatesTab />} />
              <Route path="simulate" element={<SimulationTab />} />
              <Route path="audit" element={<BuyerAuditTab />} />
            </Route>
          </Route>
          
          {/* Catch-all redirect to dashboard */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
