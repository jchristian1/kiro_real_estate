import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { useToast } from '@/shared/contexts/ToastContext';
import { SectionHeader } from '../SectionHeader';
import styles from '../../index.module.css';

const API = '/api/v1';

interface QuestionOption { value: string; label: string; }
interface Question {
  question_key: string;
  type: 'single_choice' | 'multi_select' | 'free_text' | 'phone' | 'email';
  label: string;
  required: boolean;
  options: QuestionOption[];
  order: number;
}
interface LogicRule {
  if: { question_key: string; answer: string };
  then: { hide: string[] };
}
interface ScoringRule { key: string; answer_value: string; points: number; reason: string; }
interface Thresholds { HOT: number; WARM: number; }
interface FormTemplate {
  id: number;
  name: string;
  status: 'active' | 'draft' | 'archived';
  intent_type: string;
  created_at: string;
}

const QUESTION_TYPES = ['single_choice', 'multi_select', 'free_text', 'phone', 'email'] as const;
const emptyQuestion = (order: number): Question => ({
  question_key: '', type: 'single_choice', label: '', required: true, options: [], order,
});

interface FormDrawerProps {
  form: FormTemplate | null;
  tenantId: string;
  onClose: () => void;
  onSaved: () => void;
}

export const FormDrawer: React.FC<FormDrawerProps> = ({ form, tenantId, onClose, onSaved }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();

  const [name, setName] = useState(form?.name ?? '');
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!form);

  const [questions, setQuestions] = useState<Question[]>([]);
  const [logicRules, setLogicRules] = useState<LogicRule[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const [scoringRules, setScoringRules] = useState<ScoringRule[]>([]);
  const [thresholds, setThresholds] = useState<Thresholds>({ HOT: 80, WARM: 50 });
  const [scoringConfigId, setScoringConfigId] = useState<number | null>(null);
  const [publishingScore, setPublishingScore] = useState(false);

  const drawerBg = isDark ? '#16181d' : '#ffffff';
  const panelBg = isDark ? '#1c1f26' : '#f8f9fb';
  const divider = isDark ? '#2a2d35' : '#e5e7eb';
  const inputStyle: React.CSSProperties = {
    background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
    padding: '7px 10px', fontSize: 13, color: t.text, outline: 'none',
    width: '100%', boxSizing: 'border-box',
  };
  const inputSm: React.CSSProperties = { ...inputStyle, padding: '5px 8px', fontSize: 12 };

  useEffect(() => {
    if (!form) { setLoading(false); return; }
    setName(form.name);
    setLoading(true);
    Promise.all([
      axios.get(`${API}/buyer-leads/tenants/${tenantId}/forms/${form.id}/versions`),
      axios.get<{ id: number }[]>(`${API}/buyer-leads/tenants/${tenantId}/scoring`),
    ]).then(async ([versRes, scoringRes]) => {
      const activeVer = (versRes.data as { is_active: boolean; schema_json?: string }[]).find(v => v.is_active);
      if (activeVer?.schema_json) {
        const schema = JSON.parse(activeVer.schema_json) as { questions?: Question[]; logic_rules?: LogicRule[] } | Question[];
        const rawQs = Array.isArray(schema) ? schema : (schema.questions ?? []);
        const rawLogic = Array.isArray(schema) ? [] : (schema.logic_rules ?? []);
        setQuestions(rawQs.map((q: Question & { options_json?: string }) => ({
          ...q, options: q.options ?? (q.options_json ? JSON.parse(q.options_json) : []),
        })).sort((a, b) => a.order - b.order));
        setLogicRules(rawLogic.map((r: LogicRule & { rule_json?: string }) =>
          typeof r.rule_json === 'string' ? JSON.parse(r.rule_json) : r
        ));
      }
      const configs = scoringRes.data;
      if (configs.length > 0) {
        const cfg = configs[0];
        setScoringConfigId(cfg.id);
        const svRes = await axios.get<{ is_active: boolean; rules_json: string; thresholds_json: string }[]>(
          `${API}/buyer-leads/tenants/${tenantId}/scoring/${cfg.id}/versions`
        );
        const activeScore = svRes.data.find(v => v.is_active);
        if (activeScore) {
          setScoringRules(JSON.parse(activeScore.rules_json) as ScoringRule[]);
          setThresholds(JSON.parse(activeScore.thresholds_json) as Thresholds);
        }
      }
    }).catch(() => toastError('Failed to load form data'))
      .finally(() => setLoading(false));
  }, [form, tenantId]);

  const handleCreate = async () => {
    if (!name.trim()) { setServerError('Name is required.'); return; }
    setSaving(true); setServerError(null);
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/forms`, { name: name.trim(), intent_type: 'BUY' });
      success('Form created'); onSaved();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string }>;
      setServerError(e.response?.data?.detail || 'Create failed');
    } finally { setSaving(false); }
  };

  const handlePublishForm = async () => {
    if (!form || questions.length === 0) return;
    setPublishing(true);
    try {
      const payload = {
        questions: questions.map(q => ({
          question_key: q.question_key, type: q.type, label: q.label,
          required: q.required, order: q.order,
          options_json: q.options.length > 0 ? JSON.stringify(q.options) : null,
          validation_json: null,
        })),
        logic_rules: logicRules.map(r => ({ rule_json: JSON.stringify(r) })),
      };
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/forms/${form.id}/versions`, payload);
      success('Form version published'); onSaved();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string }>;
      toastError(e.response?.data?.detail || 'Publish failed');
    } finally { setPublishing(false); }
  };

  const handlePublishScoring = async () => {
    if (!scoringConfigId) {
      try {
        const res = await axios.post<{ id: number }>(`${API}/buyer-leads/tenants/${tenantId}/scoring`, {
          name: `${name} Scoring`, intent_type: 'BUY',
        });
        setScoringConfigId(res.data.id);
        await axios.post(`${API}/buyer-leads/tenants/${tenantId}/scoring/${res.data.id}/versions`, { rules: scoringRules, thresholds });
      } catch { toastError('Failed to create scoring config'); return; }
    } else {
      setPublishingScore(true);
      try {
        await axios.post(`${API}/buyer-leads/tenants/${tenantId}/scoring/${scoringConfigId}/versions`, { rules: scoringRules, thresholds });
      } catch (err) {
        const e = err as AxiosError<{ detail?: string }>;
        toastError(e.response?.data?.detail || 'Scoring publish failed');
        setPublishingScore(false); return;
      }
      setPublishingScore(false);
    }
    success('Scoring published');
  };

  const updateQuestion = (i: number, patch: Partial<Question>) =>
    setQuestions(qs => qs.map((q, j) => j === i ? { ...q, ...patch } : q));
  const removeQuestion = (i: number) =>
    setQuestions(qs => qs.filter((_, j) => j !== i).map((q, j) => ({ ...q, order: j + 1 })));
  const handleDragOver = (e: React.DragEvent, i: number) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === i) return;
    const reordered = [...questions];
    const [moved] = reordered.splice(dragIndex, 1);
    reordered.splice(i, 0, moved);
    setQuestions(reordered.map((q, j) => ({ ...q, order: j + 1 })));
    setDragIndex(i);
  };

  const statusColor = (s: string) => s === 'active' ? t.green : s === 'draft' ? t.yellow : t.textFaint;
  const statusBg = (s: string) => s === 'active' ? t.greenBg : s === 'draft' ? t.yellowBg : t.bgBadge;

  return (
    <>
      <div onClick={onClose} className={styles.overlay} />
      <div className={styles.drawer} style={{ background: drawerBg }}>
        {/* Header */}
        <div className={styles.drawerHeader} style={{ borderBottom: `1px solid ${divider}` }}>
          <div>
            <div className={styles.drawerTitle} style={{ color: t.text }}>{form ? 'Edit Form' : 'New Form'}</div>
            {form && (
              <div className={styles.drawerStatusRow}>
                <span className={styles.statusBadge} style={{ background: statusBg(form.status), color: statusColor(form.status) }}>{form.status}</span>
                <span className={styles.drawerStatusType} style={{ color: t.textFaint }}>{form.intent_type}</span>
              </div>
            )}
          </div>
          <div className={styles.drawerActions}>
            {!form && (
              <button onClick={handleCreate} disabled={saving} className={styles.drawerPrimaryButton}
                style={{ background: t.accent, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.6 : 1 }}>
                {saving ? 'Creating…' : 'Create Form'}
              </button>
            )}
            {form && (
              <>
                <button onClick={handlePublishScoring} disabled={publishingScore} className={styles.drawerActionButton}
                  style={{ background: isDark ? '#1e2330' : '#f0f4ff', color: t.accent, border: `1px solid ${t.accent}30`, opacity: publishingScore ? 0.6 : 1 }}>
                  {publishingScore ? 'Saving…' : 'Save Scoring'}
                </button>
                <button onClick={handlePublishForm} disabled={publishing || questions.length === 0} className={styles.drawerPrimaryButton}
                  style={{ background: t.accent, opacity: publishing || questions.length === 0 ? 0.6 : 1 }}>
                  {publishing ? 'Publishing…' : 'Publish Form'}
                </button>
              </>
            )}
            <button onClick={onClose} className={styles.drawerCloseButton} style={{ color: t.textMuted }}>×</button>
          </div>
        </div>

        {/* Body */}
        <div className={styles.drawerBody}>
          {serverError && (
            <div className={styles.serverError} style={{ background: isDark ? '#2d1a1a' : '#fff0f0', border: `1px solid ${t.red}40`, color: t.red }}>
              {serverError}
            </div>
          )}

          <div>
            <label className={styles.fieldLabel} style={{ color: t.textMuted }}>
              Form Name <span style={{ color: t.red }}>*</span>
            </label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Buyer Qualification Form"
              style={{ ...inputStyle, maxWidth: 400 }} disabled={!!form} />
            {form && <p className={styles.fieldHint} style={{ color: t.textFaint }}>Rename via the card menu.</p>}
          </div>

          {loading ? (
            <div className={styles.loadingText} style={{ color: t.textMuted }}>Loading form data…</div>
          ) : form ? (
            <>
              {/* Questions */}
              <div>
                <SectionHeader icon="📋" label="Form Questions" divider={divider} textFaint={t.textFaint} />
                <div className={styles.formList}>
                  {questions.map((q, qi) => (
                    <div key={qi} draggable onDragStart={() => setDragIndex(qi)}
                      onDragOver={e => handleDragOver(e, qi)} onDragEnd={() => setDragIndex(null)}
                      className={`${styles.questionCard} ${dragIndex === qi ? styles.questionCardDragging : ''}`}
                      style={{ background: panelBg, border: `1px solid ${divider}` }}>
                      <div className={styles.questionHeader}>
                        <span className={styles.questionOrder} style={{ color: t.textFaint }}>Q{q.order} ⠿</span>
                        <button onClick={() => removeQuestion(qi)} className={styles.linkButton} style={{ color: t.red }}>Remove</button>
                      </div>
                      <div className={styles.twoColGrid}>
                        <div>
                          <label className={styles.miniLabel} style={{ color: t.textFaint }}>Key</label>
                          <input value={q.question_key} onChange={e => updateQuestion(qi, { question_key: e.target.value })} placeholder="e.g. timeline" style={inputSm} />
                        </div>
                        <div>
                          <label className={styles.miniLabel} style={{ color: t.textFaint }}>Type</label>
                          <select value={q.type} onChange={e => updateQuestion(qi, { type: e.target.value as Question['type'] })} style={inputSm}>
                            {QUESTION_TYPES.map(tp => <option key={tp} value={tp}>{tp}</option>)}
                          </select>
                        </div>
                      </div>
                      <div>
                        <label className={styles.miniLabel} style={{ color: t.textFaint }}>Label</label>
                        <input value={q.label} onChange={e => updateQuestion(qi, { label: e.target.value })} placeholder="Question shown to the lead" style={inputSm} />
                      </div>
                      <label className={styles.checkboxLabel} style={{ color: t.textMuted }}>
                        <input type="checkbox" checked={q.required} onChange={e => updateQuestion(qi, { required: e.target.checked })} style={{ accentColor: t.accent }} />
                        Required
                      </label>
                      {(q.type === 'single_choice' || q.type === 'multi_select') && (
                        <div className={styles.optionsContainer}>
                          <div className={styles.optionsHeader}>
                            <span className={styles.miniLabel} style={{ color: t.textFaint }}>Options</span>
                            <button onClick={() => updateQuestion(qi, { options: [...q.options, { value: '', label: '' }] })}
                              className={styles.linkButtonBold} style={{ color: t.accent }}>+ Add Option</button>
                          </div>
                          {q.options.map((opt, oi) => (
                            <div key={oi} className={styles.optionRow}>
                              <input value={opt.value} onChange={e => updateQuestion(qi, { options: q.options.map((o, i) => i === oi ? { ...o, value: e.target.value } : o) })} placeholder="value" style={{ ...inputSm, flex: 1 }} />
                              <input value={opt.label} onChange={e => updateQuestion(qi, { options: q.options.map((o, i) => i === oi ? { ...o, label: e.target.value } : o) })} placeholder="label" style={{ ...inputSm, flex: 1 }} />
                              <button onClick={() => updateQuestion(qi, { options: q.options.filter((_, i) => i !== oi) })} className={styles.removeButton} style={{ color: t.red }}>✕</button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  <button onClick={() => setQuestions(qs => [...qs, emptyQuestion(qs.length + 1)])}
                    className={styles.addButton} style={{ border: `1px dashed ${divider}`, color: t.textMuted }}>
                    + Add Question
                  </button>
                </div>
              </div>

              {/* Conditional Logic */}
              <div>
                <SectionHeader icon="🔀" label="Conditional Logic" divider={divider} textFaint={t.textFaint} />
                <div className={styles.formList}>
                  {logicRules.map((rule, ri) => (
                    <div key={ri} className={styles.ruleCard} style={{ background: panelBg, border: `1px solid ${divider}` }}>
                      <div className={styles.ruleHeader}>
                        <span className={styles.ruleLabel} style={{ color: t.textFaint }}>Rule {ri + 1}</span>
                        <button onClick={() => setLogicRules(rs => rs.filter((_, i) => i !== ri))} className={styles.linkButton} style={{ color: t.red }}>Remove</button>
                      </div>
                      <div className={styles.twoColGrid}>
                        <div>
                          <label className={styles.miniLabel} style={{ color: t.textFaint }}>If question key</label>
                          <input value={rule.if.question_key} onChange={e => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, if: { ...r.if, question_key: e.target.value } } : r))} placeholder="e.g. has_agent" style={inputSm} />
                        </div>
                        <div>
                          <label className={styles.miniLabel} style={{ color: t.textFaint }}>equals answer</label>
                          <input value={rule.if.answer} onChange={e => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, if: { ...r.if, answer: e.target.value } } : r))} placeholder="e.g. yes" style={inputSm} />
                        </div>
                      </div>
                      <div>
                        <label className={styles.miniLabel} style={{ color: t.textFaint }}>Then hide (comma-separated keys)</label>
                        <input value={rule.then.hide.join(', ')} onChange={e => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, then: { hide: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } } : r))} placeholder="e.g. wants_tour, areas" style={inputSm} />
                      </div>
                    </div>
                  ))}
                  <button onClick={() => setLogicRules(rs => [...rs, { if: { question_key: '', answer: '' }, then: { hide: [] } }])}
                    className={styles.addButton} style={{ border: `1px dashed ${divider}`, color: t.textMuted }}>
                    + Add Logic Rule
                  </button>
                </div>
              </div>

              {/* Scoring */}
              <div>
                <SectionHeader icon="🎯" label="Lead Scoring" divider={divider} textFaint={t.textFaint} />
                <div className={styles.thresholdsPanel} style={{ background: panelBg, border: `1px solid ${divider}` }}>
                  <div className={styles.thresholdsTitle} style={{ color: t.textMuted }}>Bucket Thresholds</div>
                  <div className={styles.thresholdsRow}>
                    {(['HOT', 'WARM'] as const).map(bucket => (
                      <div key={bucket}>
                        <label className={styles.miniLabel} style={{ color: t.textFaint }}>{bucket} (score ≥)</label>
                        <input type="number" value={thresholds[bucket]}
                          onChange={e => setThresholds(th => ({ ...th, [bucket]: Number(e.target.value) }))}
                          style={{ ...inputSm, width: 80 }} />
                      </div>
                    ))}
                    <span className={styles.thresholdHint} style={{ color: t.textFaint }}>NURTURE = below WARM</span>
                  </div>
                </div>

                <div className={styles.scoringRulesContainer}>
                  <div className={`${styles.scoringGrid} ${styles.scoringGridHeader}`}>
                    {['Question Key', 'Answer Value', 'Points', 'Reason', ''].map(h => (
                      <span key={h} className={styles.scoringColumnLabel} style={{ color: t.textFaint }}>{h}</span>
                    ))}
                  </div>
                  {scoringRules.map((rule, i) => (
                    <div key={i} className={styles.scoringGrid} style={{ alignItems: 'center' }}>
                      <input value={rule.key} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, key: e.target.value } : r))} placeholder="question_key" style={inputSm} />
                      <input value={rule.answer_value} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, answer_value: e.target.value } : r))} placeholder="answer" style={inputSm} />
                      <input type="number" value={rule.points} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, points: Number(e.target.value) } : r))} style={inputSm} />
                      <input value={rule.reason} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, reason: e.target.value } : r))} placeholder="reason" style={inputSm} />
                      <button onClick={() => setScoringRules(rs => rs.filter((_, j) => j !== i))} className={styles.removeButton} style={{ color: t.red }}>✕</button>
                    </div>
                  ))}
                  <button onClick={() => setScoringRules(rs => [...rs, { key: '', answer_value: '', points: 0, reason: '' }])}
                    className={styles.addButton} style={{ border: `1px dashed ${divider}`, color: t.textMuted }}>
                    + Add Scoring Rule
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
};
