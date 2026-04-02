/**
 * Sidebar Navigation — theme-aware, Apple-inspired
 */
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/apps/platform-admin/contexts/AuthContext';
import { useTheme } from '@/shared/contexts';
import { getTokens, NAV_GROUPS } from '@/shared/utils';
import styles from './index.module.css';

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
    <aside className={styles.sidebar}
      style={{ background: t.bgSidebar, borderRight: `1px solid ${t.border}` }}>
      <div className={styles.logoSection} style={{ borderBottom: `1px solid ${t.border}` }}>
        <div className={styles.logoRow}>
          <div className={styles.logoIcon}>L</div>
          <div>
            <div className={styles.logoTitle} style={{ color: t.text }}>LeadSync</div>
            <div className={styles.logoSubtitle} style={{ color: t.textFaint }}>Admin Panel</div>
          </div>
        </div>
      </div>

      <nav className={styles.nav}>
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} style={{ marginBottom: gi < NAV_GROUPS.length - 1 ? 16 : 0 }}>
            <div className={styles.groupLabel} style={{ color: t.textFaint }}>{group.label}</div>
            {group.items.map(item => (
              <NavLink key={item.to} to={item.to} className={styles.navLink}
                style={({ isActive }) => ({
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? (theme === 'dark' ? '#fff' : '#6366f1') : t.textMuted,
                  background: isActive ? t.accentBg : 'transparent',
                })}
                onMouseEnter={e => {
                  const el = e.currentTarget as HTMLAnchorElement;
                  if (!el.getAttribute('aria-current')) { el.style.background = t.bgCardHover; el.style.color = t.textSecondary; }
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget as HTMLAnchorElement;
                  if (!el.getAttribute('aria-current')) { el.style.background = 'transparent'; el.style.color = t.textMuted; }
                }}>
                <span className={styles.navIcon}>{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className={styles.userFooter} style={{ borderTop: `1px solid ${t.border}` }}>
        <div className={styles.userCard} style={{ background: t.bgCard }}>
          <div className={styles.userAvatar}>{user?.username?.[0]?.toUpperCase() || 'A'}</div>
          <div className={styles.userInfo}>
            <div className={styles.userName} style={{ color: t.text }}>{user?.username}</div>
            <div className={styles.userRole} style={{ color: t.textFaint }}>Administrator</div>
          </div>
          <button onClick={handleLogout} title="Sign out" className={styles.logoutButton}
            style={{ color: t.textFaint }}
            onMouseEnter={e => (e.currentTarget.style.color = t.red)}
            onMouseLeave={e => (e.currentTarget.style.color = t.textFaint)}>⏻</button>
        </div>
      </div>
    </aside>
  );
};
