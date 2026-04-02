import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import styles from '../../index.module.css';

interface FormTemplate {
  id: number;
  name: string;
  status: 'active' | 'draft' | 'archived';
  intent_type: string;
  created_at: string;
}

interface FormCardProps {
  form: FormTemplate;
  onEdit: () => void;
  onDelete: () => void;
  onRename: () => void;
}

export const FormCard: React.FC<FormCardProps> = ({ form, onEdit, onDelete, onRename }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const [hovered, setHovered] = useState(false);

  const statusColor = form.status === 'active' ? t.green : form.status === 'draft' ? t.yellow : t.textFaint;
  const statusBg = form.status === 'active' ? t.greenBg : form.status === 'draft' ? t.yellowBg : t.bgBadge;
  const borderColor = hovered ? t.accent + '60' : (isDark ? '#2a2d35' : '#e5e7eb');
  const cardBg = isDark ? '#1c1f26' : '#ffffff';
  const cardShadow = hovered
    ? `0 0 0 1px ${t.accent}30, 0 4px 20px rgba(0,0,0,0.15)`
    : isDark ? '0 1px 4px rgba(0,0,0,0.2)' : '0 1px 4px rgba(0,0,0,0.05)';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onEdit}
      className={styles.card}
      style={{ background: cardBg, border: `1px solid ${borderColor}`, boxShadow: cardShadow }}
    >
      <div className={styles.cardContent}>
        <div className={styles.cardNameRow}>
          <span className={styles.cardName} style={{ color: t.text }}>{form.name}</span>
          <span className={styles.statusBadge} style={{ background: statusBg, color: statusColor }}>{form.status}</span>
        </div>
        <div className={styles.cardMeta} style={{ color: t.textFaint }}>
          {form.intent_type} · Created {new Date(form.created_at).toLocaleDateString()}
        </div>
      </div>
      <div className={styles.cardActions} onClick={e => e.stopPropagation()}>
        <button onClick={onEdit} className={styles.cardActionButton}
          style={{ background: isDark ? '#1e2330' : '#f0f4ff', color: t.accent, border: `1px solid ${t.accent}30` }}>Edit</button>
        <button onClick={onRename} className={styles.cardActionButton}
          style={{ background: isDark ? '#1e2330' : '#f5f5f7', color: t.textMuted, border: `1px solid ${isDark ? '#2a2d35' : '#e5e7eb'}` }}>Rename</button>
        <button onClick={onDelete} className={styles.cardActionButton}
          style={{ background: isDark ? '#2d1a1a' : '#fff0f0', color: t.red, border: `1px solid ${t.red}30` }}>Delete</button>
      </div>
    </div>
  );
};
