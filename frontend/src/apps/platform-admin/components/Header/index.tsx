/**
 * Header — sticky, blurred, with theme toggle
 */
import React from 'react';
import { useLocation } from 'react-router-dom';
import { useTheme } from '@/shared/contexts';
import { getTokens, PAGE_TITLES } from '@/shared/utils';
import styles from './index.module.css';

export const Header: React.FC = () => {
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const location = useLocation();
  const segment = '/' + location.pathname.split('/')[1];
  const title = PAGE_TITLES[segment] || 'Dashboard';

  return (
    <header className={styles.header}
      style={{ background: t.bgHeader, borderBottom: `1px solid ${t.border}` }}>
      <h1 className={styles.title} style={{ color: t.text }}>{title}</h1>
      <button onClick={toggle} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        className={styles.themeToggle}
        style={{ background: t.bgCard, border: `1px solid ${t.border}`, color: t.textMuted }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = t.bgCardHover; (e.currentTarget as HTMLButtonElement).style.color = t.text; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = t.bgCard; (e.currentTarget as HTMLButtonElement).style.color = t.textMuted; }}>
        <span className={styles.themeIcon}>{theme === 'dark' ? '☀️' : '🌙'}</span>
        {theme === 'dark' ? 'Light' : 'Dark'}
      </button>
    </header>
  );
};
