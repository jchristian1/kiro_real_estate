/**
 * Agent Settings Layout — just Account (personal/Gmail settings).
 * Templates, Automation, Sources are managed in the company admin panel.
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';

export const AgentSettingsLayout: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: '0 0 24px' }}>Account Settings</h1>
      <Outlet />
    </div>
  );
};
