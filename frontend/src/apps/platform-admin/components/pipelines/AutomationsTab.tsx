/**
 * AutomationsTab — Zapier-style When/Then rule builder.
 * Requirements: 9.6
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import {
  usePipelineRules, usePipelineStages,
  useCreateRule, useUpdateRule, useDeleteRule,
  useAdminTemplates,
} from '../../hooks/usePipelineQueries';
import type { PipelineActionRule, PipelineStage, RuleCreate, RuleUpdate, ActionType } from '../../api/pipelinesApi';

interface Props { pipelineId: number; }

const TRIGGER_OPTIONS = [
  { value: 'on_stage_enter', label: 'Lead enters a stage', icon: '→' },
  { value: 'on_event',       label: 'A platform event fires', icon: '⚡' },
];

const CONDITION_OPTIONS = [
  { value: 'always',    label: 'Always (no condition)',  desc: 'Run every time the trigger fires' },
  { value: 'bucket_is', label: 'Lead score bucket is…',  desc: 'e.g. HOT, WARM, NURTURE' },
  { value: 'stage_is',  label: 'Lead is in stage…',      desc: 'Match by stage key' },
];

const ACTION_OPTIONS: { value: ActionType; label: string; icon: string; desc: string }[] = [
  { value: 'send_email_template',       label: 'Send Email Template',      icon: '✉️', desc: 'Send a pre-built email template to the lead' },
  { value: 'send_qualification_form',   label: 'Send Qualification Form',  icon: '📋', desc: 'Send a qualification form to the lead' },
  { value: 'send_bucket_followup_email',label: 'Send Bucket Follow-up',    icon: '📨', desc: 'Send a follow-up email based on score bucket' },
  { value: 'move_to_stage',             label: 'Move to Stage',            icon: '➡️', desc: 'Move the lead to a specific pipeline stage' },
];

export const AutomationsTab: React.FC<Props> = ({ pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: rules = [], isLoading } = usePipelineRules(pipelineId);
  const { data: stages = [] } = usePipelineStages(pipelineId);
  const { data: templates = [] } = useAdminTemplates();
  const createRule = useCreateRule();
  const sorted = [...rules].sort((a, b) => a.position - b.position);

  const handleNewRule = async () => {
    await createRule.mutateAsync({
      pipelineId,
      name: 'New Automation',
      trigger_type: 'on_stage_enter',
      condition_type: 'always',
      is_enabled: false,
      position: sorted.length + 1,
      steps: [],
    } as RuleCreate & { pipelineId: number });
  };

  if (isLoading) return <div style={{ color: t.textFaint, fontSize: 14, padding: 24 }}>Loading…</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Explainer */}
      <div style={{
        background: t.accentBg, border: `1px solid ${t.accent}22`,
        borderRadius: 12, padding: '14px 18px',
        display: 'flex', alignItems: 'flex-start', gap: 12,
      }}>
        <span style={{ fontSize: 20 }}>⚡</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: t.text, marginBottom: 2 }}>Automate your pipeline</div>
          <div style={{ fontSize: 12, color: t.textMuted }}>
            Create rules that run automatically. Each rule has a <strong>trigger</strong> (when something happens),
            an optional <strong>condition</strong> (only if…), and one or more <strong>actions</strong> (do this).
          </div>
        </div>
      </div>

      {sorted.length === 0 && (
        <div style={{
          background: t.bgCard, border: `1.5px dashed ${t.border}`,
          borderRadius: 14, padding: '48px 24px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🤖</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: t.text, marginBottom: 6 }}>No automations yet</div>
          <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 20 }}>
            Automations save time by taking actions automatically when leads move through your pipeline.
          </div>
          <button
            onClick={handleNewRule}
            disabled={createRule.isPending}
            style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 9, color: '#fff',
              fontSize: 13, fontWeight: 600, padding: '10px 22px', cursor: 'pointer',
            }}
          >
            Create your first automation
          </button>
        </div>
      )}

      {sorted.map(rule => (
        <RuleCard key={rule.id} rule={rule} pipelineId={pipelineId} stages={stages} templates={templates} />
      ))}

      {sorted.length > 0 && (
        <button
          onClick={handleNewRule}
          disabled={createRule.isPending}
          style={{
            background: t.bgCard, border: `1.5px dashed ${t.border}`,
            borderRadius: 12, color: t.textMuted, fontSize: 13, fontWeight: 600,
            padding: '12px', cursor: 'pointer', transition: 'all 0.15s',
          }}
        >
          {createRule.isPending ? 'Creating…' : '+ Add Automation'}
        </button>
      )}
    </div>
  );
};

