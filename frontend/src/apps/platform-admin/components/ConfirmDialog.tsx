import React, { useEffect, useRef } from 'react';
import { useT } from '../../../shared/hooks/useT';

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
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" data-testid="confirm-dialog">
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
        onClick={onCancel} data-testid="confirm-dialog-backdrop" />
      <div style={{
        position: 'relative', zIndex: 10,
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 18, padding: '28px 28px 24px',
        maxWidth: 420, width: '100%', margin: '0 16px',
        boxShadow: '0 24px 60px rgba(0,0,0,0.4)',
      }}>
        <h2 id="confirm-dialog-title" style={{ margin: '0 0 10px', fontSize: 17, fontWeight: 700, color: t.text }}
          data-testid="confirm-dialog-title">{title}</h2>
        <p style={{ margin: '0 0 24px', fontSize: 14, color: t.textMuted, lineHeight: 1.6 }}
          data-testid="confirm-dialog-message">{message}</p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button ref={cancelRef} onClick={onCancel} style={t.btnSecondary} data-testid="confirm-dialog-cancel">
            {cancelLabel}
          </button>
          <button onClick={onConfirm} data-testid="confirm-dialog-confirm"
            style={isDangerous ? t.btnDanger : t.btnPrimary}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
