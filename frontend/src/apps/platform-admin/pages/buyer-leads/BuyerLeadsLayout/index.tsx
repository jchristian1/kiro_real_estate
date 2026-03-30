/**
 * Forms — layout with tab navigation.
 * Formerly "Buyer Lead Automation". Company-scoped, no tenantId in URL.
 */
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useT } from '@/shared/hooks';

const TAB_LINKS = [
  { to: 'qualification', label: 'Qualification Forms' },
  { to: 'scoring', label: 'Scoring' },
  { to: 'states', label: 'Lead States' },
  { to: 'simulate', label: 'Simulate' },
  { to: 'audit', label: 'Audit Log' },
];

export const BuyerLeadsLayout: React.FC = () => {
  const t = useT();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Forms</h1>
      <nav style={{ display: 'flex', gap: 4, borderBottom: `1px solid ${t.border}` }}>
        {TAB_LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: 500,
              color: isActive ? t.accent : t.textMuted,
              borderBottom: isActive ? `2px solid ${t.accent}` : '2px solid transparent',
              textDecoration: 'none',
              transition: 'all 0.15s',
              marginBottom: -1,
            })}
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
};
