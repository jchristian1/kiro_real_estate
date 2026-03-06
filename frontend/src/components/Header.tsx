/**
 * Header — sticky, blurred, with theme toggle
 */

import React from 'react';
import { useLocation } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { getTokens } from '../utils/theme';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard':    'Dashboard',
  '/leads':        'Leads',
  '/buyer-leads':  'Buyer Automation',
  '/agents':       'Agents',
  '/companies':    'Companies',
  '/lead-sources': 'Lead Sources',
  '/templates':    'Templates',
  '/audit-logs':   'Audit Logs',
  '/settings':     'Settings',
};

export const Header: React.FC = () => {
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const location = useLocation();
  const segment = '/' + location.pathname.split('/')[1];
  const title = PAGE_TITLES[segment] || 'Dashboard';

  return (
    <header style={{
      height: 56,
      background: t.bgHeader,
      borderBottom: `1px solid ${t.border}`,
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      flexShrink: 0,
      position: 'sticky',
      top: 0,
      zIndex: 10,
    }}>
      <h1 style={{
        margin: 0,
        fontSize: 16,
        fontWeight: 600,
        color: t.text,
        letterSpacing: '-0.3px',
      }}>
        {title}
      </h1>

      {/* Theme toggle */}
      <button
        onClick={toggle}
        title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          padding: '6px 12px',
          background: t.bgCard,
          border: `1px solid ${t.border}`,
          borderRadius: 20,
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 500,
          color: t.textMuted,
          transition: 'all 0.15s',
          userSelect: 'none',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLButtonElement).style.background = t.bgCardHover;
          (e.currentTarget as HTMLButtonElement).style.color = t.text;
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLButtonElement).style.background = t.bgCard;
          (e.currentTarget as HTMLButtonElement).style.color = t.textMuted;
        }}
      >
        <span style={{ fontSize: 14 }}>{theme === 'dark' ? '☀️' : '🌙'}</span>
        {theme === 'dark' ? 'Light' : 'Dark'}
      </button>
    </header>
  );
};
