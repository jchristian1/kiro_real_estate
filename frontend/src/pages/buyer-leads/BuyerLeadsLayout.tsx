/**
 * Buyer Lead Automation — layout with tab navigation.
 */
import React from 'react';
import { NavLink, Outlet, useParams } from 'react-router-dom';

const TAB_LINKS = [
  { to: 'forms',     label: 'Forms' },
  { to: 'scoring',   label: 'Scoring' },
  { to: 'templates', label: 'Email Templates' },
  { to: 'states',    label: 'Lead States' },
  { to: 'simulate',  label: 'Simulate' },
  { to: 'audit',     label: 'Audit Log' },
];

export const BuyerLeadsLayout: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const base = `/buyer-leads/${tenantId}`;

  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      isActive
        ? 'border-blue-600 text-blue-600'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
    }`;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-800">Buyer Lead Automation</h1>
      <nav className="flex border-b border-gray-200 space-x-1">
        {TAB_LINKS.map(({ to, label }) => (
          <NavLink key={to} to={`${base}/${to}`} className={tabClass}>
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
};
