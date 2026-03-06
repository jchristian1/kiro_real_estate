/**
 * Buyer Lead Automation — layout with tab navigation.
 */
import React from 'react';
import { NavLink, Outlet, useParams } from 'react-router-dom';
import { useT } from '../../utils/useT';

const TAB_LINKS = [
  { to: 'forms',    label: 'Forms' },
  { to: 'scoring',  label: 'Scoring' },
  { to: 'states',   label: 'Lead States' },
  { to: 'simulate', label: 'Simulate' },
  { to: 'audit',    label: 'Audit Log' },
];

export const BuyerLeadsLayout: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const t = useT();
  const base = `/buyer-leads/${tenantId}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Buyer Lead Automation</h1>
      <nav style={{ display: 'flex', gap: 4, borderBottom: `1px solid ${t.border}` }}>
        {TAB_LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={`${base}/${to}`}
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
