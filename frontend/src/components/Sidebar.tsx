/**
 * Sidebar Navigation Component
 * 
 * Provides navigation links for all dashboard pages.
 * 
 * Requirements: 6.6
 */

import React from 'react';
import { NavLink } from 'react-router-dom';

export const Sidebar: React.FC = () => {
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `block px-4 py-2 rounded-md transition-colors ${
      isActive
        ? 'bg-blue-600 text-white'
        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
    }`;

  return (
    <aside className="w-64 bg-gray-800 min-h-screen">
      <div className="p-4">
        <h1 className="text-xl font-bold text-white mb-6">
          Gmail Lead Sync
        </h1>
        
        <nav className="space-y-2">
          <NavLink to="/dashboard" className={navLinkClass}>
            Dashboard
          </NavLink>
          
          <NavLink to="/agents" className={navLinkClass}>
            Agents
          </NavLink>
          
          <NavLink to="/lead-sources" className={navLinkClass}>
            Lead Sources
          </NavLink>
          
          <NavLink to="/templates" className={navLinkClass}>
            Templates
          </NavLink>
          
          <NavLink to="/leads" className={navLinkClass}>
            Leads
          </NavLink>
          
          <NavLink to="/audit-logs" className={navLinkClass}>
            Audit Logs
          </NavLink>
          
          <NavLink to="/settings" className={navLinkClass}>
            Settings
          </NavLink>
        </nav>
      </div>
    </aside>
  );
};
