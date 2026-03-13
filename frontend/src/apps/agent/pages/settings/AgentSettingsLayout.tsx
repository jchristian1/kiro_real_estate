/**
 * Agent Settings Layout — sub-nav for Templates, Automation, Account.
 */

import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';

const TABS = [
  { to: 'templates',  label: 'Templates'  },
  { to: 'automation', label: 'Automation' },
  { to: 'sources',    label: 'Sources'    },
  { to: 'account',    label: 'Account'    },
];

export const AgentSettingsLayout: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 24, borderBottom: `1px solid ${t.border}`, paddingBottom: 0 }}>
        {TABS.map(tab => (
          <NavLink
            key={tab.to}
            to={tab.to}
            style={({ isActive }) => ({
              padding: '8px 18px', fontSize: 13, fontWeight: isActive ? 600 : 400,
              color: isActive ? t.accent : t.textMuted,
              borderBottom: `2px solid ${isActive ? t.accent : 'transparent'}`,
              textDecoration: 'none', transition: 'all 0.15s', marginBottom: -1,
            })}
          >
            {tab.label}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  );
};
