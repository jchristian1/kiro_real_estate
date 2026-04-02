/**
 * AutomationsTab — Zapier-style When/Then rule builder.
 * Requirements: 9.6
 */

import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts';
import { getTokens } from '@/shared/utils';
import {
  usePipelineRules, usePipelineStages,
  useCreateRule, useUpdateRule, useDeleteRule,
  useAdminTemplates,
} from '@/apps/platform-admin/hooks/usePipelineQueries';
import type { PipelineActionRule, PipelineStage, RuleCreate, RuleUpdate, ActionType } from '@/models/platform-admin'
import { TRIGGER_OPTIONS, CONDITION_OPTIONS, ACTION_OPTIONS } from '@/shared/utils';
import styles from './index.module.css';


interface Props { pipelineId: number; }

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

  if (isLoading) return <div className={styles.loadingText} style={{ color: t.textFaint }}>Loading…</div>;

  return (
    <div className={styles.container}>
      {/* Explainer */}
      <div className={styles.explainer} style={{ background: t.accentBg, border: `1px solid ${t.accent}22` }}>
        <span className={styles.explainerIcon}>⚡</span>
        <div>
          <div className={styles.explainerTitle} style={{ color: t.text }}>Automate your pipeline</div>
          <div className={styles.explainerDesc} style={{ color: t.textMuted }}>
            Create rules that run automatically. Each rule has a <strong>trigger</strong> (when something happens),
            an optional <strong>condition</strong> (only if…), and one or more <strong>actions</strong> (do this).
          </div>
        </div>
      </div>

      {sorted.length === 0 && (
        <div className={styles.emptyState} style={{ background: t.bgCard, border: `1.5px dashed ${t.border}` }}>
          <div className={styles.emptyIcon}>🤖</div>
          <div className={styles.emptyTitle} style={{ color: t.text }}>No automations yet</div>
          <div className={styles.emptyDesc} style={{ color: t.textMuted }}>
            Automations save time by taking actions automatically when leads move through your pipeline.
          </div>
          <button onClick={handleNewRule} disabled={createRule.isPending} className={styles.primaryBtn}>
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
          className={styles.addBtn}
          style={{ background: t.bgCard, border: `1.5px dashed ${t.border}`, color: t.textMuted }}
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
    <div className={styles.ruleCard} style={{
      background: t.bgCard, border: `1px solid ${t.border}`,
      opacity: rule.is_enabled ? 1 : 0.75,
    }}>
      {/* Header */}
      <div className={styles.ruleHeader}>
        <button onClick={() => setExpanded(e => !e)} className={styles.expandBtn} style={{ color: t.textMuted }}>
          {expanded ? '▾' : '▸'}
        </button>

        <div className={styles.ruleInfo}>
          <div className={styles.ruleName} style={{ color: t.text }}>{rule.name}</div>
          <div className={styles.ruleSummary} style={{ color: t.textMuted }}>
            <span className={styles.badge} style={{ background: t.accentBg, color: t.accent }}>WHEN</span>
            <span>{summary}</span>
            {rule.steps.length > 0 && (
              <>
                <span style={{ color: t.textFaint }}>→</span>
                <span className={styles.badge} style={{ background: '#16a34a22', color: '#16a34a' }}>THEN</span>
                <span>{rule.steps.length} action{rule.steps.length !== 1 ? 's' : ''}</span>
              </>
            )}
          </div>
        </div>

        {/* Toggle */}
        <button
          onClick={handleToggle}
          className={styles.toggleBtn}
          style={{
            background: rule.is_enabled ? '#16a34a22' : t.bgCardHover,
            border: `1px solid ${rule.is_enabled ? '#16a34a44' : t.border}`,
            color: rule.is_enabled ? '#16a34a' : t.textMuted,
          }}
        >
          {rule.is_enabled ? '● On' : '○ Off'}
        </button>

        <button
          onClick={() => deleteRule.mutate({ pipelineId, ruleId: rule.id })}
          className={styles.deleteBtn}
          style={{ color: t.textFaint }}
          title="Delete"
        >×</button>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div className={styles.ruleEditor} style={{ borderTop: `1px solid ${t.border}` }}>
          {/* Name */}
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel} style={{ color: t.textFaint }}>
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
          <ZapBlock color="#6366f1" label="WHEN" icon="⚡" description="This automation runs when…">
            <div className={styles.stepsContainer}>
              <div>
                <label className={styles.smallLabel} style={{ color: t.textFaint }}>Trigger event</label>
                <select value={draft.trigger_type ?? ''} onChange={e => setDraft(d => ({ ...d, trigger_type: e.target.value }))} style={sel}>
                  {TRIGGER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.icon} {o.label}</option>)}
                </select>
              </div>
              {(draft.trigger_type === 'on_stage_enter') && (
                <div>
                  <label className={styles.smallLabel} style={{ color: t.textFaint }}>Which stage?</label>
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
            <div className={styles.stepsContainer}>
              <div>
                <label className={styles.smallLabel} style={{ color: t.textFaint }}>Condition</label>
                <select value={draft.condition_type ?? 'always'} onChange={e => setDraft(d => ({ ...d, condition_type: e.target.value }))} style={sel}>
                  {CONDITION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <div className={styles.conditionDesc} style={{ color: t.textFaint }}>
                  {CONDITION_OPTIONS.find(o => o.value === draft.condition_type)?.desc}
                </div>
              </div>
              {draft.condition_type !== 'always' && (
                <div>
                  <label className={styles.smallLabel} style={{ color: t.textFaint }}>Value</label>
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
            <div className={styles.stepsContainer}>
              {(draft.steps ?? []).length === 0 && (
                <div className={styles.noActionsText} style={{ color: t.textFaint }}>No actions yet — add one below.</div>
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
                className={styles.addActionBtn}
                style={{ border: `1.5px dashed ${t.border}`, color: t.textMuted }}
              >
                + Add action
              </button>
            </div>
          </ZapBlock>

          <div className={styles.editorActions}>
            <button onClick={() => setExpanded(false)} className={styles.cancelBtn} style={{ border: `1px solid ${t.border}`, color: t.textMuted }}>
              Cancel
            </button>
            <button onClick={handleSave} disabled={updateRule.isPending} className={styles.saveBtn}>
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
    <div className={styles.zapBlock} style={{ border: `1.5px solid ${color}33` }}>
      <div className={styles.zapBlockHeader} style={{ background: `${color}18`, borderBottom: `1px solid ${color}22` }}>
        <span className={styles.zapBlockIcon}>{icon}</span>
        <span className={styles.zapBlockLabel} style={{ color }}>{label}</span>
        <span className={styles.zapBlockDesc} style={{ color: t.textMuted }}>{description}</span>
      </div>
      <div className={styles.zapBlockBody}>{children}</div>
    </div>
  );
};

// ── Connector arrow ───────────────────────────────────────────────────────

const Connector: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div className={styles.connector} style={{ color: t.textFaint }}>↓</div>
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
    <div className={styles.actionRow} style={{ background: t.bgCardHover, border: `1px solid ${t.border}` }}>
      <div className={styles.actionHeader}>
        <span className={styles.actionIcon}>{opt?.icon ?? '▶'}</span>
        <select
          value={step.action_type}
          onChange={e => onUpdate({ ...step, action_type: e.target.value as ActionType })}
          style={{ ...sel, flex: 1 }}
        >
          {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.icon} {o.label}</option>)}
        </select>
        <button onClick={onRemove} className={styles.actionRemoveBtn} style={{ color: t.textFaint }}>×</button>
      </div>
      {opt && <div className={styles.actionDesc} style={{ color: t.textFaint }}>{opt.desc}</div>}

      {/* Friendly config fields per action type */}
      {step.action_type === 'send_email_template' && (
        <div className={styles.actionFields}>
          <label className={styles.smallLabel} style={{ color: t.textFaint }}>Email template</label>
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
            <div className={styles.noTemplatesText} style={{ color: t.textFaint }}>No templates found. Create one in the Templates page first.</div>
          )}
        </div>
      )}
      {step.action_type === 'send_qualification_form' && (
        <input placeholder="Form ID" value={config.form_id ?? ''} onChange={e => onUpdate({ ...step, action_config_json: JSON.stringify({ ...config, form_id: e.target.value }) })} style={sel} />
      )}
      {step.action_type === 'send_bucket_followup_email' && (
        <div className={styles.actionFields}>
          <label className={styles.smallLabel} style={{ color: t.textFaint }}>Email template (optional)</label>
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
        <div className={styles.actionFields}>
          <label className={styles.smallLabel} style={{ color: t.textFaint }}>Target stage</label>
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
