import React from 'react';
import { useT } from '../utils/useT';

export interface LeadSource {
  id: number;
  sender_email: string;
  identifier_snippet: string;
  name_regex: string;
  phone_regex: string;
  template_id: number | null;
  auto_respond_enabled: boolean;
  created_at: string;
  updated_at: string;
}

interface LeadSourceListProps {
  leadSources: LeadSource[];
  onEdit: (leadSource: LeadSource) => void;
  onDelete: (leadSource: LeadSource) => void;
  onView: (leadSource: LeadSource) => void;
  onViewHistory?: (leadSource: LeadSource) => void;
}

export const LeadSourceList: React.FC<LeadSourceListProps> = ({ leadSources, onEdit, onDelete, onView, onViewHistory }) => {
  const t = useT();
  const truncate = (str: string, maxLen = 40) => str.length > maxLen ? str.slice(0, maxLen) + '…' : str;

  return (
    <div style={t.card}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Sender Email', 'Identifier Snippet', 'Name Regex', 'Auto Respond', 'Created', 'Actions'].map(h => (
              <th key={h} style={{ ...t.th, textAlign: h === 'Actions' ? 'right' : 'left' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {leadSources.map((ls) => (
            <tr key={ls.id} style={{ borderBottom: `1px solid ${t.border}` }}>
              <td style={{ ...t.td, fontWeight: 500 }}>{ls.sender_email}</td>
              <td style={{ ...t.td, color: t.textMuted }}>{truncate(ls.identifier_snippet)}</td>
              <td style={t.td}>
                <code style={{ fontSize: 11, background: t.bgBadge, color: t.textSecondary, padding: '2px 6px', borderRadius: 4, fontFamily: 'monospace' }} title={ls.name_regex}>
                  {truncate(ls.name_regex)}
                </code>
              </td>
              <td style={t.td}>
                <span style={{ padding: '2px 8px', fontSize: 10, fontWeight: 600, background: ls.auto_respond_enabled ? t.greenBg : t.bgBadge, color: ls.auto_respond_enabled ? t.green : t.textMuted, borderRadius: 20 }}>
                  {ls.auto_respond_enabled ? 'Yes' : 'No'}
                </span>
              </td>
              <td style={{ ...t.td, color: t.textMuted }}>{new Date(ls.created_at).toLocaleDateString()}</td>
              <td style={{ ...t.td, textAlign: 'right' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
                  <button onClick={() => onView(ls)} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>View</button>
                  <button onClick={() => onEdit(ls)} style={{ color: t.textMuted, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Edit</button>
                  {onViewHistory && <button onClick={() => onViewHistory(ls)} style={{ color: t.textSecondary, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>History</button>}
                  <button onClick={() => onDelete(ls)} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Delete</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
