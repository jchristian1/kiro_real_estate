/**
 * AgentLayout — sidebar + header layout matching admin panel style exactly.
 * Desktop: persistent sidebar. Mobile (<768px): hamburger + overlay sidebar.
 */

import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { PAGE_TITLES } from '@/models/agent';
import { AgentSidebar, AgentHeader } from './components';

// Inject responsive CSS once at module load
if (typeof document !== 'undefined' && !document.getElementById('agent-layout-css')) {
  const style = document.createElement('style');
  style.id = 'agent-layout-css';
  style.textContent = `
    @media (min-width: 768px) {
      .agent-sidebar-desktop { display: flex !important; }
      .agent-sidebar-mobile  { display: none !important; }
      .agent-hamburger       { display: none !important; }
    }
    @media (max-width: 767px) {
      .agent-sidebar-desktop { display: none !important; }
      .agent-sidebar-mobile  { display: flex !important; }
      .agent-hamburger       { display: flex !important; }
    }
  `;
  document.head.appendChild(style);
}

export const AgentLayout: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const segment = '/' + location.pathname.split('/').slice(1, 3).join('/');
  const title = PAGE_TITLES[segment] || 'Agent Portal';

  React.useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const sidebarStyles = {
    width: 224, minHeight: '100vh',
    background: t.bgSidebar,
    borderRight: `1px solid ${t.border}`,
    flexDirection: 'column' as const, flexShrink: 0,
    backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
    transition: 'background 0.2s',
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: t.bgPage, transition: 'background 0.2s' }}>
      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }}
        />
      )}

      {/* Desktop sidebar — persistent, static in flow */}
      <aside className="agent-sidebar-desktop" style={sidebarStyles}>
        <AgentSidebar />
      </aside>

      {/* Mobile sidebar — fixed overlay */}
      <aside
        className="agent-sidebar-mobile"
        style={{
          ...sidebarStyles,
          position: 'fixed',
          top: 0, left: 0, bottom: 0,
          zIndex: 50,
          transition: 'transform 0.25s ease, background 0.2s',
          transform: mobileOpen ? 'translateX(0)' : 'translateX(-100%)',
        }}
      >
        <AgentSidebar />
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <AgentHeader title={title} onMenuOpen={() => setMobileOpen(v => !v)} />
        <main style={{ flex: 1, padding: '28px', overflowY: 'auto', background: t.bgPage, transition: 'background 0.2s' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
