/**
 * TemplateChooserModal — shown on first run or when creating a new pipeline.
 * Options: Real Estate Buyer Pipeline, Law Firm Pipeline, Blank.
 * Requirements: 9.8, 11.3
 */

import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts';
import { getTokens, TEMPLATES } from '@/shared/utils';

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
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: theme === 'dark' ? '#16161e' : '#fff',
        border: `1px solid ${t.border}`, borderRadius: 20,
        padding: '32px 28px', width: 480, maxWidth: '90vw',
        boxShadow: '0 24px 64px rgba(0,0,0,0.4)',
      }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: t.text, marginBottom: 6 }}>Choose a Pipeline Template</div>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 24 }}>Pick a starting point for your pipeline.</div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28 }}>
          {TEMPLATES.map(tpl => (
            <button
              key={tpl.id}
              onClick={() => setSelected(tpl.id)}
              style={{
                background: selected === tpl.id ? t.accentBg : t.bgCard,
                border: `1.5px solid ${selected === tpl.id ? t.accent : t.border}`,
                borderRadius: 12, padding: '14px 16px', cursor: 'pointer',
                textAlign: 'left', transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 4 }}>{tpl.label}</div>
              <div style={{ fontSize: 12, color: t.textMuted }}>{tpl.desc}</div>
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: `1px solid ${t.border}`, borderRadius: 9,
              color: t.textMuted, fontSize: 13, padding: '8px 18px', cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!selected || loading}
            style={{
              background: selected ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgBadge,
              border: 'none', borderRadius: 9, color: selected ? '#fff' : t.textFaint,
              fontSize: 13, fontWeight: 600, padding: '8px 20px', cursor: selected ? 'pointer' : 'default',
              transition: 'all 0.15s',
            }}
          >
            {loading ? 'Creating…' : 'Create Pipeline'}
          </button>
        </div>
      </div>
    </div>
  );
};
