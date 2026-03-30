/**
 * TaskItem — single task row with complete/delete actions.
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { Task } from '../../api/tasks';

interface Props {
  task: Task;
  onToggle: (taskId: number, done: boolean) => void;
  onDelete: (taskId: number) => void;
}

export const TaskItem: React.FC<Props> = ({ task, onToggle, onDelete }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [confirming, setConfirming] = useState(false);

  const isDone = task.status === 'done';

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '10px 0',
      borderBottom: `1px solid ${t.border}`,
    }}>
      {/* Checkbox */}
      <button
        onClick={() => onToggle(task.id, !isDone)}
        style={{
          width: 18, height: 18, borderRadius: 4, flexShrink: 0, marginTop: 2,
          border: `2px solid ${isDone ? t.accent : t.border}`,
          background: isDone ? t.accent : 'transparent',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        aria-label={isDone ? 'Mark open' : 'Mark done'}
      >
        {isDone && <span style={{ color: '#fff', fontSize: 11, lineHeight: 1 }}>✓</span>}
      </button>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13, fontWeight: 500, color: isDone ? t.textMuted : t.text,
          textDecoration: isDone ? 'line-through' : 'none',
          wordBreak: 'break-word',
        }}>
          {task.title}
        </div>
        {task.description && (
          <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2, wordBreak: 'break-word' }}>
            {task.description}
          </div>
        )}
        {task.due_at && (
          <div style={{ fontSize: 11, color: t.textFaint, marginTop: 3 }}>
            Due {new Date(task.due_at).toLocaleDateString()}
          </div>
        )}
      </div>

      {/* Delete */}
      {confirming ? (
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <button
            onClick={() => { onDelete(task.id); setConfirming(false); }}
            style={{ fontSize: 11, color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px' }}
          >
            Delete
          </button>
          <button
            onClick={() => setConfirming(false)}
            style={{ fontSize: 11, color: t.textMuted, background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px' }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setConfirming(true)}
          style={{ fontSize: 16, color: t.textFaint, background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0, lineHeight: 1, padding: '0 4px' }}
          aria-label="Delete task"
        >
          ×
        </button>
      )}
    </div>
  );
};
