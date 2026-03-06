/**
 * Header Component — Apple-inspired dark theme
 */

import React from 'react';
import { useLocation } from 'react-router-dom';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard':     'Dashboard',
  '/leads':         'Leads',
  '/buyer-leads':   'Buyer Automation',
  '/agents':        'Agents',
  '/companies':     'Companies',
  '/lead-sources':  'Lead Sources',
  '/templates':     'Templates',
  '/audit-logs':    'Audit Logs',
  '/settings':      'Settings',
};

export const Header: React.FC = () => {
  const location = useLocation();
  const segment = '/' + location.pathname.split('/')[1];
  const title = PAGE_TITLES[segment] || 'Dashboard';

  return (
    <header style={{
      height: 56,
      background: 'rgba(10,10,15,0.85)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      backdropFilter: 'blur(20px)',
      display: 'flex',
      alignItems: 'center',
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
        color: '#f0f0f5',
        letterSpacing: '-0.3px',
      }}>
        {title}
      </h1>
    </header>
  );
};
