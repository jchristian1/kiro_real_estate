/**
 * Dashboard Layout — theme-aware
 */
import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../Sidebar';
import { Header } from '../Header';
import { ToastProvider, useTheme } from '@/shared/contexts';
import { ToastContainer } from '../ToastContainer';
import { getTokens } from '@/shared/utils';
import styles from './index.module.css';

export const DashboardLayout: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  return (
    <ToastProvider>
      <ToastContainer />
      <div className={styles.layout} style={{ background: t.bgPage }}>
        <Sidebar />
        <div className={styles.contentColumn}>
          <Header />
          <main className={styles.main} style={{ background: t.bgPage }}>
            <Outlet />
          </main>
        </div>
      </div>
    </ToastProvider>
  );
};
