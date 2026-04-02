/**
 * TemplateChooserModal — shown on first run or when creating a new pipeline.
 * Options: Real Estate Buyer Pipeline, Law Firm Pipeline, Blank.
 * Requirements: 9.8, 11.3
 */

import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts';
import { getTokens, TEMPLATES } from '@/shared/utils';
import styles from './index.module.css';

interface Props {
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}


export const TemplateChooserModal: React.FC<Props> = ({ onClose, onCreate }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    if (!selected) return;
    setLoading(true);
    try {
      const tpl = TEMPLATES.find(t => t.id === selected)!;
      await onCreate(tpl.label);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.modal} style={{
        background: theme === 'dark' ? '#16161e' : '#fff',
        border: `1px solid ${t.border}`,
      }}>
        <div className={styles.title} style={{ color: t.text }}>Choose a Pipeline Template</div>
        <div className={styles.subtitle} style={{ color: t.textMuted }}>Pick a starting point for your pipeline.</div>

        <div className={styles.templateList}>
          {TEMPLATES.map(tpl => (
            <button
              key={tpl.id}
              onClick={() => setSelected(tpl.id)}
              className={styles.templateBtn}
              style={{
                background: selected === tpl.id ? t.accentBg : t.bgCard,
                border: `1.5px solid ${selected === tpl.id ? t.accent : t.border}`,
              }}
            >
              <div className={styles.templateLabel} style={{ color: t.text }}>{tpl.label}</div>
              <div className={styles.templateDesc} style={{ color: t.textMuted }}>{tpl.desc}</div>
            </button>
          ))}
        </div>

        <div className={styles.actions}>
          <button
            onClick={onClose}
            className={styles.cancelBtn}
            style={{ border: `1px solid ${t.border}`, color: t.textMuted }}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!selected || loading}
            className={styles.createBtn}
            style={{
              background: selected ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgBadge,
              color: selected ? '#fff' : t.textFaint,
              cursor: selected ? 'pointer' : 'default',
            }}
          >
            {loading ? 'Creating…' : 'Create Pipeline'}
          </button>
        </div>
      </div>
    </div>
  );
};
