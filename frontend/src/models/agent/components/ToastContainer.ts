import type { ToastType } from '@/shared/contexts/ToastContext';

export const TOAST_COLORS: Record<ToastType, { bg: string; border: string; color: string; dot: string }> = {
  success: { bg: 'rgba(52,211,153,0.1)',  border: 'rgba(52,211,153,0.3)',  color: '#34d399', dot: '#34d399' },
  error:   { bg: 'rgba(248,113,113,0.1)', border: 'rgba(248,113,113,0.3)', color: '#f87171', dot: '#f87171' },
  warning: { bg: 'rgba(251,191,36,0.1)',  border: 'rgba(251,191,36,0.3)',  color: '#fbbf24', dot: '#fbbf24' },
  info:    { bg: 'rgba(99,102,241,0.1)',  border: 'rgba(99,102,241,0.3)',  color: '#818cf8', dot: '#818cf8' },
};
