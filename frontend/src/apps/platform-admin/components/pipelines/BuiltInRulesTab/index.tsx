/**
 * BuiltInRulesTab — table of built-in event type → stage mappings.
 * Requirements: 9.5
 */

import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { usePipelineEventMappings, usePipelineStages, useUpsertEventMapping } from '@/apps/platform-admin/hooks/usePipelineQueries';
import type { BuiltInEventType } from '@/apps/platform-admin/api/pipelinesApi';
import { EVENT_LABELS, ALL_EVENTS } from '@/shared/utils';
import styles from './index.module.css';

interface Props { pipelineId: number; }

export const BuiltInRulesTab: React.FC<Props> = ({ pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: mappings = [] } = usePipelineEventMappings(pipelineId);
  const { data: stages = [] } = usePipelineStages(pipelineId);
  const upsert = useUpsertEventMapping();

  const mappingByEvent = Object.fromEntries(mappings.map(m => [m.event_type, m]));

  const handleStageChange = (eventType: BuiltInEventType, stageId: number) => {
    const existing = mappingByEvent[eventType];
    upsert.mutate({ pipelineId, eventType, target_stage_id: stageId, is_enabled: existing?.is_enabled ?? true });
  };

  const handleToggle = (eventType: BuiltInEventType, enabled: boolean) => {
    const existing = mappingByEvent[eventType];
    if (!existing) return;
    upsert.mutate({ pipelineId, eventType, target_stage_id: existing.target_stage_id, is_enabled: enabled });
  };

  const sortedStages = [...stages].sort((a, b) => a.position - b.position);

  return (
    <div className={styles.wrapper} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
      <div className={styles.header} style={{ borderBottom: `1px solid ${t.border}` }}>
        <div className={styles.headerTitle} style={{ color: t.text }}>Built-in Event Rules</div>
        <div className={styles.headerDesc} style={{ color: t.textMuted }}>
          When a platform event fires, automatically move the lead to the selected stage.
        </div>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            {['Event', 'Move to Stage', 'Enabled'].map(h => (
              <th key={h} className={styles.colHeader} style={{
                color: t.textFaint,
                borderBottom: `1px solid ${t.border}`,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ALL_EVENTS.map((eventType, idx) => {
            const mapping = mappingByEvent[eventType];
            return (
              <tr key={eventType} style={{ borderBottom: idx < ALL_EVENTS.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                <td className={styles.eventCell} style={{ color: t.text }}>
                  {EVENT_LABELS[eventType]}
                </td>
                <td className={styles.selectCell}>
                  <select
                    value={mapping?.target_stage_id ?? ''}
                    onChange={e => e.target.value && handleStageChange(eventType, Number(e.target.value))}
                    className={styles.stageSelect}
                    style={{ background: t.bgInput, border: `1px solid ${t.border}`, color: t.text }}
                  >
                    <option value="">— not mapped —</option>
                    {sortedStages.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </td>
                <td className={styles.toggleCell}>
                  <label className={styles.toggleLabel} style={{ cursor: mapping ? 'pointer' : 'default' }}>
                    <input
                      type="checkbox"
                      checked={mapping?.is_enabled ?? false}
                      disabled={!mapping}
                      onChange={e => mapping && handleToggle(eventType, e.target.checked)}
                      className={styles.checkbox}
                      style={{ cursor: mapping ? 'pointer' : 'default' }}
                    />
                    <span className={styles.toggleText} style={{ color: mapping?.is_enabled ? t.green : t.textMuted }}>
                      {mapping?.is_enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </label>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
