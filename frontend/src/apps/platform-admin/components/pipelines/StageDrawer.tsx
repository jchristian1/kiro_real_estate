/**
 * StageDrawer — unified stage config panel.
 * Shows stage settings, entry triggers (event mappings), and automations
 * all in one place so users never need to switch tabs.
 * Requirements: 9.4, 2.10
 */

import React, { useState, useEffect } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import {
  useUpdateStage, useDeleteStage,
  usePipelineEventMappings, useUpsertEventMapping,
  usePipelineRules, useCreateRule, useUpdateRule, useDeleteRule,
  useAdminTemplates,
} from '../../hooks/usePipelineQueries';
import type {
  PipelineStage, StageCategory, BuiltInEventType,
  ActionType, RuleCreate, RuleUpdate,
  PipelineActionRule,
} from '../../api/pipelinesApi';

interface Props {
  stage: PipelineStage;
  pipelineId: number;
  stages: PipelineStage[];
  onClose: () => void;
}

const COLORS = ['#6366f1', '#34d399', '#f87171', '#fb923c', '#fbbf24', '#60a5fa', '#a78bfa', '#f472b6', '#2dd4bf', '#e879f9'];
const CATEGORIES: StageCategory[] = ['open', 'in_progress', 'waiting', 'won', 'lost'];

const EVENT_LABELS: Record<BuiltInEventType, string> = {
  lead_created:                   '🆕 Lead created',
  response_email_sent:            '✉️ Response email sent',
  qualification_form_sent:        '📋 Qualification form sent',
  qualification_form_submitted:   '✅ Qualification form submitted',
  qualification_bucket_hot:       '🔥 Score bucket → HOT',
  qualification_bucket_warm:      '🌤 Score bucket → WARM',
  qualification_bucket_nurture:   '🌱 Score bucket → NURTURE',
};

const ACTION_OPTIONS: { value: ActionType; label: string; icon: string }[] = [
  { value: 'send_email_template',        label: 'Send Email Template',     icon: '✉️' },
  { value: 'send_qualification_form',    label: 'Send Qualification Form', icon: '📋' },
  { value: 'send_bucket_followup_email', label: 'Send Bucket Follow-up',   icon: '📨' },
  { value: 'move_to_stage',              label: 'Move to Stage',           icon: '➡️' },
];

type DrawerSection = 'settings' | 'triggers' | 'automations';

