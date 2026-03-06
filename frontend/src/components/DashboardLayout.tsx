/**
 * Dashboard Layout — theme-aware
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ToastProvider } from '../contexts/ToastContext';
import { ToastContainer } from './ToastContainer';
import { useTheme } from '../contexts/ThemeContext';
import { getTokens } from '../utils/theme';

export const DashboardLayout: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  return (
    <ToastProvider>
      <ToastContainer />
      <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: t.bgPage, transition: 'background 0.2s' }}>
        <Sidebar />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <Header />
          <main style={{
            flex: 1,
            padding: '28px',
            overflowY: 'auto',
            background: t.bgPage,
            transition: 'background 0.2s',
          }}>
            <Outlet />
          </main>
        </div>
      </div>
    </ToastProvider>
  );
};