// ── Rule Card ─────────────────────────────────────────────────────────────

const RuleCard: React.FC<{ rule: PipelineActionRule; pipelineId: number; stages: PipelineStage[]; templates: { id: number; name: string; subject: string }[] }> = ({ rule, pipelineId, stages, templates }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const updateRule = useUpdateRule();
  const deleteRule = useDeleteRule();
  const [expanded, setExpanded] = useState(!rule.name || rule.name === 'New Automation');
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

  const triggerLabel = TRIGGER_OPTIONS.find(o => o.value === rule.trigger_type)?.label ?? rule.trigger_type;
  const stageName = stages.find(s => s.id === rule.trigger_stage_id)?.name;
  const summary = stageName ? `${triggerLabel}: ${stageName}` : triggerLabel;

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
      steps: [...(d.steps ?? []), { action_type: 'send_email_template' as ActionType, action_config_json: '{}', position: (d.steps?.length ?? 0) + 1 }],
    }));
  };

  const removeStep = (idx: number) => {
    setDraft(d => ({ ...d, steps: (d.steps ?? []).filter((_, i) => i !== idx) }));
  };

  const sel: React.CSSProperties = {
    background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
    color: t.text, fontSize: 13, padding: '8px 12px', width: '100%', boxSizing: 'border-box' as const,
  };

  return (
    <div style={{
      background: t.bgCard, border: `1px solid ${t.border}`,
      borderRadius: 14, overflow: 'hidden',
      opacity: rule.is_enabled ? 1 : 0.75,
    }}>
      {/* Header */}
      <div style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => setExpanded(e => !e)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textMuted, fontSize: 14, padding: 0, flexShrink: 0 }}
        >
          {expanded ? '▾' : '▸'}
        </button>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 2 }}>{rule.name}</div>
          <div style={{ fontSize: 12, color: t.textMuted, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ background: t.accentBg, color: t.accent, padding: '1px 7px', borderRadius: 6, fontSize: 11, fontWeight: 600 }}>WHEN</span>
            <span>{summary}</span>
            {rule.steps.length > 0 && (
              <>
                <span style={{ color: t.textFaint }}>→</span>
                <span style={{ background: '#16a34a22', color: '#16a34a', padding: '1px 7px', borderRadius: 6, fontSize: 11, fontWeight: 600 }}>THEN</span>
                <span>{rule.steps.length} action{rule.steps.length !== 1 ? 's' : ''}</span>
              </>
            )}
          </div>
        </div>

        {/* Toggle */}
        <button
          onClick={handleToggle}
          style={{
            background: rule.is_enabled ? '#16a34a22' : t.bgCardHover,
            border: `1px solid ${rule.is_enabled ? '#16a34a44' : t.border}`,
            borderRadius: 20, padding: '4px 12px', cursor: 'pointer',
            fontSize: 12, fontWeight: 600,
            color: rule.is_enabled ? '#16a34a' : t.textMuted,
            flexShrink: 0,
          }}
        >
          {rule.is_enabled ? '● On' : '○ Off'}
        </button>

        <button
          onClick={() => deleteRule.mutate({ pipelineId, ruleId: rule.id })}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 18, padding: '0 2px', flexShrink: 0, lineHeight: 1 }}
          title="Delete"
        >×</button>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div style={{ borderTop: `1px solid ${t.border}`, padding: '20px 18px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {/* Name */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 6 }}>
              Automation Name
            </label>
            <input
              value={draft.name ?? ''}
              onChange={e => setDraft(d => ({ ...d, name: e.target.value }))}
              style={sel}
              placeholder="e.g. Send welcome email on new lead"
            />
          </div>

          {/* WHEN block */}
          <ZapBlock
            color="#6366f1"
            label="WHEN"
            icon="⚡"
            description="This automation runs when…"
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Trigger event</label>
                <select value={draft.trigger_type ?? ''} onChange={e => setDraft(d => ({ ...d, trigger_type: e.target.value }))} style={sel}>
                  {TRIGGER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.icon} {o.label}</option>)}
                </select>
              </div>
              {(draft.trigger_type === 'on_stage_enter') && (
                <div>
                  <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Which stage?</label>
                  <select value={draft.trigger_stage_id ?? ''} onChange={e => setDraft(d => ({ ...d, trigger_stage_id: e.target.value ? Number(e.target.value) : undefined }))} style={sel}>
                    <option value="">Any stage</option>
                    {[...stages].sort((a, b) => a.position - b.position).map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </ZapBlock>

          <Connector />

          {/* IF block */}
          <ZapBlock color="#f59e0b" label="IF" icon="🔍" description="But only if…">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Condition</label>
                <select value={draft.condition_type ?? 'always'} onChange={e => setDraft(d => ({ ...d, condition_type: e.target.value }))} style={sel}>
                  {CONDITION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <div style={{ fontSize: 11, color: t.textFaint, marginTop: 4 }}>
                  {CONDITION_OPTIONS.find(o => o.value === draft.condition_type)?.desc}
                </div>
              </div>
              {draft.condition_type !== 'always' && (
                <div>
                  <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Value</label>
                  <input
                    value={draft.condition_value ?? ''}
                    onChange={e => setDraft(d => ({ ...d, condition_value: e.target.value }))}
                    style={sel}
                    placeholder={draft.condition_type === 'score_bucket' ? 'HOT, WARM, or NURTURE' : 'tag name'}
                  />
                </div>
              )}
            </div>
          </ZapBlock>

          <Connector />

          {/* THEN block */}
          <ZapBlock color="#16a34a" label="THEN" icon="✅" description="Do these actions…">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(draft.steps ?? []).length === 0 && (
                <div style={{ fontSize: 12, color: t.textFaint, fontStyle: 'italic' }}>No actions yet — add one below.</div>
              )}
      {(draft.steps ?? []).map((step, _idx) => (
                <ActionRow
                  key={_idx}
                  step={step}
                  idx={_idx}
                  onUpdate={(updated) => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === _idx ? updated : s) }))}
                  onRemove={() => removeStep(_idx)}
                  templates={templates}
                  stages={stages}
                />
              ))}
              <button
                onClick={addStep}
                style={{
                  background: 'none', border: `1.5px dashed ${t.border}`,
                  borderRadius: 8, color: t.textMuted, fontSize: 12,
                  padding: '8px', cursor: 'pointer', textAlign: 'center',
                }}
              >
                + Add action
              </button>
            </div>
          </ZapBlock>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button onClick={() => setExpanded(false)} style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '8px 16px', cursor: 'pointer' }}>
              Cancel
            </button>
            <button onClick={handleSave} disabled={updateRule.isPending} style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600, padding: '8px 20px', cursor: 'pointer' }}>
              {updateRule.isPending ? 'Saving…' : 'Save Automation'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Zap block ─────────────────────────────────────────────────────────────

const ZapBlock: React.FC<{ color: string; label: string; icon: string; description: string; children: React.ReactNode }> = ({ color, label, icon, description, children }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ border: `1.5px solid ${color}33`, borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ background: `${color}18`, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: `1px solid ${color}22` }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color, letterSpacing: '0.8px' }}>{label}</span>
        <span style={{ fontSize: 12, color: t.textMuted }}>{description}</span>
      </div>
      <div style={{ padding: '14px' }}>{children}</div>
    </div>
  );
};

