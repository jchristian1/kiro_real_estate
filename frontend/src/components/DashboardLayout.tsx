/**
 * Dashboard Layout Component — Apple-inspired dark theme
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ToastProvider } from '../contexts/ToastContext';
import { ToastContainer } from './ToastContainer';

export const DashboardLayout: React.FC = () => {
  return (
    <ToastProvider>
      <ToastContainer />
      <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: '#0a0a0f' }}>
        <Sidebar />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <Header />
          <main style={{
            flex: 1,
            padding: '28px 28px',
            overflowY: 'auto',
            background: '#0a0a0f',
          }}>
            <Outlet />
          </main>
        </div>
      </div>
    </ToastProvider>
  );
};
