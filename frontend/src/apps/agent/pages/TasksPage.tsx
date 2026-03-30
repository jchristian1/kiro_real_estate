/**
 * TasksPage — agent's task overview across all leads.
 *
 * V1: Shows tasks for a specific lead when navigated from lead detail,
 * or a placeholder when accessed directly.
 * The TaskList component is the primary entry point for task management
 * and is embedded in AgentLeadDetailPage for per-lead context.
 */

import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { TaskList } from '../components/tasks/TaskList';

export const TasksPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [params] = useSearchParams();
  const leadId = Number(params.get('lead_id'));

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: t.text, marginBottom: 20, letterSpacing: '-0.4px' }}>
        Tasks
      </div>

      {leadId > 0 ? (
        <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '20px 20px' }}>
          <TaskList leadId={leadId} />
        </div>
      ) : (
        <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '40px 20px', textAlign: 'center' }}>
          <div style={{ fontSize: 14, color: t.textMuted }}>
            Open a lead to view and manage its tasks.
          </div>
        </div>
      )}
    </div>
  );
};