// ── Connector arrow ───────────────────────────────────────────────────────

const Connector: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0', color: t.textFaint, fontSize: 18 }}>↓</div>
  );
};

// ── Action row ────────────────────────────────────────────────────────────

const ActionRow: React.FC<{
  step: { action_type: ActionType; action_config_json: string; position: number };
  idx: number;
  onUpdate: (s: { action_type: ActionType; action_config_json: string; position: number }) => void;
  onRemove: () => void;
  templates: { id: number; name: string; subject: string }[];
  stages: PipelineStage[];
}> = ({ step, idx: _idx, onUpdate, onRemove, templates, stages }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const opt = ACTION_OPTIONS.find(o => o.value === step.action_type);

  // Parse config for friendly display
  let config: Record<string, string> = {};
  try { config = JSON.parse(step.action_config_json); } catch { /* ignore */ }

  const sel: React.CSSProperties = {
    background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
    color: t.text, fontSize: 13, padding: '7px 10px', width: '100%', boxSizing: 'border-box' as const,
  };

  return (
    <div style={{ background: t.bgCardHover, border: `1px solid ${t.border}`, borderRadius: 10, padding: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 16 }}>{opt?.icon ?? '▶'}</span>
        <select
          value={step.action_type}
          onChange={e => onUpdate({ ...step, action_type: e.target.value as ActionType })}
          style={{ ...sel, flex: 1 }}
        >
          {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.icon} {o.label}</option>)}
        </select>
        <button onClick={onRemove} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 18, padding: '0 2px', lineHeight: 1 }}>×</button>
      </div>
      {opt && <div style={{ fontSize: 11, color: t.textFaint, marginBottom: 8 }}>{opt.desc}</div>}

      {/* Friendly config fields per action type */}
      {step.action_type === 'send_email_template' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 11, color: t.textFaint }}>Email template</label>
          <select
            value={config.template_id ?? ''}
            onChange={e => onUpdate({ ...step, action_config_json: JSON.stringify({ ...config, template_id: e.target.value }) })}
            style={sel}
          >
            <option value="">— select a template —</option>
            {templates.map(tpl => (
              <option key={tpl.id} value={String(tpl.id)}>{tpl.name}</option>
            ))}
          </select>
          {templates.length === 0 && (
            <div style={{ fontSize: 11, color: t.textFaint }}>No templates found. Create one in the Templates page first.</div>
          )}
        </div>
      )}
      {step.action_type === 'send_qualification_form' && (
        <input placeholder="Form ID" value={config.form_id ?? ''} onChange={e => onUpdate({ ...step, action_config_json: JSON.stringify({ ...config, form_id: e.target.value }) })} style={sel} />
      )}
      {step.action_type === 'send_bucket_followup_email' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 11, color: t.textFaint }}>Email template (optional)</label>
          <select
            value={config.template_id ?? ''}
            onChange={e => onUpdate({ ...step, action_config_json: JSON.stringify({ ...config, template_id: e.target.value }) })}
            style={sel}
          >
            <option value="">— use default —</option>
            {templates.map(tpl => (
              <option key={tpl.id} value={String(tpl.id)}>{tpl.name}</option>
            ))}
          </select>
        </div>
      )}
      {step.action_type === 'move_to_stage' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 11, color: t.textFaint }}>Target stage</label>
          <select
            value={config.stage_id ?? ''}
            onChange={e => onUpdate({ ...step, action_config_json: JSON.stringify({ ...config, stage_id: e.target.value }) })}
            style={sel}
          >
            <option value="">— select a stage —</option>
            {[...stages].sort((a, b) => a.position - b.position).map(s => (
              <option key={s.id} value={String(s.id)}>{s.name}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};
