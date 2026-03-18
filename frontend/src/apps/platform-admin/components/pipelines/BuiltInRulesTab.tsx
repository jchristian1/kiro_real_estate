/**
 * BuiltInRulesTab — table of built-in event type → stage mappings.
 * Requirements: 9.5
 */

import React from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { usePipelineEventMappings, usePipelineStages, useUpsertEventMapping } from '../../hooks/usePipelineQueries';
import type { BuiltInEventType } from '../../api/pipelinesApi';

interface Props { pipelineId: number; }

const EVENT_LABELS: Record<BuiltInEventType, string> = {
  lead_created:                  'Lead Created',
  response_email_sent:           'Response Email Sent',
  qualification_form_sent:       'Qualification Form Sent',
  qualification_form_submitted:  'Qualification Form Submitted',
  qualification_bucket_hot:      'Qualified as Hot',
  qualification_bucket_warm:     'Qualified as Warm',
  qualification_bucket_nurture:  'Qualified as Nurture',
};

const ALL_EVENTS = Object.keys(EVENT_LABELS) as BuiltInEventType[];

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
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, overflow: 'hidden' }}>
      <div style={{ padding: '18px 24px', borderBottom: `1px solid ${t.border}` }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>Built-in Event Rules</div>
        <div style={{ fontSize: 12, color: t.textMuted, marginTop: 4 }}>
          When a platform event fires, automatically move the lead to the selected stage.
        </div>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Event', 'Move to Stage', 'Enabled'].map(h => (
              <th key={h} style={{
                textAlign: 'left', padding: '12px 24px',
                fontSize: 11, fontWeight: 600, color: t.textFaint,
                textTransform: 'uppercase', letterSpacing: '0.5px',
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
                <td style={{ padding: '14px 24px', fontSize: 13, color: t.text, fontWeight: 500 }}>
                  {EVENT_LABELS[eventType]}
                </td>
                <td style={{ padding: '14px 24px' }}>
                  <select
                    value={mapping?.target_stage_id ?? ''}
                    onChange={e => e.target.value && handleStageChange(eventType, Number(e.target.value))}
                    style={{
                      background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
                      color: t.text, fontSize: 13, padding: '6px 10px', minWidth: 180,
                    }}
                  >
                    <option value="">— not mapped —</option>
                    {sortedStages.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </td>
                <td style={{ padding: '14px 24px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: mapping ? 'pointer' : 'default' }}>
                    <input
                      type="checkbox"
                      checked={mapping?.is_enabled ?? false}
                      disabled={!mapping}
                      onChange={e => mapping && handleToggle(eventType, e.target.checked)}
                      style={{ width: 16, height: 16, cursor: mapping ? 'pointer' : 'default' }}
                    />
                    <span style={{ fontSize: 13, color: mapping?.is_enabled ? t.green : t.textMuted }}>
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
