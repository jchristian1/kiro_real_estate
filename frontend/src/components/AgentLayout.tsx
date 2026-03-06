/**
 * Agent Layout Component
 *
 * Simplified layout for the real estate agent portal.
 * Shows only lead-related navigation.
 */

import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const AgentLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive
      ? 'bg-emerald-600 text-white shadow-sm'
      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
    }`;

  return (
    <div className="flex min-h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 flex flex-col shadow-xl">
        {/* Branding */}
        <div className="p-5 border-b border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">🏡</span>
            <h1 className="text-lg font-bold text-white">Portal Agente</h1>
          </div>
          <p className="text-xs text-gray-400">Inmobiliaria</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-4 mb-2">
            Leads
          </p>
          <NavLink to="/agent/leads" className={navLinkClass}>
            <span>📋</span>
            Mis Leads
          </NavLink>
        </nav>

        {/* User info & logout */}
        <div className="p-4 border-t border-gray-700">
          <div className="flex items-center gap-3 mb-3 px-1">
            <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-white font-bold text-sm">
              {user?.username?.[0]?.toUpperCase() ?? 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.username}</p>
              <p className="text-xs text-gray-400 capitalize">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-gray-700 rounded-lg transition-colors text-left"
          >
            🚪 Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
};
