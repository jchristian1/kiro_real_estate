/**
 * AgentLayout — sidebar + header layout matching admin panel style exactly.
 * Desktop: persistent sidebar (like admin DashboardLayout).
 * Mobile (<768px): hamburger + overlay sidebar.
 */

import React from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { useAgentAuth } from '../contexts/AgentAuthContext';

interface NavItem { to: string; label: string; icon: string; }

const NAV_ITEMS: NavItem[] = [
  { to: '/agent/dashboard', label: 'Dashboard', icon: '◈' },
  { to: '/agent/leads',     label: 'Leads',     icon: '◎' },
  { to: '/agent/settings',  label: 'Settings',  icon: '⚙' },
  { to: '/agent/reports',   label: 'Reports',   icon: '≡' },
];

const PAGE_TITLES: Record<string, string> = {
  '/agent/dashboard': 'Dashboard',
  '/agent/leads':     'Leads',
  '/agent/settings':  'Settings',
  '/agent/reports':   'Reports',
};

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
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const { agent, logout } = useAgentAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const segment = '/' + location.pathname.split('/').slice(1, 3).join('/');
  const title = PAGE_TITLES[segment] || 'Agent Portal';

  React.useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate('/agent/login');
  };

  const sidebarContent = (
    <>
      {/* Logo */}
      <div style={{ padding: '22px 18px 18px', borderBottom: `1px solid ${t.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 17, color: '#fff', fontWeight: 800, flexShrink: 0,
            boxShadow: '0 4px 12px rgba(99,102,241,0.4)',
          }}>L</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text, letterSpacing: '-0.3px' }}>LeadSync</div>
            <div style={{ fontSize: 10, color: t.textFaint, letterSpacing: '0.6px', textTransform: 'uppercase' }}>Agent Portal</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '10px 8px', overflowY: 'auto' }}>
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 10px', borderRadius: 9, marginBottom: 1,
              fontSize: 13, fontWeight: isActive ? 600 : 400,
              color: isActive ? (theme === 'dark' ? '#fff' : '#6366f1') : t.textMuted,
              background: isActive ? t.accentBg : 'transparent',
              textDecoration: 'none', transition: 'all 0.12s', letterSpacing: '-0.1px',
            })}
            onMouseEnter={e => {
              const el = e.currentTarget as HTMLAnchorElement;
              if (!el.getAttribute('aria-current')) {
                el.style.background = t.bgCardHover;
                el.style.color = t.textSecondary;
              }
            }}
            onMouseLeave={e => {
              const el = e.currentTarget as HTMLAnchorElement;
              if (!el.getAttribute('aria-current')) {
                el.style.background = 'transparent';
                el.style.color = t.textMuted;
              }
            }}
          >
            <span style={{ fontSize: 13, width: 18, textAlign: 'center', flexShrink: 0 }}>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div style={{ padding: '10px 8px 14px', borderTop: `1px solid ${t.border}` }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 9,
          padding: '8px 10px', borderRadius: 9, background: t.bgCard,
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, color: '#fff', fontWeight: 700, flexShrink: 0,
          }}>
            {agent?.full_name?.[0]?.toUpperCase() || agent?.email?.[0]?.toUpperCase() || 'A'}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {agent?.full_name || agent?.email}
            </div>
            <div style={{ fontSize: 10, color: t.textFaint }}>Agent</div>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: t.textFaint, fontSize: 15, padding: '2px 4px',
              borderRadius: 5, transition: 'color 0.15s', lineHeight: 1,
            }}
            onMouseEnter={e => (e.currentTarget.style.color = t.red)}
            onMouseLeave={e => (e.currentTarget.style.color = t.textFaint)}
          >
            ⏻
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: t.bgPage, transition: 'background 0.2s' }}>
      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }}
        />
      )}

      {/* Desktop sidebar — persistent, static in flow (matches admin panel) */}
      <aside
        className="agent-sidebar-desktop"
        style={{
          width: 224, minHeight: '100vh',
          background: t.bgSidebar,
          borderRight: `1px solid ${t.border}`,
          flexDirection: 'column', flexShrink: 0,
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          transition: 'background 0.2s',
        }}
      >
        {sidebarContent}
      </aside>

      {/* Mobile sidebar — fixed overlay */}
      <aside
        className="agent-sidebar-mobile"
        style={{
          width: 224, minHeight: '100vh',
          background: t.bgSidebar,
          borderRight: `1px solid ${t.border}`,
          flexDirection: 'column', flexShrink: 0,
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          transition: 'transform 0.25s ease, background 0.2s',
          position: 'fixed',
          top: 0, left: 0, bottom: 0,
          zIndex: 50,
          transform: mobileOpen ? 'translateX(0)' : 'translateX(-100%)',
        }}
      >
        {sidebarContent}
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header */}
        <header style={{
          height: 56, background: t.bgHeader,
          borderBottom: `1px solid ${t.border}`,
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 24px', flexShrink: 0, position: 'sticky', top: 0, zIndex: 10,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Hamburger — mobile only, hidden on desktop via CSS */}
            <button
              onClick={() => setMobileOpen(v => !v)}
              aria-label="Open navigation"
              className="agent-hamburger"
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: t.textMuted, fontSize: 20, padding: '8px', borderRadius: 8,
                alignItems: 'center', justifyContent: 'center',
                minWidth: 44, minHeight: 44,
              }}
            >☰</button>
            <h1 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: t.text, letterSpacing: '-0.3px' }}>
              {title}
            </h1>
          </div>
          <button
            onClick={toggle}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '6px 12px', background: t.bgCard,
              border: `1px solid ${t.border}`, borderRadius: 20,
              cursor: 'pointer', fontSize: 12, fontWeight: 500,
              color: t.textMuted, transition: 'all 0.15s', userSelect: 'none',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = t.bgCardHover;
              (e.currentTarget as HTMLButtonElement).style.color = t.text;
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = t.bgCard;
              (e.currentTarget as HTMLButtonElement).style.color = t.textMuted;
            }}
          >
            <span style={{ fontSize: 14 }}>{theme === 'dark' ? '☀️' : '🌙'}</span>
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </header>

        <main style={{
          flex: 1, padding: '28px', overflowY: 'auto',
          background: t.bgPage, transition: 'background 0.2s',
        }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
