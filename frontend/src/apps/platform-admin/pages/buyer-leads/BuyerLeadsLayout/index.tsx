/**
 * Forms — layout with tab navigation.
 * Formerly "Buyer Lead Automation". Company-scoped, no tenantId in URL.
 */
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useT } from '@/shared/hooks';
import styles from './index.module.css';

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
    <div className={styles.container}>
      <h1 className={styles.title} style={{ color: t.text }}>Forms</h1>
      <nav className={styles.nav} style={{ borderBottom: `1px solid ${t.border}` }}>
        {TAB_LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={styles.navLink}
            style={({ isActive }) => ({
              color: isActive ? t.accent : t.textMuted,
              borderBottom: isActive ? `2px solid ${t.accent}` : '2px solid transparent',
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
