/**
 * TaskList — renders the full task panel for a lead.
 * Composes TaskItem + TaskForm.
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { useTasks, useCreateTask, useUpdateTask, useDeleteTask } from '../../hooks/useTasks';
import { TaskItem } from './TaskItem';
import { TaskForm } from './TaskForm';

interface Props {
  leadId: number;
}

export const TaskList: React.FC<Props> = ({ leadId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [showForm, setShowForm] = useState(false);
  const [filter, setFilter] = useState<'all' | 'open' | 'done'>('all');

  const { data, isLoading, error } = useTasks(leadId, filter === 'all' ? undefined : filter);
  const createTask = useCreateTask(leadId);
  const updateTask = useUpdateTask(leadId);
  const deleteTask = useDeleteTask(leadId);

  const tasks = data?.tasks ?? [];

  const handleToggle = (taskId: number, done: boolean) => {
    updateTask.mutate({ taskId, payload: { status: done ? 'done' : 'open' } });
  };

  const handleDelete = (taskId: number) => {
    deleteTask.mutate(taskId);
  };

  const handleCreate = (payload: { title: string; description?: string; due_at?: string }) => {
    createTask.mutate(payload, {
      onSuccess: () => setShowForm(false),
    });
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['all', 'open', 'done'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '4px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                border: `1px solid ${filter === f ? t.accent : t.border}`,
                background: filter === f ? t.accentBg : 'transparent',
                color: filter === f ? t.accent : t.textMuted,
                cursor: 'pointer', textTransform: 'capitalize',
              }}
            >
              {f}
            </button>
          ))}
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            style={{
              padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', color: '#fff', cursor: 'pointer',
            }}
          >
            + Add Task
          </button>
        )}
      </div>

      {/* Inline form */}
      {showForm && (
        <TaskForm
          onSubmit={handleCreate}
          onCancel={() => setShowForm(false)}
          isSubmitting={createTask.isPending}
        />
      )}

      {/* Task list */}
      {isLoading && (
        <div style={{ fontSize: 13, color: t.textFaint, padding: '12px 0' }}>Loading tasks…</div>
      )}
      {error && (
        <div style={{ fontSize: 13, color: '#ef4444', padding: '8px 0' }}>Failed to load tasks.</div>
      )}
      {!isLoading && tasks.length === 0 && (
        <div style={{ fontSize: 13, color: t.textFaint, padding: '12px 0', textAlign: 'center' }}>
          {filter === 'all' ? 'No tasks yet.' : `No ${filter} tasks.`}
        </div>
      )}
      {tasks.map(task => (
        <TaskItem
          key={task.id}
          task={task}
          onToggle={handleToggle}
          onDelete={handleDelete}
        />
      ))}
    </div>
  );
};
