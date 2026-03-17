/**
 * AutomationsTab — When/Then rule card builder.
 * Requirements: 9.6
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import {
  usePipelineRules, usePipelineStages,
  useCreateRule, useUpdateRule, useDeleteRule,
} from '../../hooks/usePipelineQueries';
import type { PipelineActionRule, PipelineStage, RuleCreate, RuleUpdate, ActionType } from '../../api/pipelinesApi';

interface Props { pipelineId: number; }

const TRIGGER_TYPES = ['stage_entered', 'stage_exited', 'event_fired'];
const CONDITION_TYPES = ['always', 'score_bucket', 'tag_present'];
const ACTION_TYPES: ActionType[] = ['send_email', 'send_form', 'update_score', 'add_tag', 'webhook'];

export const AutomationsTab: React.FC<Props> = ({ pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: rules = [], isLoading } = usePipelineRules(pipelineId);
  const { data: stages = [] } = usePipelineStages(pipelineId);
  const createRule = useCreateRule();

  const sorted = [...rules].sort((a, b) => a.position - b.position);

  const handleNewRule = async () => {
    await createRule.mutateAsync({
      pipelineId,
      name: 'New Rule',
      trigger_type: 'stage_entered',
      condition_type: 'always',
      is_enabled: false,
      position: sorted.length + 1,
      steps: [],
    } as RuleCreate & { pipelineId: number });
  };

  if (isLoading) {
    return <div style={{ color: t.textFaint, fontSize: 14, padding: 24 }}>Loading rules…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {sorted.length === 0 && (
        <div style={{
          background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14,
          padding: '40px 24px', textAlign: 'center', color: t.textMuted, fontSize: 13,
        }}>
          No automation rules yet. Create one to automate actions when leads move through stages.
        </div>
      )}

      {sorted.map(rule => (
        <RuleCard key={rule.id} rule={rule} pipelineId={pipelineId} stages={stages} />
      ))}

      <button
        onClick={handleNewRule}
        disabled={createRule.isPending}
        style={{
          background: t.accentBg, border: `1.5px dashed ${t.accent}`, borderRadius: 12,
          color: t.accent, fontSize: 13, fontWeight: 600, padding: '12px',
          cursor: 'pointer', transition: 'all 0.15s',
        }}
      >
        {createRule.isPending ? 'Creating…' : '+ New Rule'}
      </button>
    </div>
  );
};

// ── Rule Card ─────────────────────────────────────────────────────────────

const RuleCard: React.FC<{ rule: PipelineActionRule; pipelineId: number; stages: PipelineStage[] }> = ({ rule, pipelineId, stages }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const updateRule = useUpdateRule();
  const deleteRule = useDeleteRule();
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useState<RuleUpdate>({
    name: rule.name,
    trigger_type: rule.trigger_type,
    trigger_stage_id: rule.trigger_stage_id,
    trigger_event_type: rule.trigger_event_type,
    condition_type: rule.condition_type,
    condition_value: rule.condition_value,
    is_enabled: rule.is_enabled,
    steps: rule.steps.map(s => ({ action_type: s.action_type, action_config_json: s.action_config_json, position: s.position })),
  });

  const handleSave = async () => {
    await updateRule.mutateAsync({ pipelineId, ruleId: rule.id, ...draft });
    setExpanded(false);
  };

  const handleToggle = () => {
    updateRule.mutate({ pipelineId, ruleId: rule.id, is_enabled: !rule.is_enabled });
  };

  const addStep = () => {
    setDraft(d => ({
      ...d,
      steps: [...(d.steps ?? []), { action_type: 'send_email', action_config_json: '{}', position: (d.steps?.length ?? 0) + 1 }],
    }));
  };

  const removeStep = (idx: number) => {
    setDraft(d => ({ ...d, steps: (d.steps ?? []).filter((_, i) => i !== idx) }));
  };

  const inputStyle: React.CSSProperties = {
    background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
    color: t.text, fontSize: 13, padding: '7px 10px',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: t.textFaint,
    textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4, display: 'block',
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, overflow: 'hidden' }}>
      {/* Card header */}
      <div style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => setExpanded(e => !e)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textMuted, fontSize: 14, padding: 0, lineHeight: 1 }}
        >
          {expanded ? '▾' : '▸'}
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>{rule.name}</div>
          <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
            WHEN {rule.trigger_type.replace(/_/g, ' ')} · {rule.steps.length} action{rule.steps.length !== 1 ? 's' : ''}
          </div>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input type="checkbox" checked={rule.is_enabled} onChange={handleToggle} style={{ width: 15, height: 15, cursor: 'pointer' }} />
          <span style={{ fontSize: 12, color: rule.is_enabled ? t.green : t.textMuted }}>
            {rule.is_enabled ? 'On' : 'Off'}
          </span>
        </label>
        <button
          onClick={() => deleteRule.mutate({ pipelineId, ruleId: rule.id })}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 16, padding: '0 4px' }}
          title="Delete rule"
        >
          ×
        </button>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div style={{ borderTop: `1px solid ${t.border}`, padding: '18px 18px 14px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Name */}
          <div>
            <label style={labelStyle}>Rule Name</label>
            <input value={draft.name ?? ''} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' }} />
          </div>

          {/* WHEN */}
          <div style={{ background: t.bgCardHover, borderRadius: 10, padding: '14px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: t.accent, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 10 }}>WHEN</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={labelStyle}>Trigger</label>
                <select value={draft.trigger_type ?? ''} onChange={e => setDraft(d => ({ ...d, trigger_type: e.target.value }))} style={inputStyle}>
                  {TRIGGER_TYPES.map(tt => <option key={tt} value={tt}>{tt.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              {(draft.trigger_type === 'stage_entered' || draft.trigger_type === 'stage_exited') && (
                <div>
                  <label style={labelStyle}>Stage</label>
                  <select value={draft.trigger_stage_id ?? ''} onChange={e => setDraft(d => ({ ...d, trigger_stage_id: e.target.value ? Number(e.target.value) : undefined }))} style={inputStyle}>
                    <option value="">Any stage</option>
                    {stages.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
              )}
            </div>
          </div>

          {/* AND condition */}
          <div style={{ background: t.bgCardHover, borderRadius: 10, padding: '14px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: t.textMuted, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 10 }}>AND (condition)</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={labelStyle}>Condition</label>
                <select value={draft.condition_type ?? ''} onChange={e => setDraft(d => ({ ...d, condition_type: e.target.value }))} style={inputStyle}>
                  {CONDITION_TYPES.map(ct => <option key={ct} value={ct}>{ct.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              {draft.condition_type !== 'always' && (
                <div>
                  <label style={labelStyle}>Value</label>
                  <input value={draft.condition_value ?? ''} onChange={e => setDraft(d => ({ ...d, condition_value: e.target.value }))} style={inputStyle} placeholder="e.g. HOT" />
                </div>
              )}
            </div>
          </div>

          {/* THEN steps */}
          <div style={{ background: t.bgCardHover, borderRadius: 10, padding: '14px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: t.green, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 10 }}>THEN</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(draft.steps ?? []).map((step, idx) => (
                <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <select
                    value={step.action_type}
                    onChange={e => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === idx ? { ...s, action_type: e.target.value as ActionType } : s) }))}
                    style={{ ...inputStyle, flex: 1 }}
                  >
                    {ACTION_TYPES.map(at => <option key={at} value={at}>{at.replace(/_/g, ' ')}</option>)}
                  </select>
                  <input
                    value={step.action_config_json}
                    onChange={e => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === idx ? { ...s, action_config_json: e.target.value } : s) }))}
                    placeholder='{"key":"value"}'
                    style={{ ...inputStyle, flex: 2, fontFamily: 'monospace', fontSize: 12 }}
                  />
                  <button onClick={() => removeStep(idx)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.red, fontSize: 16, padding: '0 4px' }}>×</button>
                </div>
              ))}
              <button onClick={addStep} style={{ background: 'none', border: `1px dashed ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 12, padding: '7px', cursor: 'pointer' }}>
                + Add step
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={() => setExpanded(false)} style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '8px 16px', cursor: 'pointer' }}>
              Cancel
            </button>
            <button onClick={handleSave} disabled={updateRule.isPending} style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600, padding: '8px 18px', cursor: 'pointer' }}>
              {updateRule.isPending ? 'Saving…' : 'Save Rule'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
