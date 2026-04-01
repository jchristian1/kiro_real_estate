import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { useAgentAuth } from '../../../../contexts/AgentAuthContext';
import { NAV_ITEMS } from '@/models/agent';

export const AgentSidebar: React.FC = () => {
  const { agent, logout } = useAgentAuth();
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/agent/login');
  };

  return (
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
};
