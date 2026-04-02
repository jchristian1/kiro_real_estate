import React from 'react';
import { useToast } from '@/shared/contexts';
import { useT } from '@/shared/hooks';
import { TOAST_COLORS } from '@/shared/utils';
import styles from './index.module.css';

export const ToastContainer: React.FC = () => {
  const { toasts, dismissToast } = useToast();
  const t = useT();

  if (toasts.length === 0) return null;

  return (
    <div className={styles.container}>
      {toasts.map(toast => {
        const c = TOAST_COLORS[toast.type] || TOAST_COLORS.info;
        return (
          <div key={toast.id} role="alert" className={styles.toast}
            style={{ background: t.isDark ? c.bg : '#fff', border: `1px solid ${c.border}` }}>
            <span className={styles.dot} style={{ background: c.dot }} />
            <span className={styles.message} style={{ color: t.isDark ? c.color : '#1c1c1e' }}>{toast.message}</span>
            <button onClick={() => dismissToast(toast.id)} aria-label="Dismiss"
              className={styles.dismissButton} style={{ color: t.textFaint }}>×</button>
          </div>
        );
      })}
    </div>
  );
};
