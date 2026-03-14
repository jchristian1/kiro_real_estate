import React from 'react';
import { useT } from '../../../shared/hooks/useT';

export interface Template {
  id: number;
  name: string;
  subject: string;
  body: string;
  created_at: string;
  updated_at: string;
}

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
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
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
              <td style={{ ...t.td, fontWeight: 500 }}>{tmpl.name}</td>
              <td style={{ ...t.td, color: t.textMuted }}>{truncate(tmpl.subject)}</td>
              <td style={{ ...t.td, color: t.textMuted, whiteSpace: 'nowrap' }}>{new Date(tmpl.updated_at).toLocaleDateString()}</td>
              <td style={{ ...t.td, textAlign: 'right' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
                  <button onClick={() => onEdit(tmpl)} style={{ color: t.textMuted, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Edit</button>
                  <button onClick={() => onViewHistory(tmpl)} style={{ color: t.textSecondary, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>History</button>
                  <button onClick={() => onDelete(tmpl)} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Delete</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
