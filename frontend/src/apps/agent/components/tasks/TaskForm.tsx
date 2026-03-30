/**
 * TaskForm — inline form for creating a new task.
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { CreateTaskPayload } from '../../api/tasks';

interface Props {
  onSubmit: (payload: CreateTaskPayload) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export const TaskForm: React.FC<Props> = ({ onSubmit, onCancel, isSubmitting }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueAt, setDueAt] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      description: description.trim() || undefined,
      due_at: dueAt || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ marginTop: 12 }}>
      <input
        autoFocus
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Task title"
        maxLength={500}
        required
        style={{
          width: '100%', padding: '8px 10px', borderRadius: 8,
          border: `1px solid ${t.borderFocus}`, background: t.bgCard,
          color: t.text, fontSize: 13, boxSizing: 'border-box', marginBottom: 8,
          outline: 'none',
        }}
      />
      <textarea
        value={description}
        onChange={e => setDescription(e.target.value)}
        placeholder="Description (optional)"
        maxLength={2000}
        rows={2}
        style={{
          width: '100%', padding: '8px 10px', borderRadius: 8,
          border: `1px solid ${t.border}`, background: t.bgCard,
          color: t.text, fontSize: 12, boxSizing: 'border-box', marginBottom: 8,
          resize: 'vertical', outline: 'none',
        }}
      />
      <input
        type="datetime-local"
        value={dueAt}
        onChange={e => setDueAt(e.target.value)}
        style={{
          width: '100%', padding: '7px 10px', borderRadius: 8,
          border: `1px solid ${t.border}`, background: t.bgCard,
          color: t.text, fontSize: 12, boxSizing: 'border-box', marginBottom: 10,
          outline: 'none',
        }}
      />
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="submit"
          disabled={isSubmitting || !title.trim()}
          style={{
            flex: 1, padding: '8px', borderRadius: 8, border: 'none',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: '#fff', fontSize: 13, fontWeight: 600,
            cursor: isSubmitting || !title.trim() ? 'not-allowed' : 'pointer',
            opacity: isSubmitting || !title.trim() ? 0.6 : 1,
          }}
        >
          {isSubmitting ? 'Adding…' : 'Add Task'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          style={{
            padding: '8px 14px', borderRadius: 8,
            border: `1px solid ${t.border}`, background: t.bgCard,
            color: t.textMuted, fontSize: 13, cursor: 'pointer',
          }}
        >
          Cancel
        </button>
      </div>
    </form>
  );
};
