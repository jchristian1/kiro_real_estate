import React from 'react';
import { useT } from '@/shared/hooks';
import { LeadSource } from '@/models';
import styles from './index.module.css';


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
      <table className={styles.table}>
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
              <td style={{ ...t.td }} className={styles.fontMedium}>{ls.sender_email}</td>
              <td style={{ ...t.td, color: t.textMuted }}>{truncate(ls.identifier_snippet)}</td>
              <td style={t.td}>
                <code className={styles.codeSnippet} style={{ background: t.bgBadge, color: t.textSecondary }} title={ls.name_regex}>
                  {truncate(ls.name_regex)}
                </code>
              </td>
              <td style={t.td}>
                <span className={styles.autoRespondBadge} style={{ background: ls.auto_respond_enabled ? t.greenBg : t.bgBadge, color: ls.auto_respond_enabled ? t.green : t.textMuted }}>
                  {ls.auto_respond_enabled ? 'Yes' : 'No'}
                </span>
              </td>
              <td style={{ ...t.td, color: t.textMuted }}>{new Date(ls.created_at).toLocaleDateString()}</td>
              <td style={{ ...t.td, textAlign: 'right' }}>
                <div className={styles.actionsCell}>
                  <button onClick={() => onView(ls)} className={styles.actionBtnPrimary} style={{ color: t.accent }}>View</button>
                  <button onClick={() => onEdit(ls)} className={styles.actionBtn} style={{ color: t.textMuted }}>Edit</button>
                  {onViewHistory && <button onClick={() => onViewHistory(ls)} className={styles.actionBtn} style={{ color: t.textSecondary }}>History</button>}
                  <button onClick={() => onDelete(ls)} className={styles.actionBtn} style={{ color: t.red }}>Delete</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
