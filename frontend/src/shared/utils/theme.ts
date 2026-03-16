/**
 * Design tokens for dark and light themes.
 * Apple-inspired — clean, modern, professional.
 */

export type Theme = 'dark' | 'light';

export interface ThemeTokens {
  // Backgrounds
  bgPage: string;
  bgSidebar: string;
  bgCard: string;
  bgCardHover: string;
  bgInput: string;
  bgInputFocus: string;
  bgHeader: string;
  bgBadge: string;

  // Borders
  border: string;
  borderFocus: string;

  // Text
  text: string;
  textSecondary: string;
  textMuted: string;
  textFaint: string;

  // Accent
  accent: string;
  accentGrad: string;
  accentGlow: string;
  accentBg: string;

  // Status
  green: string;
  greenBg: string;
  red: string;
  redBg: string;
  orange: string;
  orangeBg: string;
  yellow: string;
  yellowBg: string;

  // Scrollbar
  scrollbar: string;
}

export const dark: ThemeTokens = {
  bgPage:       '#0a0a0f',
  bgSidebar:    'rgba(12,12,18,0.98)',
  bgCard:       'rgba(255,255,255,0.04)',
  bgCardHover:  'rgba(255,255,255,0.07)',
  bgInput:      'rgba(255,255,255,0.06)',
  bgInputFocus: 'rgba(255,255,255,0.09)',
  bgHeader:     'rgba(10,10,15,0.88)',
  bgBadge:      'rgba(255,255,255,0.08)',

  border:       'rgba(255,255,255,0.08)',
  borderFocus:  'rgba(99,102,241,0.65)',

  text:         '#f0f0f5',
  textSecondary:'rgba(255,255,255,0.7)',
  textMuted:    'rgba(255,255,255,0.45)',
  textFaint:    'rgba(255,255,255,0.25)',

  accent:       '#6366f1',
  accentGrad:   'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
  accentGlow:   'rgba(99,102,241,0.35)',
  accentBg:     'rgba(99,102,241,0.15)',

  green:        '#34d399',
  greenBg:      'rgba(52,211,153,0.12)',
  red:          '#f87171',
  redBg:        'rgba(239,68,68,0.12)',
  orange:       '#fb923c',
  orangeBg:     'rgba(251,146,60,0.12)',
  yellow:       '#fbbf24',
  yellowBg:     'rgba(251,191,36,0.12)',

  scrollbar:    'rgba(255,255,255,0.12)',
};

export const light: ThemeTokens = {
  bgPage:       '#f5f5f7',
  bgSidebar:    'rgba(255,255,255,0.95)',
  bgCard:       '#ffffff',
  bgCardHover:  '#f9f9fb',
  bgInput:      '#ffffff',
  bgInputFocus: '#fafafe',
  bgHeader:     'rgba(255,255,255,0.88)',
  bgBadge:      'rgba(0,0,0,0.05)',

  border:       'rgba(0,0,0,0.08)',
  borderFocus:  'rgba(99,102,241,0.55)',

  text:         '#1c1c1e',
  textSecondary:'rgba(0,0,0,0.65)',
  textMuted:    'rgba(0,0,0,0.45)',
  textFaint:    'rgba(0,0,0,0.28)',

  accent:       '#6366f1',
  accentGrad:   'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
  accentGlow:   'rgba(99,102,241,0.25)',
  accentBg:     'rgba(99,102,241,0.08)',

  green:        '#059669',
  greenBg:      'rgba(5,150,105,0.1)',
  red:          '#dc2626',
  redBg:        'rgba(220,38,38,0.08)',
  orange:       '#ea580c',
  orangeBg:     'rgba(234,88,12,0.1)',
  yellow:       '#d97706',
  yellowBg:     'rgba(217,119,6,0.1)',

  scrollbar:    'rgba(0,0,0,0.15)',
};

export const tokens = { dark, light };

export const getTokens = (theme: Theme): ThemeTokens => tokens[theme];
