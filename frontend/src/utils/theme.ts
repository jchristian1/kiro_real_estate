/**
 * Shared design tokens — Apple-inspired dark theme
 */

export const colors = {
  bg:           '#0a0a0f',
  surface:      'rgba(255,255,255,0.04)',
  surfaceHover: 'rgba(255,255,255,0.07)',
  border:       'rgba(255,255,255,0.07)',
  borderFocus:  'rgba(99,102,241,0.6)',
  text:         '#f0f0f5',
  textMuted:    'rgba(255,255,255,0.4)',
  textFaint:    'rgba(255,255,255,0.25)',
  accent:       '#6366f1',
  accentGrad:   'linear-gradient(135deg, #6366f1, #8b5cf6)',
  accentGlow:   'rgba(99,102,241,0.35)',
  green:        '#34d399',
  greenBg:      'rgba(52,211,153,0.12)',
  red:          '#f87171',
  redBg:        'rgba(239,68,68,0.12)',
  orange:       '#fb923c',
  orangeBg:     'rgba(251,146,60,0.12)',
  yellow:       '#fbbf24',
};

export const card: React.CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: 16,
  padding: '20px 24px',
};

export const labelStyle: React.CSSProperties = {
  fontSize: 11, fontWeight: 600,
  color: colors.textFaint,
  textTransform: 'uppercase',
  letterSpacing: '0.6px',
  marginBottom: 6,
};

export const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px',
  background: 'rgba(255,255,255,0.06)',
  border: `1px solid ${colors.border}`,
  borderRadius: 10, fontSize: 13,
  color: colors.text, outline: 'none',
  boxSizing: 'border-box',
  transition: 'border-color 0.15s',
};

export const btnPrimary: React.CSSProperties = {
  padding: '9px 18px',
  background: colors.accentGrad,
  border: 'none', borderRadius: 10,
  fontSize: 13, fontWeight: 600, color: '#fff',
  cursor: 'pointer',
  boxShadow: `0 4px 14px ${colors.accentGlow}`,
  transition: 'opacity 0.15s',
};

export const btnSecondary: React.CSSProperties = {
  padding: '9px 18px',
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: 10, fontSize: 13,
  fontWeight: 500, color: colors.textMuted,
  cursor: 'pointer', transition: 'all 0.15s',
};

export const badge = (color: string, bg: string): React.CSSProperties => ({
  display: 'inline-block', padding: '3px 10px',
  borderRadius: 20, fontSize: 11, fontWeight: 600,
  color, background: bg,
});

// Need React for CSSProperties
import type React from 'react';
