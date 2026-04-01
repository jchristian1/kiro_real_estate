import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';


export interface AgentHeaderProps {
  title: string;
  onMenuOpen: () => void;
}

export const AgentHeader: React.FC<AgentHeaderProps> = ({ title, onMenuOpen }) => {
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);

  return (
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
          onClick={onMenuOpen}
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
  );
};