export const StageDrawer: React.FC<Props> = ({ stage, pipelineId, stages, onClose }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [section, setSection] = useState<DrawerSection>('settings');

  const inputStyle: React.CSSProperties = {
    background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
    color: t.text, fontSize: 13, padding: '8px 12px', width: '100%', boxSizing: 'border-box',
  };

  const tabs: { id: DrawerSection; label: string; icon: string }[] = [
    { id: 'settings',    label: 'Settings',    icon: '⚙️' },
    { id: 'triggers',    label: 'Triggers',    icon: '🔌' },
    { id: 'automations', label: 'Automations', icon: '⚡' },
  ];

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 900, background: 'rgba(0,0,0,0.3)' }} />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 901,
        width: 420, background: theme === 'dark' ? '#16161e' : '#fff',
        border: `1px solid ${t.border}`, borderRight: 'none',
        boxShadow: '-8px 0 32px rgba(0,0,0,0.2)',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{ padding: '18px 20px 0', borderBottom: `1px solid ${t.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: stage.color, flexShrink: 0 }} />
              <div style={{ fontSize: 16, fontWeight: 700, color: t.text }}>{stage.name}</div>
            </div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textMuted, fontSize: 20, lineHeight: 1 }}>×</button>
          </div>
          {/* Section tabs */}
          <div style={{ display: 'flex', gap: 0 }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setSection(tab.id)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: '8px 14px', fontSize: 13,
                  fontWeight: section === tab.id ? 600 : 400,
                  color: section === tab.id ? t.accent : t.textMuted,
                  borderBottom: section === tab.id ? `2px solid ${t.accent}` : '2px solid transparent',
                  marginBottom: -1, transition: 'all 0.15s',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
              >
                <span>{tab.icon}</span> {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Section content */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {section === 'settings' && (
            <SettingsSection
              stage={stage} pipelineId={pipelineId} stages={stages}
              onClose={onClose} inputStyle={inputStyle}
            />
          )}
          {section === 'triggers' && (
            <TriggersSection stage={stage} pipelineId={pipelineId} inputStyle={inputStyle} />
          )}
          {section === 'automations' && (
            <AutomationsSection stage={stage} pipelineId={pipelineId} stages={stages} inputStyle={inputStyle} />
          )}
        </div>
      </div>
    </>
  );
};

// ── Settings section ──────────────────────────────────────────────────────

const SettingsSection: React.FC<{
  stage: PipelineStage; pipelineId: number; stages: PipelineStage[];
  onClose: () => void; inputStyle: React.CSSProperties;
}> = ({ stage, pipelineId, stages, onClose, inputStyle }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const updateStage = useUpdateStage();
  const deleteStage = useDeleteStage();

  const [name, setName] = useState(stage.name);
  const [key, setKey] = useState(stage.key);
  const [color, setColor] = useState(stage.color);
  const [category, setCategory] = useState<StageCategory>(stage.category);
  const [isDefault, setIsDefault] = useState(stage.is_default);
  const [isClosedWon, setIsClosedWon] = useState(stage.is_closed_won);
  const [isClosedLost, setIsClosedLost] = useState(stage.is_closed_lost);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [reassignTo, setReassignTo] = useState<number | ''>('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    setKey(name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''));
  }, [name]);

  const labelStyle: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: t.textFaint,
    textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6, display: 'block',
  };

  const handleSave = async () => {
    await updateStage.mutateAsync({ pipelineId, stageId: stage.id, name, key, color, category, is_default: isDefault, is_closed_won: isClosedWon, is_closed_lost: isClosedLost });
    onClose();
  };

  const handleDelete = async () => {
    setDeleteError(null);
    try {
      await deleteStage.mutateAsync({ pipelineId, stageId: stage.id, reassignTo: reassignTo ? Number(reassignTo) : undefined });
      onClose();
    } catch (err: unknown) {
      setDeleteError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete stage.');
    }
  };

  const otherStages = stages.filter(s => s.id !== stage.id);

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <label style={labelStyle}>Name</label>
        <input value={name} onChange={e => setName(e.target.value)} style={inputStyle} />
      </div>
      <div>
        <label style={labelStyle}>Key (auto-generated)</label>
        <input value={key} onChange={e => setKey(e.target.value)} style={{ ...inputStyle, color: t.textMuted }} />
      </div>
      <div>
        <label style={labelStyle}>Color</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {COLORS.map(c => (
            <button key={c} type="button" onClick={() => setColor(c)} style={{ width: 26, height: 26, borderRadius: '50%', background: c, border: 'none', cursor: 'pointer', outline: color === c ? `2.5px solid ${t.text}` : 'none', outlineOffset: 2 }} />
          ))}
          <input type="color" value={color} onChange={e => setColor(e.target.value)} style={{ width: 26, height: 26, borderRadius: '50%', border: 'none', cursor: 'pointer', padding: 0 }} />
        </div>
      </div>
      <div>
        <label style={labelStyle}>Category</label>
        <select value={category} onChange={e => setCategory(e.target.value as StageCategory)} style={inputStyle}>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[
          { label: 'Default stage (new leads start here)', val: isDefault, set: setIsDefault },
          { label: 'Closed Won', val: isClosedWon, set: (v: boolean) => { setIsClosedWon(v); if (v) setIsClosedLost(false); } },
          { label: 'Closed Lost', val: isClosedLost, set: (v: boolean) => { setIsClosedLost(v); if (v) setIsClosedWon(false); } },
        ].map(({ label, val, set }) => (
          <label key={label} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
            <input type="checkbox" checked={val} onChange={e => set(e.target.checked)} style={{ width: 16, height: 16, cursor: 'pointer' }} />
            <span style={{ fontSize: 13, color: t.text }}>{label}</span>
          </label>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, paddingTop: 4 }}>
        <button onClick={handleSave} disabled={updateStage.isPending} style={{ flex: 1, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', borderRadius: 9, color: '#fff', fontSize: 13, fontWeight: 600, padding: '10px', cursor: 'pointer' }}>
          {updateStage.isPending ? 'Saving…' : 'Save Changes'}
        </button>
        <button onClick={() => setShowDeleteConfirm(true)} style={{ background: t.redBg, border: `1px solid ${t.red}`, borderRadius: 9, color: t.red, fontSize: 13, fontWeight: 600, padding: '10px 16px', cursor: 'pointer' }}>
          Delete
        </button>
      </div>

      {showDeleteConfirm && (
        <div style={{ background: t.redBg, border: `1px solid ${t.red}`, borderRadius: 10, padding: '14px' }}>
          <div style={{ fontSize: 13, color: t.text, marginBottom: 10 }}>Delete this stage? Leads will need to be reassigned.</div>
          {otherStages.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <label style={{ ...labelStyle, color: t.textMuted }}>Reassign leads to</label>
              <select value={reassignTo} onChange={e => setReassignTo(e.target.value ? Number(e.target.value) : '')} style={inputStyle}>
                <option value="">— none —</option>
                {otherStages.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}
          {deleteError && <div style={{ fontSize: 12, color: t.red, marginBottom: 8 }}>{deleteError}</div>}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleDelete} disabled={deleteStage.isPending} style={{ flex: 1, background: t.red, border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600, padding: '8px', cursor: 'pointer' }}>
              {deleteStage.isPending ? 'Deleting…' : 'Confirm Delete'}
            </button>
            <button onClick={() => { setShowDeleteConfirm(false); setDeleteError(null); }} style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '8px 12px', cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Triggers section ──────────────────────────────────────────────────────
// Shows all built-in events. For each event, user can toggle it on/off
// and it will map/unmap to this stage.

const TriggersSection: React.FC<{
  stage: PipelineStage; pipelineId: number; inputStyle: React.CSSProperties;
}> = ({ stage, pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: mappings = [] } = usePipelineEventMappings(pipelineId);
  const upsertMapping = useUpsertEventMapping();

  const allEvents = Object.keys(EVENT_LABELS) as BuiltInEventType[];

  // Find mapping for this event that points to THIS stage
  const getMappingForEvent = (eventType: BuiltInEventType) =>
    mappings.find(m => m.event_type === eventType);

  const isActive = (eventType: BuiltInEventType) => {
    const m = getMappingForEvent(eventType);
    return m?.target_stage_id === stage.id && m?.is_enabled;
  };

  const handleToggle = (eventType: BuiltInEventType) => {
    const currently = isActive(eventType);
    upsertMapping.mutate({
      pipelineId,
      eventType,
      target_stage_id: stage.id,
      is_enabled: !currently,
    });
  };

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 8 }}>
        Toggle which platform events automatically move a lead into <strong style={{ color: t.text }}>{stage.name}</strong>.
      </div>
      {allEvents.map(eventType => {
        const active = isActive(eventType);
        const mapping = getMappingForEvent(eventType);
        const pointsElsewhere = mapping && mapping.target_stage_id !== stage.id && mapping.is_enabled;

        return (
          <div
            key={eventType}
            style={{
              background: active ? t.accentBg : t.bgCard,
              border: `1px solid ${active ? t.accent + '44' : t.border}`,
              borderRadius: 10, padding: '12px 14px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: t.text }}>{EVENT_LABELS[eventType]}</div>
              {pointsElsewhere && (
                <div style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>
                  Currently mapped to another stage
                </div>
              )}
            </div>
            <button
              onClick={() => handleToggle(eventType)}
              disabled={upsertMapping.isPending}
              style={{
                background: active ? t.accent : t.bgCardHover,
                border: `1px solid ${active ? t.accent : t.border}`,
                borderRadius: 20, padding: '4px 14px', cursor: 'pointer',
                fontSize: 12, fontWeight: 600,
                color: active ? '#fff' : t.textMuted,
                flexShrink: 0, transition: 'all 0.15s',
              }}
            >
              {active ? '● On' : '○ Off'}
            </button>
          </div>
        );
      })}
    </div>
  );
};

// ── Automations section ───────────────────────────────────────────────────
// Shows rules that trigger on entering THIS stage. Can add new ones inline.

const AutomationsSection: React.FC<{
  stage: PipelineStage; pipelineId: number; stages: PipelineStage[]; inputStyle: React.CSSProperties;
}> = ({ stage, pipelineId, stages, inputStyle }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: allRules = [] } = usePipelineRules(pipelineId);
  const { data: templates = [] } = useAdminTemplates();
  const createRule = useCreateRule();
  const deleteRule = useDeleteRule();

  // Rules that trigger on entering this specific stage
  const stageRules = allRules.filter(
    r => r.trigger_type === 'on_stage_enter' && r.trigger_stage_id === stage.id
  );

  const handleAddRule = async () => {
    await createRule.mutateAsync({
      pipelineId,
      name: `On enter ${stage.name}`,
      trigger_type: 'on_stage_enter',
      trigger_stage_id: stage.id,
      condition_type: 'always',
      is_enabled: false,
      position: allRules.length + 1,
      steps: [],
    } as RuleCreate & { pipelineId: number });
  };

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 12, color: t.textMuted }}>
        These automations run when a lead enters <strong style={{ color: t.text }}>{stage.name}</strong>.
      </div>

      {stageRules.length === 0 && (
        <div style={{ background: t.bgCard, border: `1.5px dashed ${t.border}`, borderRadius: 10, padding: '24px', textAlign: 'center' }}>
          <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 12 }}>No automations for this stage yet.</div>
          <button
            onClick={handleAddRule}
            disabled={createRule.isPending}
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600, padding: '8px 18px', cursor: 'pointer' }}
          >
            + Add automation
          </button>
        </div>
      )}

      {stageRules.map(rule => (
        <StageRuleCard
          key={rule.id}
          rule={rule}
          pipelineId={pipelineId}
          stages={stages}
          templates={templates}
          inputStyle={inputStyle}
          onDelete={() => deleteRule.mutate({ pipelineId, ruleId: rule.id })}
        />
      ))}

      {stageRules.length > 0 && (
        <button
          onClick={handleAddRule}
          disabled={createRule.isPending}
          style={{ background: t.bgCard, border: `1.5px dashed ${t.border}`, borderRadius: 10, color: t.textMuted, fontSize: 13, fontWeight: 600, padding: '10px', cursor: 'pointer' }}
        >
          {createRule.isPending ? 'Adding…' : '+ Add automation'}
        </button>
      )}
    </div>
  );
};

// ── Inline rule card ──────────────────────────────────────────────────────

const StageRuleCard: React.FC<{
  rule: PipelineActionRule;
  pipelineId: number;
  stages: PipelineStage[];
  templates: { id: number; name: string; subject: string }[];
  inputStyle: React.CSSProperties;
  onDelete: () => void;
}> = ({ rule, pipelineId, stages, templates, inputStyle, onDelete }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const updateRule = useUpdateRule();
  const [expanded, setExpanded] = useState(rule.name === `On enter ${rule.trigger_stage_id}` || rule.steps.length === 0);
  const [draft, setDraft] = useState<RuleUpdate>({
    name: rule.name,
    condition_type: rule.condition_type,
    condition_value: rule.condition_value,
    is_enabled: rule.is_enabled,
    steps: rule.steps.map(s => ({ action_type: s.action_type, action_config_json: s.action_config_json, position: s.position })),
  });

  const sel = inputStyle;

  const addStep = () => setDraft(d => ({
    ...d,
    steps: [...(d.steps ?? []), { action_type: 'send_email_template' as ActionType, action_config_json: '{}', position: (d.steps?.length ?? 0) + 1 }],
  }));

  const removeStep = (idx: number) => setDraft(d => ({ ...d, steps: (d.steps ?? []).filter((_, i) => i !== idx) }));

  const handleSave = async () => {
    await updateRule.mutateAsync({ pipelineId, ruleId: rule.id, ...draft });
    setExpanded(false);
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 12, overflow: 'hidden', opacity: rule.is_enabled ? 1 : 0.75 }}>
      {/* Header */}
      <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <button onClick={() => setExpanded(e => !e)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textMuted, fontSize: 13, padding: 0, flexShrink: 0 }}>
          {expanded ? '▾' : '▸'}
        </button>
        <div style={{ flex: 1, fontSize: 13, fontWeight: 600, color: t.text }}>{rule.name}</div>
        <button
          onClick={() => updateRule.mutate({ pipelineId, ruleId: rule.id, is_enabled: !rule.is_enabled })}
          style={{ background: rule.is_enabled ? '#16a34a22' : t.bgCardHover, border: `1px solid ${rule.is_enabled ? '#16a34a44' : t.border}`, borderRadius: 20, padding: '3px 10px', cursor: 'pointer', fontSize: 11, fontWeight: 600, color: rule.is_enabled ? '#16a34a' : t.textMuted, flexShrink: 0 }}
        >
          {rule.is_enabled ? '● On' : '○ Off'}
        </button>
        <button onClick={onDelete} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 16, padding: '0 2px', lineHeight: 1 }}>×</button>
      </div>

      {expanded && (
        <div style={{ borderTop: `1px solid ${t.border}`, padding: '14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Name */}
          <div>
            <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Name</label>
            <input value={draft.name ?? ''} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} style={sel} />
          </div>

          {/* IF condition */}
          <div>
            <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Condition (IF)</label>
            <select value={draft.condition_type ?? 'always'} onChange={e => setDraft(d => ({ ...d, condition_type: e.target.value }))} style={sel}>
              <option value="always">Always</option>
              <option value="bucket_is">Score bucket is…</option>
              <option value="stage_is">Lead is in stage…</option>
            </select>
          </div>
          {draft.condition_type !== 'always' && (
            <input
              value={draft.condition_value ?? ''}
              onChange={e => setDraft(d => ({ ...d, condition_value: e.target.value }))}
              placeholder={draft.condition_type === 'bucket_is' ? 'HOT, WARM, or NURTURE' : 'stage key'}
              style={sel}
            />
          )}

          {/* THEN actions */}
          <div>
            <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 6 }}>Actions (THEN)</label>
            {(draft.steps ?? []).length === 0 && (
              <div style={{ fontSize: 12, color: t.textFaint, fontStyle: 'italic', marginBottom: 8 }}>No actions yet.</div>
            )}
            {(draft.steps ?? []).map((step, idx) => (
              <div key={idx} style={{ background: t.bgCardHover, border: `1px solid ${t.border}`, borderRadius: 8, padding: '10px', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <select value={step.action_type} onChange={e => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === idx ? { ...s, action_type: e.target.value as ActionType } : s) }))} style={{ ...sel, flex: 1 }}>
                    {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.icon} {o.label}</option>)}
                  </select>
                  <button onClick={() => removeStep(idx)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 16, padding: '0 2px', lineHeight: 1 }}>×</button>
                </div>
                {/* Config per action type */}
                {step.action_type === 'send_email_template' && (
                  <select
                    value={(() => { try { return JSON.parse(step.action_config_json).template_id ?? ''; } catch { return ''; } })()}
                    onChange={e => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === idx ? { ...s, action_config_json: JSON.stringify({ template_id: e.target.value }) } : s) }))}
                    style={sel}
                  >
                    <option value="">— select template —</option>
                    {templates.map(tpl => <option key={tpl.id} value={String(tpl.id)}>{tpl.name}</option>)}
                  </select>
                )}
                {step.action_type === 'send_bucket_followup_email' && (
                  <select
                    value={(() => { try { return JSON.parse(step.action_config_json).template_id ?? ''; } catch { return ''; } })()}
                    onChange={e => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === idx ? { ...s, action_config_json: JSON.stringify({ template_id: e.target.value }) } : s) }))}
                    style={sel}
                  >
                    <option value="">— use default —</option>
                    {templates.map(tpl => <option key={tpl.id} value={String(tpl.id)}>{tpl.name}</option>)}
                  </select>
                )}
                {step.action_type === 'move_to_stage' && (
                  <select
                    value={(() => { try { return JSON.parse(step.action_config_json).stage_id ?? ''; } catch { return ''; } })()}
                    onChange={e => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === idx ? { ...s, action_config_json: JSON.stringify({ stage_id: e.target.value }) } : s) }))}
                    style={sel}
                  >
                    <option value="">— select stage —</option>
                    {[...stages].sort((a, b) => a.position - b.position).map(s => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
                  </select>
                )}
                {step.action_type === 'send_qualification_form' && (
                  <input placeholder="Form ID" value={(() => { try { return JSON.parse(step.action_config_json).form_id ?? ''; } catch { return ''; } })()} onChange={e => setDraft(d => ({ ...d, steps: (d.steps ?? []).map((s, i) => i === idx ? { ...s, action_config_json: JSON.stringify({ form_id: e.target.value }) } : s) }))} style={sel} />
                )}
              </div>
            ))}
            <button onClick={addStep} style={{ background: 'none', border: `1.5px dashed ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 12, padding: '7px', cursor: 'pointer', width: '100%' }}>
              + Add action
            </button>
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={() => setExpanded(false)} style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '7px 14px', cursor: 'pointer' }}>Cancel</button>
            <button onClick={handleSave} disabled={updateRule.isPending} style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600, padding: '7px 18px', cursor: 'pointer' }}>
              {updateRule.isPending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
