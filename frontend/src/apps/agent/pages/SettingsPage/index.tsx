/**
 * Agent Settings Page — layout and sub-routing.
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';

export const SettingsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: '0 0 24px' }}>Account Settings</h1>
      <Outlet />
    </div>
  );
};
