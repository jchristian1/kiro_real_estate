import React from 'react';
import { useToast } from '@/shared/contexts/ToastContext';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { TOAST_COLORS } from '@/models/agent';

export const ToastContainer: React.FC = () => {
  const { toasts, dismissToast } = useToast();
  const { theme } = useTheme();
  const t = getTokens(theme);

  if (toasts.length === 0) return null;

  return (
    <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 100, display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 360 }}>
      {toasts.map(toast => {
        const c = TOAST_COLORS[toast.type] || TOAST_COLORS.info;
        return (
          <div key={toast.id} role="alert" style={{
            display: 'flex', alignItems: 'flex-start', gap: 10,
            padding: '12px 14px',
            background: theme === 'dark' ? c.bg : '#fff',
            border: `1px solid ${c.border}`,
            borderRadius: 12,
            boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
            backdropFilter: 'blur(12px)',
          }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: c.dot, flexShrink: 0, marginTop: 4 }} />
            <span style={{ flex: 1, fontSize: 13, color: theme === 'dark' ? c.color : '#1c1c1e', fontWeight: 500, lineHeight: 1.5 }}>
              {toast.message}
            </span>
            <button onClick={() => dismissToast(toast.id)} aria-label="Dismiss"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 16, lineHeight: 1, padding: 0, flexShrink: 0 }}>
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
};
