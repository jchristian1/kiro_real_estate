/**
 * Dashboard Layout Component
 * 
 * Provides the main layout structure with sidebar, header, and content area.
 * Used for all authenticated pages.
 * 
 * Requirements: 6.6
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
      <div className="flex min-h-screen bg-gray-100">
        <Sidebar />
        
        <div className="flex-1 flex flex-col">
          <Header />
          
          <main className="flex-1 p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </ToastProvider>
  );
};
