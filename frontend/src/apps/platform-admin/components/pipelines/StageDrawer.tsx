/**
 * StageDrawer — premium 2-section stage config panel.
 * Section 1: Settings (name, color, category, toggles)
 * Section 2: Actions (When/Then automation builder for this stage)
 * No tab switching — everything visible in one scroll.
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
  ActionType, RuleCreate,
  PipelineActionRule,
} from '../../api/pipelinesApi';

interface Props {
  stage: PipelineStage;
  pipelineId: number;
  stages: PipelineStage[];
  onClose: () => void;
}

const COLORS = [
  '#6366f1','#8b5cf6','#ec4899','#f43f5e',
  '#f97316','#eab308','#22c55e','#14b8a6',
  '#3b82f6','#06b6d4',
];
const CATEGORIES: { value: StageCategory; label: string; icon: string }[] = [
  { value: 'open',        label: 'Open',        icon: '○' },
  { value: 'in_progress', label: 'In Progress',  icon: '◑' },
  { value: 'waiting',     label: 'Waiting',      icon: '◷' },
  { value: 'won',         label: 'Won',          icon: '★' },
  { value: 'lost',        label: 'Lost',         icon: '✕' },
];
const EVENT_LABELS: Record<BuiltInEventType, string> = {
  lead_created:                 'Lead created',
  response_email_sent:          'Response email sent',
  qualification_form_sent:      'Qualification form sent',
  qualification_form_submitted: 'Qualification form submitted',
  qualification_bucket_hot:     'Score bucket → HOT',
  qualification_bucket_warm:    'Score bucket → WARM',
  qualification_bucket_nurture: 'Score bucket → NURTURE',
};
const ACTION_OPTIONS: { value: ActionType; label: string }[] = [
  { value: 'send_email_template',        label: 'Send email template'     },
  { value: 'send_qualification_form',    label: 'Send qualification form' },
  { value: 'send_bucket_followup_email', label: 'Send bucket follow-up'   },
  { value: 'move_to_stage',              label: 'Move to stage'           },
];

// ── Main drawer ───────────────────────────────────────────────────────────

export const StageDrawer: React.FC<Props> = ({ stage, pipelineId, stages, onClose }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';

  const drawerBg = isDark ? '#111118' : '#ffffff';
  const sectionBg = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)';
  const divider = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)';

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, zIndex: 900, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)' }}
      />

      {/* Drawer panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 901,
        width: 440,
        background: drawerBg,
        borderLeft: `1px solid ${divider}`,
        boxShadow: '-20px 0 60px rgba(0,0,0,0.35)',
        display: 'flex', flexDirection: 'column',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}>

        {/* ── Header ── */}
        <div style={{
          padding: '20px 24px 18px',
          borderBottom: `1px solid ${divider}`,
          background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 14, height: 14, borderRadius: '50%',
                background: stage.color,
                boxShadow: `0 0 10px ${stage.color}88`,
                flexShrink: 0,
              }} />
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: t.text, letterSpacing: '-0.2px' }}>{stage.name}</div>
                <div style={{ fontSize: 11, color: t.textFaint, marginTop: 1 }}>Stage configuration</div>
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                border: 'none', borderRadius: 8, cursor: 'pointer',
                color: t.textMuted, fontSize: 18, width: 32, height: 32,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                lineHeight: 1, transition: 'background 0.15s',
              }}
            >×</button>
          </div>
        </div>

        {/* ── Scrollable body ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 0 24px' }}>

          {/* Section 1: Settings */}
          <SectionBlock label="Settings" icon="⚙" sectionBg={sectionBg} divider={divider}>
            <SettingsSection
              stage={stage} pipelineId={pipelineId} stages={stages}
              onClose={onClose}
            />
          </SectionBlock>

          {/* Section 2: Entry triggers */}
          <SectionBlock label="Entry Triggers" icon="⚡" sectionBg={sectionBg} divider={divider}>
            <TriggersSection stage={stage} pipelineId={pipelineId} />
          </SectionBlock>

          {/* Section 3: Actions */}
          <SectionBlock label="Actions" icon="▶" sectionBg={sectionBg} divider={divider}>
            <ActionsSection stage={stage} pipelineId={pipelineId} stages={stages} />
          </SectionBlock>

        </div>
      </div>
    </>
  );
};

// ── Section wrapper ───────────────────────────────────────────────────────

