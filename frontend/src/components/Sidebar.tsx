/**
 * Sidebar Navigation Component
 * 
 * Provides navigation links based on user role.
 * - Admins: See all management pages
 * - Agents: See only their leads and dashboard
 * 
 * Requirements: 6.6
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const Sidebar: React.FC = () => {
  const { user } = useAuth();
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `block px-4 py-2 rounded-md transition-colors ${
      isActive
        ? 'bg-blue-600 text-white'
        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
    }`;

  const isAdmin = user?.role === 'admin';
  const isAgent = user?.role === 'agent';

  return (
    <aside className="w-64 bg-gray-800 min-h-screen">
      <div className="p-4">
        <h1 className="text-xl font-bold text-white mb-6">
          Gmail Lead Sync
        </h1>
        
        <nav className="space-y-2">
          {/* Dashboard - visible to all */}
          <NavLink to="/dashboard" className={navLinkClass}>
            Dashboard
          </NavLink>
          
          {/* Admin-only sections */}
          {isAdmin && (
            <>
              <div className="pt-2 pb-1">
                <p className="text-xs font-semibold text-gray-400 uppercase px-4">
                  Administration
                </p>
              </div>
              
              <NavLink to="/agents" className={navLinkClass}>
                Agents
              </NavLink>
              
              <NavLink to="/companies" className={navLinkClass}>
                Companies
              </NavLink>
              
              <NavLink to="/lead-sources" className={navLinkClass}>
                Lead Sources
              </NavLink>
              
              <NavLink to="/templates" className={navLinkClass}>
                Templates
              </NavLink>
              
              <NavLink to="/leads" className={navLinkClass}>
                All Leads
              </NavLink>
              
              <NavLink to="/audit-logs" className={navLinkClass}>
                Audit Logs
              </NavLink>
            </>
          )}
          
          {/* Agent-only sections */}
          {isAgent && (
            <>
              <div className="pt-2 pb-1">
                <p className="text-xs font-semibold text-gray-400 uppercase px-4">
                  My Work
                </p>
              </div>
              
              <NavLink to="/agent/leads" className={navLinkClass}>
                My Leads
              </NavLink>
            </>
          )}
          
          {/* Settings - visible to all */}
          <div className="pt-4 border-t border-gray-700">
            <NavLink to="/settings" className={navLinkClass}>
              Settings
            </NavLink>
          </div>
        </nav>
      </div>
    </aside>
  );
};
