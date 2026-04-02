import React from 'react';
import { useT } from '@/shared/hooks';
import { Template } from '@/models/app-model';
import styles from './index.module.css';

interface TemplateListProps {
  templates: Template[];
  onEdit: (t: Template) => void;
  onDelete: (t: Template) => void;
  onViewHistory: (t: Template) => void;
}

export const TemplateList: React.FC<TemplateListProps> = ({ templates, onEdit, onDelete, onViewHistory }) => {
  const t = useT();
  const truncate = (s: string, n = 60) => s.length > n ? s.slice(0, n) + '…' : s;

  return (
    <div style={t.card}>
      <table className={styles.table}>
        <thead>
          <tr>
            {['Name', 'Subject', 'Updated', 'Actions'].map(h => (
              <th key={h} style={{ ...t.th, textAlign: h === 'Actions' ? 'right' : 'left' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {templates.map((tmpl) => (
            <tr key={tmpl.id} style={{ borderBottom: `1px solid ${t.border}` }}>
              <td style={{ ...t.td }} className={styles.fontMedium}>{tmpl.name}</td>
              <td style={{ ...t.td, color: t.textMuted }}>{truncate(tmpl.subject)}</td>
              <td style={{ ...t.td, color: t.textMuted }} className={styles.noWrap}>{new Date(tmpl.updated_at).toLocaleDateString()}</td>
              <td style={{ ...t.td, textAlign: 'right' }}>
                <div className={styles.actionsCell}>
                  <button onClick={() => onEdit(tmpl)} className={styles.actionBtn} style={{ color: t.textMuted }}>Edit</button>
                  <button onClick={() => onViewHistory(tmpl)} className={styles.actionBtn} style={{ color: t.textSecondary }}>History</button>
                  <button onClick={() => onDelete(tmpl)} className={styles.actionBtn} style={{ color: t.red }}>Delete</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
