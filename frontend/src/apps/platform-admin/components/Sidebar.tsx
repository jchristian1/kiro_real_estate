/**
 * Sidebar Navigation — theme-aware, Apple-inspired
 */

import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';

interface NavItem { to: string; label: string; icon: string; }

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard',     label: 'Dashboard',        icon: '◈' },
  { to: '/leads',         label: 'Leads',            icon: '◎' },
  { to: '/buyer-leads/1', label: 'Buyer Automation', icon: '⟳' },
  { to: '/agents',        label: 'Agents',           icon: '◉' },
  { to: '/companies',     label: 'Companies',        icon: '▣' },
  { to: '/lead-sources',  label: 'Lead Sources',     icon: '⬡' },
  { to: '/templates',     label: 'Templates',        icon: '◧' },
  { to: '/audit-logs',    label: 'Audit Logs',       icon: '≡' },
  { to: '/settings',      label: 'Settings',         icon: '⚙' },
];

export const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <aside style={{
      width: 224,
      minHeight: '100vh',
      background: t.bgSidebar,
      borderRight: `1px solid ${t.border}`,
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      transition: 'background 0.2s',
    }}>
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
            <div style={{ fontSize: 10, color: t.textFaint, letterSpacing: '0.6px', textTransform: 'uppercase' }}>Admin Panel</div>
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
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 9,
              marginBottom: 1,
              fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              color: isActive ? (theme === 'dark' ? '#fff' : '#6366f1') : t.textMuted,
              background: isActive ? t.accentBg : 'transparent',
              textDecoration: 'none',
              transition: 'all 0.12s',
              letterSpacing: '-0.1px',
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
          padding: '8px 10px', borderRadius: 9,
          background: t.bgCard,
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, color: '#fff', fontWeight: 700, flexShrink: 0,
          }}>
            {user?.username?.[0]?.toUpperCase() || 'A'}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.username}
            </div>
            <div style={{ fontSize: 10, color: t.textFaint }}>Administrator</div>
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
    </aside>
  );
};
