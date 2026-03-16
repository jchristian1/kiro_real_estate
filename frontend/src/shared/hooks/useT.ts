/**
 * Convenience hook — returns theme tokens + helpers.
 * Import this in every page/component instead of importing both useTheme + getTokens.
 */
import { useTheme } from '../contexts/ThemeContext';
import { getTokens, ThemeTokens } from '../utils/theme';

export interface T extends ThemeTokens {
  isDark: boolean;
  // Prebuilt card style
  card: React.CSSProperties;
  // Prebuilt table header cell style
  th: React.CSSProperties;
  // Prebuilt table row style (pass hover state manually)
  td: React.CSSProperties;
  // Prebuilt input style
  input: React.CSSProperties;
  // Prebuilt primary button style
  btnPrimary: React.CSSProperties;
  // Prebuilt secondary button style
  btnSecondary: React.CSSProperties;
  // Prebuilt danger button style
  btnDanger: React.CSSProperties;
  // Prebuilt label style
  labelStyle: React.CSSProperties;
  // Prebuilt section title style
  sectionTitle: React.CSSProperties;
  // Prebuilt divider style
  divider: React.CSSProperties;
}

import type React from 'react';

export const useT = (): T => {
  const { theme } = useTheme();
  const tok = getTokens(theme);
  const isDark = theme === 'dark';

  return {
    ...tok,
    isDark,
    card: {
      background: tok.bgCard,
      border: `1px solid ${tok.border}`,
      borderRadius: 16,
      padding: '20px 24px',
      transition: 'background 0.2s',
    },
    th: {
      textAlign: 'left' as const,
      padding: '0 0 10px',
      color: tok.textFaint,
      fontWeight: 500,
      fontSize: 11,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px',
      borderBottom: `1px solid ${tok.border}`,
    },
    td: {
      padding: '11px 0',
      color: tok.text,
      fontSize: 13,
    },
    input: {
      width: '100%',
      padding: '9px 13px',
      background: tok.bgInput,
      border: `1.5px solid ${tok.border}`,
      borderRadius: 10,
      fontSize: 13,
      color: tok.text,
      outline: 'none',
      boxSizing: 'border-box' as const,
      transition: 'border-color 0.15s',
    },
    btnPrimary: {
      padding: '8px 18px',
      background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
      border: 'none',
      borderRadius: 10,
      fontSize: 13,
      fontWeight: 600,
      color: '#fff',
      cursor: 'pointer',
      boxShadow: '0 4px 14px rgba(99,102,241,0.35)',
      transition: 'opacity 0.15s',
      whiteSpace: 'nowrap' as const,
    },
    btnSecondary: {
      padding: '8px 18px',
      background: tok.bgCard,
      border: `1px solid ${tok.border}`,
      borderRadius: 10,
      fontSize: 13,
      fontWeight: 500,
      color: tok.textMuted,
      cursor: 'pointer',
      transition: 'all 0.15s',
      whiteSpace: 'nowrap' as const,
    },
    btnDanger: {
      padding: '8px 18px',
      background: tok.redBg,
      border: `1px solid ${tok.red}30`,
      borderRadius: 10,
      fontSize: 13,
      fontWeight: 600,
      color: tok.red,
      cursor: 'pointer',
      transition: 'all 0.15s',
      whiteSpace: 'nowrap' as const,
    },
    labelStyle: {
      display: 'block' as const,
      fontSize: 11,
      fontWeight: 600,
      color: tok.textFaint,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px',
      marginBottom: 5,
    },
    sectionTitle: {
      fontSize: 11,
      fontWeight: 600,
      color: tok.textFaint,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.6px',
      marginBottom: 16,
    },
    divider: {
      borderTop: `1px solid ${tok.border}`,
      margin: '16px 0',
    },
  };
};
