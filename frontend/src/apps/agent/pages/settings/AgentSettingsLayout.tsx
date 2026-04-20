/**
 * Agent Settings Layout — Account preferences and Email Templates.
 */

import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';

export const AgentSettingsLayout: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  const navStyle = (isActive: boolean) => ({
    display: 'inline-block',
    padding: '6px 14px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600 as const,
    textDecoration: 'none',
    color: isActive ? t.accent : t.textMuted,
    background: isActive ? t.accentBg : 'transparent',
    marginRight: 6,
    transition: 'all 0.15s',
  });

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: '0 0 16px' }}>Settings</h1>
      <nav style={{ marginBottom: 24 }}>
        <NavLink to="account" style={({ isActive }) => navStyle(isActive)}>Account</NavLink>
        <NavLink to="templates" style={({ isActive }) => navStyle(isActive)}>Email Templates</NavLink>
      </nav>
      <Outlet />
    </div>
  );
};
