/**
 * StageDrawer — premium 2-section stage config panel.
 * Section 1: Settings (name, color, category, toggles)
 * Section 2: Actions (When/Then automation builder for this stage)
 * No tab switching — everything visible in one scroll.
 */

import React, { useState, useEffect } from 'react';
import { useTheme } from '@/shared/contexts';
import { getTokens } from '@/shared/utils';
import {
  useUpdateStage, useDeleteStage,
  usePipelineEventMappings, useUpsertEventMapping,
  usePipelineRules, useCreateRule, useUpdateRule, useDeleteRule,
  useAdminTemplates,
} from '@/apps/platform-admin/hooks/usePipelineQueries';
import type {
  PipelineStage, StageCategory, BuiltInEventType,
  ActionType, RuleCreate,
  PipelineActionRule,
} from '@/apps/platform-admin/api/pipelinesApi';

import { COLORS, CATEGORIES, EVENT_LABELS, ACTION_OPTIONS } from '@/shared/utils/config/const';
import styles from './index.module.css';

interface Props {
  stage: PipelineStage;
  pipelineId: number;
  stages: PipelineStage[];
  onClose: () => void;
}


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
      <div onClick={onClose} className={styles.backdrop} />

      {/* Drawer panel */}
      <div className={styles.drawer} style={{
        background: drawerBg,
        borderLeft: `1px solid ${divider}`,
        boxShadow: '-20px 0 60px rgba(0,0,0,0.35)',
      }}>

        {/* ── Header ── */}
        <div className={styles.drawerHeader} style={{
          borderBottom: `1px solid ${divider}`,
          background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)',
        }}>
          <div className={styles.drawerHeaderRow}>
            <div className={styles.drawerHeaderLeft}>
              <div className={styles.stageColorDot} style={{
                background: stage.color,
                boxShadow: `0 0 10px ${stage.color}88`,
              }} />
              <div>
                <div className={styles.drawerTitle} style={{ color: t.text }}>{stage.name}</div>
                <div className={styles.drawerSubtitle} style={{ color: t.textFaint }}>Stage configuration</div>
              </div>
            </div>
            <button
              onClick={onClose}
              className={styles.closeBtn}
              style={{
                background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                color: t.textMuted,
              }}
            >×</button>
          </div>
        </div>

        {/* ── Scrollable body ── */}
        <div className={styles.scrollBody}>
          <SectionBlock label="Settings" icon="⚙" sectionBg={sectionBg} divider={divider}>
            <SettingsSection stage={stage} pipelineId={pipelineId} stages={stages} onClose={onClose} />
          </SectionBlock>
          <SectionBlock label="Entry Triggers" icon="⚡" sectionBg={sectionBg} divider={divider}>
            <TriggersSection stage={stage} pipelineId={pipelineId} />
          </SectionBlock>
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
      <div className={styles.sectionHeader} style={{ background: sectionBg, borderBottom: `1px solid ${divider}` }}>
        <span className={styles.sectionIcon}>{icon}</span>
        <span className={styles.sectionLabel} style={{ color: t.textMuted }}>{label}</span>
      </div>
      <div className={styles.sectionBody}>{children}</div>
      <div className={styles.sectionDivider} style={{ background: divider }} />
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
    <div className={styles.settingsForm}>
      {/* Name */}
      <div>
        <label className={styles.fieldLabel} style={{ color: t.textFaint }}>Name</label>
        <input value={name} onChange={e => setName(e.target.value)} style={inp} />
      </div>

      {/* Key */}
      <div>
        <label className={styles.fieldLabel} style={{ color: t.textFaint }}>Key</label>
        <input value={key} onChange={e => setKey(e.target.value)} style={{ ...inp, color: t.textMuted, fontFamily: 'monospace', fontSize: 12 }} />
      </div>

      {/* Color */}
      <div>
        <label className={styles.colorFieldLabel} style={{ color: t.textFaint }}>Color</label>
        <div className={styles.colorRow}>
          {COLORS.map(c => (
            <button key={c} type="button" onClick={() => setColor(c)} className={styles.colorBtn} style={{
              background: c,
              outline: color === c ? `2.5px solid ${t.text}` : `2px solid transparent`,
              outlineOffset: 2,
              boxShadow: color === c ? `0 0 8px ${c}88` : 'none',
            }} />
          ))}
          <input type="color" value={color} onChange={e => setColor(e.target.value)} className={styles.customColorInput} title="Custom color" />
        </div>
      </div>

      {/* Category */}
      <div>
        <label className={styles.colorFieldLabel} style={{ color: t.textFaint }}>Category</label>
        <div className={styles.categoryRow}>
          {CATEGORIES.map(cat => (
            <button key={cat.value} type="button" onClick={() => setCategory(cat.value)} className={styles.categoryBtn} style={{
              background: category === cat.value ? t.accentBg : (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'),
              border: `1px solid ${category === cat.value ? t.accent + '66' : t.border}`,
              fontWeight: category === cat.value ? 600 : 400,
              color: category === cat.value ? t.accent : t.textMuted,
            }}>
              {cat.icon} {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Toggles */}
      <div className={styles.toggleList}>
        {[
          { label: 'Default stage', sub: 'New leads start here', val: isDefault, set: setIsDefault },
          { label: 'Closed Won', sub: 'Marks lead as won', val: isClosedWon, set: (v: boolean) => { setIsClosedWon(v); if (v) setIsClosedLost(false); } },
          { label: 'Closed Lost', sub: 'Marks lead as lost', val: isClosedLost, set: (v: boolean) => { setIsClosedLost(v); if (v) setIsClosedWon(false); } },
        ].map(({ label, sub, val, set }) => (
          <label key={label} className={styles.toggleRow} style={{
            background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
            border: `1px solid ${t.border}`,
          }}>
            <div>
              <div className={styles.toggleLabel} style={{ color: t.text }}>{label}</div>
              <div className={styles.toggleSub} style={{ color: t.textFaint }}>{sub}</div>
            </div>
            <div onClick={() => set(!val)} className={styles.toggleSwitch} style={{
              background: val ? t.accent : (isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)'),
            }}>
              <div className={styles.toggleKnob} style={{ left: val ? 18 : 2 }} />
            </div>
          </label>
        ))}
      </div>

      {/* Save / Delete */}
      <div className={styles.saveDeleteRow}>
        <button onClick={handleSave} disabled={updateStage.isPending} className={styles.saveBtn}>
          {updateStage.isPending ? 'Saving…' : 'Save Changes'}
        </button>
        <button onClick={() => setShowDelete(true)} className={styles.deleteBtn} style={{
          border: `1px solid ${t.red}22`, color: t.red,
        }}>Delete</button>
      </div>

      {/* Delete confirm */}
      {showDelete && (
        <div className={styles.deleteConfirm} style={{ background: t.redBg, border: `1px solid ${t.red}44` }}>
          <div className={styles.deleteConfirmTitle} style={{ color: t.text }}>Delete "{stage.name}"?</div>
          {otherStages.length > 0 && (
            <div className={styles.deleteConfirmField}>
              <label className={styles.deleteConfirmLabel} style={{ color: t.textFaint }}>Reassign leads to</label>
              <select value={reassignTo} onChange={e => setReassignTo(e.target.value ? Number(e.target.value) : '')} style={inp}>
                <option value="">— none —</option>
                {otherStages.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}
          {deleteError && <div className={styles.deleteError} style={{ color: t.red }}>{deleteError}</div>}
          <div className={styles.deleteActions}>
            <button onClick={handleDelete} disabled={deleteStage.isPending} className={styles.confirmDeleteBtn} style={{ background: t.red }}>
              {deleteStage.isPending ? 'Deleting…' : 'Confirm Delete'}
            </button>
            <button onClick={() => { setShowDelete(false); setDeleteError(null); }} className={styles.cancelDeleteBtn} style={{ border: `1px solid ${t.border}`, color: t.textMuted }}>
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
    <div className={styles.triggersContainer}>
      <div className={styles.triggersDesc} style={{ color: t.textFaint }}>
        When these platform events fire, leads automatically move into <span className={styles.triggersDescHighlight} style={{ color: t.text }}>{stage.name}</span>.
      </div>
      {allEvents.map(ev => {
        const active = isActive(ev);
        const elsewhere = pointsElsewhere(ev);
        return (
          <div key={ev} className={styles.triggerRow} style={{
            background: active ? t.accentBg : (isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)'),
            border: `1px solid ${active ? t.accent + '44' : t.border}`,
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className={styles.triggerName} style={{ color: t.text, fontWeight: active ? 500 : 400 }}>{EVENT_LABELS[ev]}</div>
              {elsewhere && <div className={styles.triggerElsewhere} style={{ color: t.textFaint }}>Mapped to another stage</div>}
            </div>
            {/* Toggle pill */}
            <div onClick={() => toggle(ev)} className={styles.toggleSwitch} style={{
              background: active ? t.accent : (isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)'),
            }}>
              <div className={styles.toggleKnob} style={{ left: active ? 18 : 2 }} />
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
    <div className={styles.actionsContainer}>
      {/* When header */}
      <div className={styles.whenHeader} style={{
        background: isDark ? 'rgba(99,102,241,0.08)' : 'rgba(99,102,241,0.06)',
        border: `1px solid ${t.accent}22`,
      }}>
        <div className={styles.whenDot} style={{ background: t.accent }} />
        <span className={styles.whenText} style={{ color: t.textMuted }}>
          <span className={styles.whenBold} style={{ color: t.accent }}>When</span> a lead enters{' '}
          <span className={styles.whenStageName} style={{ color: t.text }}>{stage.name}</span>…
        </span>
      </div>

      {stageRules.length === 0 && (
        <div className={styles.emptyActions} style={{
          background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
          border: `1.5px dashed ${t.border}`,
        }}>
          <div className={styles.emptyActionsText} style={{ color: t.textFaint }}>No actions configured yet.</div>
          <button onClick={handleAdd} disabled={createRule.isPending} className={styles.addActionBtn}>
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
        <button onClick={handleAdd} disabled={createRule.isPending} className={styles.addAnotherBtn} style={{
          border: `1.5px dashed ${t.border}`, color: t.textMuted,
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
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

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
    setSaveError(null);
    try {
      const payload = {
        ...draft,
        condition_value: draft.condition_type === 'always' ? undefined : (draft.condition_value || undefined),
      };
      await updateRule.mutateAsync({ pipelineId, ruleId: rule.id, ...payload });
      setSaved(true);
      setTimeout(() => { setSaved(false); setExpanded(false); }, 800);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || (err instanceof Error ? err.message : 'Failed to save rule');
      setSaveError(msg);
    }
  };

  return (
    <div className={styles.ruleCard} style={{
      background: isDark ? 'rgba(255,255,255,0.03)' : '#fafafa',
      border: `1px solid ${rule.is_enabled ? t.accent + '33' : t.border}`,
    }}>
      {/* Card header */}
      <div className={styles.ruleCardHeader}>
        <div className={styles.ruleIndex} style={{
          background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
          color: t.textMuted,
        }}>{index + 1}</div>
        <div className={styles.ruleCardName} style={{ color: t.text }}>
          {rule.name}
        </div>
        {/* Enable toggle */}
        <div
          onClick={() => updateRule.mutate({ pipelineId, ruleId: rule.id, is_enabled: !rule.is_enabled })}
          className={styles.miniToggle}
          style={{
            background: rule.is_enabled ? t.accent : (isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)'),
          }}
        >
          <div className={styles.miniToggleKnob} style={{ left: rule.is_enabled ? 14 : 1 }} />
        </div>
        <button onClick={() => setExpanded(e => !e)} className={styles.expandBtn} style={{ color: t.textFaint }}>
          {expanded ? '▾' : '▸'}
        </button>
        <button onClick={onDelete} className={styles.ruleDeleteBtn} style={{ color: t.textFaint }}>×</button>
      </div>

      {expanded && (
        <div className={styles.ruleCardBody} style={{ borderTop: `1px solid ${t.border}` }}>
          {/* Name */}
          <div>
            <label className={styles.ruleFieldLabel} style={{ color: t.textFaint }}>Rule name</label>
            <input value={draft.name} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} style={inp} />
          </div>

          {/* IF condition */}
          <div>
            <label className={styles.ruleFieldLabel} style={{ color: t.textFaint }}>
              <span className={styles.ruleFieldLabelBold} style={{ color: t.accent }}>IF</span> condition
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
            <label className={styles.stepsLabel} style={{ color: t.textFaint }}>
              <span className={styles.ruleFieldLabelBold} style={{ color: t.green }}>THEN</span> do these actions
            </label>
            {draft.steps.map((step, i) => (
              <div key={i} className={styles.stepCard} style={{
                background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)',
                border: `1px solid ${t.border}`,
              }}>
                <div className={styles.stepHeader}>
                  <div className={styles.stepIndex} style={{ color: t.textFaint }}>{i + 1}.</div>
                  <select
                    value={step.action_type}
                    onChange={e => updateStep(i, { action_type: e.target.value as ActionType, action_config_json: '{}' })}
                    style={{ ...inp, flex: 1 }}
                  >
                    {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <button onClick={() => removeStep(i)} className={styles.stepRemoveBtn} style={{ color: t.textFaint }}>×</button>
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
            <button onClick={addStep} className={styles.addStepBtn} style={{
              border: `1.5px dashed ${t.border}`, color: t.textMuted,
            }}>+ Add step</button>
          </div>

          <div className={styles.ruleCardActions}>
            {saveError && (
              <div className={styles.saveError} style={{ color: t.red, background: t.redBg, border: `1px solid ${t.red}33` }}>
                {saveError}
              </div>
            )}
            <div className={styles.ruleCardBtns}>
              <button onClick={() => { setExpanded(false); setSaveError(null); }} className={styles.ruleCancelBtn} style={{ border: `1px solid ${t.border}`, color: t.textMuted }}>
                Cancel
              </button>
              <button onClick={handleSave} disabled={updateRule.isPending || saved} className={styles.ruleSaveBtn} style={{
                background: saved ? '#22c55e' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              }}>
                {saved ? '✓ Saved' : updateRule.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
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
      case 'send_email_template': return `Send "${getTemplateName(action_config_json)}"`;
      case 'send_bucket_followup_email': return `Send follow-up "${getTemplateName(action_config_json)}"`;
      case 'send_qualification_form': return 'Send qualification form';
      case 'move_to_stage': return `Move to "${getStageName(action_config_json)}"`;
      default: return action_type;
    }
  };

  return (
    <div className={styles.liveSummary} style={{
      background: isDark ? 'rgba(99,102,241,0.06)' : 'rgba(99,102,241,0.04)',
      border: `1px solid ${t.accent}22`,
    }}>
      <div className={styles.liveSummaryTitle} style={{ color: t.accent }}>
        Summary
      </div>
      <div className={styles.liveSummaryList}>
        {rules.map((rule, ri) => (
          <div key={rule.id} className={styles.summaryRow}>
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
              <span className={styles.disabledBadge} style={{ color: t.textFaint, background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>disabled</span>
            )}
            {ri < rules.length - 1 && <div className={styles.summaryDivider} style={{ background: t.border }} />}
          </div>
        ))}
      </div>
    </div>
  );
};
