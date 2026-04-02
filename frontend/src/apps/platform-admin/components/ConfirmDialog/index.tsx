import React, { useEffect, useRef } from 'react';
import { useT } from '@/shared/hooks';
import styles from './index.module.css';

export interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDangerous?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen, title, message,
  confirmLabel = 'Confirm', cancelLabel = 'Cancel',
  isDangerous = false, onConfirm, onCancel,
}) => {
  const t = useT();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => { if (isOpen) cancelRef.current?.focus(); }, [isOpen]);
  useEffect(() => {
    if (!isOpen) return;
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" data-testid="confirm-dialog">
      <div className={styles.backdrop} onClick={onCancel} data-testid="confirm-dialog-backdrop" />
      <div className={styles.panel} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
        <h2 id="confirm-dialog-title" className={styles.title} style={{ color: t.text }} data-testid="confirm-dialog-title">{title}</h2>
        <p className={styles.message} style={{ color: t.textMuted }} data-testid="confirm-dialog-message">{message}</p>
        <div className={styles.actions}>
          <button ref={cancelRef} onClick={onCancel} style={t.btnSecondary} data-testid="confirm-dialog-cancel">{cancelLabel}</button>
          <button onClick={onConfirm} data-testid="confirm-dialog-confirm" style={isDangerous ? t.btnDanger : t.btnPrimary}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
};
