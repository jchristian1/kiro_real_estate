import React, { useState } from 'react';
import axios from 'axios';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { useToast } from '@/shared/contexts/ToastContext';
import styles from '../../index.module.css';

interface FormTemplate {
  id: number;
  name: string;
  status: 'active' | 'draft' | 'archived';
  intent_type: string;
  created_at: string;
}

interface RenameModalProps {
  form: FormTemplate;
  tenantId: string;
  onClose: () => void;
  onSaved: () => void;
}

const API = '/api/v1';

export const RenameModal: React.FC<RenameModalProps> = ({ form, tenantId, onClose, onSaved }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();
  const [name, setName] = useState(form.name);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim() || name === form.name) { onClose(); return; }
    setSaving(true);
    try {
      await axios.put(`${API}/buyer-leads/tenants/${tenantId}/forms/${form.id}`, { name: name.trim() });
      success('Renamed'); onSaved();
    } catch { toastError('Rename failed'); }
    finally { setSaving(false); }
  };

  return (
    <>
      <div onClick={onClose} className={styles.modalOverlay} />
      <div className={styles.modalContent} style={{ background: isDark ? '#1c1f26' : '#ffffff' }}>
        <div className={styles.modalTitle} style={{ color: t.text }}>Rename Form</div>
        <input value={name} onChange={e => setName(e.target.value)} autoFocus
          onKeyDown={e => e.key === 'Enter' && handleSave()}
          className={styles.modalInput}
          style={{ background: t.bgInput, border: `1px solid ${t.border}`, color: t.text }} />
        <div className={styles.modalActions}>
          <button onClick={onClose} className={styles.modalCancelButton}
            style={{ border: `1px solid ${isDark ? '#2a2d35' : '#e5e7eb'}`, color: t.textMuted }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className={styles.modalSaveButton}
            style={{ background: t.accent, opacity: saving ? 0.6 : 1 }}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </>
  );
};