const SectionBlock: React.FC<{
  label: string; icon: string;
  sectionBg: string; divider: string;
  children: React.ReactNode;
}> = ({ label, icon, sectionBg, divider, children }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ marginTop: 0 }}>
      <div style={{
        padding: '14px 24px 10px',
        background: sectionBg,
        borderBottom: `1px solid ${divider}`,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ fontSize: 12, opacity: 0.5 }}>{icon}</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: t.textMuted, textTransform: 'uppercase', letterSpacing: '0.8px' }}>{label}</span>
      </div>
      <div style={{ padding: '16px 24px' }}>
        {children}
      </div>
      <div style={{ height: 1, background: divider }} />
    </div>
  );
};

// ── Settings section ──────────────────────────────────────────────────────

const SettingsSection: React.FC<{
  stage: PipelineStage; pipelineId: number; stages: PipelineStage[]; onClose: () => void;
}> = ({ stage, pipelineId, stages, onClose }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const updateStage = useUpdateStage();
  const deleteStage = useDeleteStage();

  const [name, setName] = useState(stage.name);
  const [key, setKey] = useState(stage.key);
  const [color, setColor] = useState(stage.color);
  const [category, setCategory] = useState<StageCategory>(stage.category);
  const [isDefault, setIsDefault] = useState(stage.is_default);
  const [isClosedWon, setIsClosedWon] = useState(stage.is_closed_won);
  const [isClosedLost, setIsClosedLost] = useState(stage.is_closed_lost);
  const [showDelete, setShowDelete] = useState(false);
  const [reassignTo, setReassignTo] = useState<number | ''>('');
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    setKey(name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''));
  }, [name]);

  const inp: React.CSSProperties = {
    background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
    border: `1px solid ${t.border}`, borderRadius: 8,
    color: t.text, fontSize: 13, padding: '8px 12px',
    width: '100%', boxSizing: 'border-box', outline: 'none',
  };

  const handleSave = async () => {
    await updateStage.mutateAsync({
      pipelineId, stageId: stage.id,
      name, key, color, category,
      is_default: isDefault, is_closed_won: isClosedWon, is_closed_lost: isClosedLost,
    });
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Name */}
      <div>
        <label style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 6 }}>Name</label>
        <input value={name} onChange={e => setName(e.target.value)} style={inp} />
      </div>

      {/* Key */}
      <div>
        <label style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 6 }}>Key</label>
        <input value={key} onChange={e => setKey(e.target.value)} style={{ ...inp, color: t.textMuted, fontFamily: 'monospace', fontSize: 12 }} />
      </div>

      {/* Color */}
      <div>
        <label style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 8 }}>Color</label>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', alignItems: 'center' }}>
          {COLORS.map(c => (
            <button key={c} type="button" onClick={() => setColor(c)} style={{
              width: 24, height: 24, borderRadius: '50%', background: c, border: 'none', cursor: 'pointer',
              outline: color === c ? `2.5px solid ${t.text}` : `2px solid transparent`,
              outlineOffset: 2, transition: 'outline 0.1s',
              boxShadow: color === c ? `0 0 8px ${c}88` : 'none',
            }} />
          ))}
          <input type="color" value={color} onChange={e => setColor(e.target.value)} style={{ width: 24, height: 24, borderRadius: '50%', border: 'none', cursor: 'pointer', padding: 0, background: 'none' }} title="Custom color" />
        </div>
      </div>

      {/* Category */}
      <div>
        <label style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 8 }}>Category</label>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {CATEGORIES.map(cat => (
            <button key={cat.value} type="button" onClick={() => setCategory(cat.value)} style={{
              background: category === cat.value ? t.accentBg : (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'),
              border: `1px solid ${category === cat.value ? t.accent + '66' : t.border}`,
              borderRadius: 8, padding: '5px 12px', cursor: 'pointer',
              fontSize: 12, fontWeight: category === cat.value ? 600 : 400,
              color: category === cat.value ? t.accent : t.textMuted,
              transition: 'all 0.15s',
            }}>
              {cat.icon} {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Toggles */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[
          { label: 'Default stage', sub: 'New leads start here', val: isDefault, set: setIsDefault },
          { label: 'Closed Won', sub: 'Marks lead as won', val: isClosedWon, set: (v: boolean) => { setIsClosedWon(v); if (v) setIsClosedLost(false); } },
          { label: 'Closed Lost', sub: 'Marks lead as lost', val: isClosedLost, set: (v: boolean) => { setIsClosedLost(v); if (v) setIsClosedWon(false); } },
        ].map(({ label, sub, val, set }) => (
          <label key={label} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
            border: `1px solid ${t.border}`, borderRadius: 10, padding: '10px 14px', cursor: 'pointer',
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: t.text }}>{label}</div>
              <div style={{ fontSize: 11, color: t.textFaint, marginTop: 1 }}>{sub}</div>
            </div>
            <div onClick={() => set(!val)} style={{
              width: 36, height: 20, borderRadius: 10,
              background: val ? t.accent : (isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)'),
              position: 'relative', transition: 'background 0.2s', flexShrink: 0, cursor: 'pointer',
            }}>
              <div style={{
                position: 'absolute', top: 2, left: val ? 18 : 2,
                width: 16, height: 16, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
              }} />
            </div>
          </label>
        ))}
      </div>

      {/* Save / Delete */}
      <div style={{ display: 'flex', gap: 8, paddingTop: 4 }}>
        <button onClick={handleSave} disabled={updateStage.isPending} style={{
          flex: 1, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none', borderRadius: 10, color: '#fff',
          fontSize: 13, fontWeight: 600, padding: '10px', cursor: 'pointer',
          boxShadow: '0 4px 14px rgba(99,102,241,0.35)',
        }}>
          {updateStage.isPending ? 'Saving…' : 'Save Changes'}
        </button>
        <button onClick={() => setShowDelete(true)} style={{
          background: 'transparent', border: `1px solid ${t.red}22`,
          borderRadius: 10, color: t.red, fontSize: 13, fontWeight: 600,
          padding: '10px 16px', cursor: 'pointer',
        }}>Delete</button>
      </div>

      {/* Delete confirm */}
      {showDelete && (
        <div style={{ background: t.redBg, border: `1px solid ${t.red}44`, borderRadius: 12, padding: 14 }}>
          <div style={{ fontSize: 13, color: t.text, marginBottom: 10, fontWeight: 500 }}>Delete "{stage.name}"?</div>
          {otherStages.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Reassign leads to</label>
              <select value={reassignTo} onChange={e => setReassignTo(e.target.value ? Number(e.target.value) : '')} style={inp}>
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
            <button onClick={() => { setShowDelete(false); setDeleteError(null); }} style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '8px 12px', cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Entry Triggers section ────────────────────────────────────────────────

const TriggersSection: React.FC<{ stage: PipelineStage; pipelineId: number }> = ({ stage, pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { data: mappings = [] } = usePipelineEventMappings(pipelineId);
  const upsertMapping = useUpsertEventMapping();

  const allEvents = Object.keys(EVENT_LABELS) as BuiltInEventType[];

  const isActive = (ev: BuiltInEventType) => {
    const m = mappings.find(x => x.event_type === ev);
    return m?.target_stage_id === stage.id && m?.is_enabled;
  };

  const pointsElsewhere = (ev: BuiltInEventType) => {
    const m = mappings.find(x => x.event_type === ev);
    return m && m.target_stage_id !== stage.id && m.is_enabled;
  };

  const toggle = (ev: BuiltInEventType) => {
    upsertMapping.mutate({ pipelineId, eventType: ev, target_stage_id: stage.id, is_enabled: !isActive(ev) });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 12, color: t.textFaint, marginBottom: 4 }}>
        When these platform events fire, leads automatically move into <span style={{ color: t.text, fontWeight: 600 }}>{stage.name}</span>.
      </div>
      {allEvents.map(ev => {
        const active = isActive(ev);
        const elsewhere = pointsElsewhere(ev);
        return (
          <div key={ev} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            background: active ? t.accentBg : (isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)'),
            border: `1px solid ${active ? t.accent + '44' : t.border}`,
            borderRadius: 10, padding: '10px 14px', transition: 'all 0.15s',
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, color: t.text, fontWeight: active ? 500 : 400 }}>{EVENT_LABELS[ev]}</div>
              {elsewhere && <div style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>Mapped to another stage</div>}
            </div>
            {/* Toggle pill */}
            <div onClick={() => toggle(ev)} style={{
              width: 36, height: 20, borderRadius: 10,
              background: active ? t.accent : (isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)'),
              position: 'relative', transition: 'background 0.2s', flexShrink: 0, cursor: 'pointer',
            }}>
              <div style={{
                position: 'absolute', top: 2, left: active ? 18 : 2,
                width: 16, height: 16, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ── Actions section ───────────────────────────────────────────────────────

const ActionsSection: React.FC<{
  stage: PipelineStage; pipelineId: number; stages: PipelineStage[];
}> = ({ stage, pipelineId, stages }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { data: allRules = [] } = usePipelineRules(pipelineId);
  const { data: templates = [] } = useAdminTemplates();
  const createRule = useCreateRule();
  const deleteRule = useDeleteRule();

  const stageRules = allRules.filter(
    r => r.trigger_type === 'on_stage_enter' && r.trigger_stage_id === stage.id
  );

  const handleAdd = async () => {
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* When header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: isDark ? 'rgba(99,102,241,0.08)' : 'rgba(99,102,241,0.06)',
        border: `1px solid ${t.accent}22`, borderRadius: 10, padding: '10px 14px',
      }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: t.accent, flexShrink: 0 }} />
        <span style={{ fontSize: 12, color: t.textMuted }}>
          <span style={{ fontWeight: 700, color: t.accent }}>When</span> a lead enters{' '}
          <span style={{ fontWeight: 600, color: t.text }}>{stage.name}</span>…
        </span>
      </div>

      {stageRules.length === 0 && (
        <div style={{
          background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
          border: `1.5px dashed ${t.border}`, borderRadius: 12,
          padding: '20px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 13, color: t.textFaint, marginBottom: 12 }}>No actions configured yet.</div>
          <button onClick={handleAdd} disabled={createRule.isPending} style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none',
            borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600,
            padding: '8px 18px', cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
          }}>
            + Add action
          </button>
        </div>
      )}

      {stageRules.map((rule, idx) => (
        <ActionRuleCard
          key={rule.id}
          rule={rule}
          index={idx}
          pipelineId={pipelineId}
          stages={stages}
          templates={templates}
          onDelete={() => deleteRule.mutate({ pipelineId, ruleId: rule.id })}
        />
      ))}

      {stageRules.length > 0 && (
        <button onClick={handleAdd} disabled={createRule.isPending} style={{
          background: 'none',
          border: `1.5px dashed ${t.border}`, borderRadius: 10,
          color: t.textMuted, fontSize: 13, fontWeight: 500,
          padding: '10px', cursor: 'pointer', width: '100%',
          transition: 'border-color 0.15s',
        }}>
          {createRule.isPending ? 'Adding…' : '+ Add another action'}
        </button>
      )}

      {/* Live summary */}
      {stageRules.length > 0 && (
        <LiveSummary stage={stage} rules={stageRules} stages={stages} templates={templates} />
      )}
    </div>
  );
};

// ── Action rule card ──────────────────────────────────────────────────────

const ActionRuleCard: React.FC<{
  rule: PipelineActionRule;
  index: number;
  pipelineId: number;
  stages: PipelineStage[];
  templates: { id: number; name: string; subject: string }[];
  onDelete: () => void;
}> = ({ rule, index, pipelineId, stages, templates, onDelete }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const updateRule = useUpdateRule();
  const [expanded, setExpanded] = useState(rule.steps.length === 0);

  const [draft, setDraft] = useState({
    name: rule.name,
    condition_type: rule.condition_type,
    condition_value: rule.condition_value ?? '',
    is_enabled: rule.is_enabled,
    steps: rule.steps.map(s => ({
      action_type: s.action_type,
      action_config_json: s.action_config_json,
      position: s.position,
    })),
  });

  const inp: React.CSSProperties = {
    background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
    border: `1px solid ${t.border}`, borderRadius: 8,
    color: t.text, fontSize: 13, padding: '7px 10px',
    width: '100%', boxSizing: 'border-box', outline: 'none',
  };

  const addStep = () => setDraft(d => ({
    ...d,
    steps: [...d.steps, { action_type: 'send_email_template' as ActionType, action_config_json: '{}', position: d.steps.length + 1 }],
  }));

  const removeStep = (i: number) => setDraft(d => ({ ...d, steps: d.steps.filter((_, idx) => idx !== i) }));

  const updateStep = (i: number, patch: Partial<typeof draft.steps[0]>) =>
    setDraft(d => ({ ...d, steps: d.steps.map((s, idx) => idx === i ? { ...s, ...patch } : s) }));

  const getConfig = (json: string) => { try { return JSON.parse(json); } catch { return {}; } };

  const handleSave = async () => {
    await updateRule.mutateAsync({ pipelineId, ruleId: rule.id, ...draft });
    setExpanded(false);
  };

  return (
    <div style={{
      background: isDark ? 'rgba(255,255,255,0.03)' : '#fafafa',
      border: `1px solid ${rule.is_enabled ? t.accent + '33' : t.border}`,
      borderRadius: 12, overflow: 'hidden',
    }}>
      {/* Card header */}
      <div style={{ padding: '11px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 6, flexShrink: 0,
          background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: t.textMuted,
        }}>{index + 1}</div>
        <div style={{ flex: 1, fontSize: 13, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {rule.name}
        </div>
        {/* Enable toggle */}
        <div
          onClick={() => updateRule.mutate({ pipelineId, ruleId: rule.id, is_enabled: !rule.is_enabled })}
          style={{
            width: 32, height: 18, borderRadius: 9,
            background: rule.is_enabled ? t.accent : (isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)'),
            position: 'relative', transition: 'background 0.2s', flexShrink: 0, cursor: 'pointer',
          }}
        >
          <div style={{
            position: 'absolute', top: 1, left: rule.is_enabled ? 14 : 1,
            width: 16, height: 16, borderRadius: '50%', background: '#fff',
            transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
          }} />
        </div>
        <button onClick={() => setExpanded(e => !e)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 14, padding: '0 2px', lineHeight: 1 }}>
          {expanded ? '▾' : '▸'}
        </button>
        <button onClick={onDelete} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 16, padding: '0 2px', lineHeight: 1 }}>×</button>
      </div>

      {expanded && (
        <div style={{ borderTop: `1px solid ${t.border}`, padding: '14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Name */}
          <div>
            <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>Rule name</label>
            <input value={draft.name} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} style={inp} />
          </div>

          {/* IF condition */}
          <div>
            <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 4 }}>
              <span style={{ color: t.accent, fontWeight: 700 }}>IF</span> condition
            </label>
            <select value={draft.condition_type} onChange={e => setDraft(d => ({ ...d, condition_type: e.target.value }))} style={inp}>
              <option value="always">Always</option>
              <option value="bucket_is">Score bucket is…</option>
              <option value="stage_is">Lead is in stage…</option>
            </select>
          </div>
          {draft.condition_type !== 'always' && (
            <input
              value={draft.condition_value}
              onChange={e => setDraft(d => ({ ...d, condition_value: e.target.value }))}
              placeholder={draft.condition_type === 'bucket_is' ? 'HOT, WARM, or NURTURE' : 'stage key'}
              style={inp}
            />
          )}

          {/* THEN steps */}
          <div>
            <label style={{ fontSize: 11, color: t.textFaint, display: 'block', marginBottom: 8 }}>
              <span style={{ color: t.green, fontWeight: 700 }}>THEN</span> do these actions
            </label>
            {draft.steps.map((step, i) => (
              <div key={i} style={{
                background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)',
                border: `1px solid ${t.border}`, borderRadius: 10,
                padding: '10px 12px', marginBottom: 8,
                display: 'flex', flexDirection: 'column', gap: 8,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, width: 16, flexShrink: 0 }}>{i + 1}.</div>
                  <select
                    value={step.action_type}
                    onChange={e => updateStep(i, { action_type: e.target.value as ActionType, action_config_json: '{}' })}
                    style={{ ...inp, flex: 1 }}
                  >
                    {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <button onClick={() => removeStep(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textFaint, fontSize: 16, padding: '0 2px', lineHeight: 1, flexShrink: 0 }}>×</button>
                </div>

                {/* Per-action config */}
                {(step.action_type === 'send_email_template' || step.action_type === 'send_bucket_followup_email') && (
                  <select
                    value={getConfig(step.action_config_json).template_id ?? ''}
                    onChange={e => updateStep(i, { action_config_json: JSON.stringify({ template_id: e.target.value }) })}
                    style={inp}
                  >
                    <option value="">— select template —</option>
                    {templates.map(tpl => <option key={tpl.id} value={String(tpl.id)}>{tpl.name}</option>)}
                  </select>
                )}
                {step.action_type === 'move_to_stage' && (
                  <select
                    value={getConfig(step.action_config_json).stage_id ?? ''}
                    onChange={e => updateStep(i, { action_config_json: JSON.stringify({ stage_id: e.target.value }) })}
                    style={inp}
                  >
                    <option value="">— select stage —</option>
                    {[...stages].sort((a, b) => a.position - b.position).map(s => (
                      <option key={s.id} value={String(s.id)}>{s.name}</option>
                    ))}
                  </select>
                )}
                {step.action_type === 'send_qualification_form' && (
                  <input
                    placeholder="Form ID (optional)"
                    value={getConfig(step.action_config_json).form_id ?? ''}
                    onChange={e => updateStep(i, { action_config_json: JSON.stringify({ form_id: e.target.value }) })}
                    style={inp}
                  />
                )}
              </div>
            ))}
            <button onClick={addStep} style={{
              background: 'none', border: `1.5px dashed ${t.border}`,
              borderRadius: 8, color: t.textMuted, fontSize: 12,
              padding: '7px', cursor: 'pointer', width: '100%',
            }}>+ Add step</button>
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={() => setExpanded(false)} style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '7px 14px', cursor: 'pointer' }}>
              Cancel
            </button>
            <button onClick={handleSave} disabled={updateRule.isPending} style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none',
              borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600,
              padding: '7px 18px', cursor: 'pointer',
            }}>
              {updateRule.isPending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Live summary ──────────────────────────────────────────────────────────

const LiveSummary: React.FC<{
  stage: PipelineStage;
  rules: PipelineActionRule[];
  stages: PipelineStage[];
  templates: { id: number; name: string; subject: string }[];
}> = ({ stage, rules, stages, templates }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';

  const getTemplateName = (json: string) => {
    try {
      const id = JSON.parse(json).template_id;
      return templates.find(t => String(t.id) === String(id))?.name ?? `Template #${id}`;
    } catch { return '—'; }
  };

  const getStageName = (json: string) => {
    try {
      const id = JSON.parse(json).stage_id;
      return stages.find(s => String(s.id) === String(id))?.name ?? `Stage #${id}`;
    } catch { return '—'; }
  };

  const describeStep = (action_type: ActionType, action_config_json: string): string => {
    switch (action_type) {
      case 'send_email_template':        return `Send "${getTemplateName(action_config_json)}"`;
      case 'send_bucket_followup_email': return `Send follow-up "${getTemplateName(action_config_json)}"`;
      case 'send_qualification_form':    return 'Send qualification form';
      case 'move_to_stage':              return `Move to "${getStageName(action_config_json)}"`;
      default: return action_type;
    }
  };

  return (
    <div style={{
      background: isDark ? 'rgba(99,102,241,0.06)' : 'rgba(99,102,241,0.04)',
      border: `1px solid ${t.accent}22`, borderRadius: 12, padding: '14px 16px',
      marginTop: 4,
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: t.accent, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 10 }}>
        Summary
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rules.map((rule, ri) => (
          <div key={rule.id} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span style={{ color: t.accent, fontWeight: 700 }}>When</span>
            <span style={{ color: t.text }}>lead enters <strong>{stage.name}</strong></span>
            {rule.condition_type !== 'always' && (
              <>
                <span style={{ color: t.textFaint }}>and</span>
                <span style={{ color: t.text }}>{rule.condition_type === 'bucket_is' ? `bucket is ${rule.condition_value}` : `stage is ${rule.condition_value}`}</span>
              </>
            )}
            {rule.steps.length > 0 ? (
              rule.steps.map((step, si) => (
                <React.Fragment key={si}>
                  <span style={{ color: t.green, fontWeight: 700 }}>{si === 0 ? '→' : 'then'}</span>
                  <span style={{ color: t.text }}>{describeStep(step.action_type, step.action_config_json)}</span>
                </React.Fragment>
              ))
            ) : (
              <span style={{ color: t.textFaint, fontStyle: 'italic' }}>→ (no steps)</span>
            )}
            {!rule.is_enabled && (
              <span style={{ fontSize: 10, color: t.textFaint, background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)', borderRadius: 4, padding: '1px 6px' }}>disabled</span>
            )}
            {ri < rules.length - 1 && <div style={{ width: '100%', height: 1, background: t.border, margin: '2px 0' }} />}
          </div>
        ))}
      </div>
    </div>
  );
};
