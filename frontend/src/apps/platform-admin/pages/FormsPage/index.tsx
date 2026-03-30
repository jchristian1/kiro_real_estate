/**
 * Forms Page — unified form + scoring builder.
 * Single view: card list + slide-in drawer with form questions AND scoring in one scroll.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios, { AxiosError } from 'axios';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { useToast } from '@/shared/contexts/ToastContext';
import { useAuth } from '@/apps/platform-admin/contexts';
import { ConfirmDialog } from '@/platform-admin-components/ConfirmDialog';


const API = '/api/v1';

// ─── Types ────────────────────────────────────────────────────────────────────

interface FormTemplate {
  id: number;
  name: string;
  status: 'active' | 'draft' | 'archived';
  intent_type: string;
  created_at: string;
}

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

const QUESTION_TYPES = ['single_choice', 'multi_select', 'free_text', 'phone', 'email'] as const;
const emptyQuestion = (order: number): Question => ({
  question_key: '', type: 'single_choice', label: '', required: true, options: [], order,
});

// ─── Section Header ───────────────────────────────────────────────────────────

const SectionHeader: React.FC<{ icon: string; label: string; divider: string; textFaint: string }> = ({ icon, label, divider, textFaint }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
    <span style={{ fontSize: 16 }}>{icon}</span>
    <span style={{ fontSize: 12, fontWeight: 700, color: textFaint, textTransform: 'uppercase', letterSpacing: '0.6px' }}>{label}</span>
    <div style={{ flex: 1, height: 1, background: divider }} />
  </div>
);

// ─── Form Drawer ──────────────────────────────────────────────────────────────

interface DrawerProps {
  form: FormTemplate | null; // null = create mode
  tenantId: string;
  onClose: () => void;
  onSaved: () => void;
}

const FormDrawer: React.FC<DrawerProps> = ({ form, tenantId, onClose, onSaved }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();

  // Form meta
  const [name, setName] = useState(form?.name ?? '');
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!form);

  // Form builder
  const [questions, setQuestions] = useState<Question[]>([]);
  const [logicRules, setLogicRules] = useState<LogicRule[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  // Scoring
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

  // Load existing form data
  useEffect(() => {
    if (!form) { setLoading(false); return; }
    setName(form.name);
    setLoading(true);
    Promise.all([
      axios.get(`${API}/buyer-leads/tenants/${tenantId}/forms/${form.id}/versions`),
      axios.get<{ id: number }[]>(`${API}/buyer-leads/tenants/${tenantId}/scoring`),
    ]).then(async ([versRes, scoringRes]) => {
      // Form questions
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
      // Scoring config
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

  // Create new form
  const handleCreate = async () => {
    if (!name.trim()) { setServerError('Name is required.'); return; }
    setSaving(true); setServerError(null);
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/forms`, { name: name.trim(), intent_type: 'BUY' });
      success('Form created');
      onSaved();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string }>;
      setServerError(e.response?.data?.detail || 'Create failed');
    } finally { setSaving(false); }
  };

  // Publish form version
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
      success('Form version published');
      onSaved();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string }>;
      toastError(e.response?.data?.detail || 'Publish failed');
    } finally { setPublishing(false); }
  };

  // Publish scoring version
  const handlePublishScoring = async () => {
    if (!scoringConfigId) {
      // Create scoring config first
      try {
        const res = await axios.post<{ id: number }>(`${API}/buyer-leads/tenants/${tenantId}/scoring`, {
          name: `${name} Scoring`, intent_type: 'BUY',
        });
        setScoringConfigId(res.data.id);
        await axios.post(`${API}/buyer-leads/tenants/${tenantId}/scoring/${res.data.id}/versions`, {
          rules: scoringRules, thresholds,
        });
      } catch { toastError('Failed to create scoring config'); return; }
    } else {
      setPublishingScore(true);
      try {
        await axios.post(`${API}/buyer-leads/tenants/${tenantId}/scoring/${scoringConfigId}/versions`, {
          rules: scoringRules, thresholds,
        });
      } catch (err) {
        const e = err as AxiosError<{ detail?: string }>;
        toastError(e.response?.data?.detail || 'Scoring publish failed');
        setPublishingScore(false);
        return;
      }
      setPublishingScore(false);
    }
    success('Scoring published');
  };

  // Question helpers
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
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 40, backdropFilter: 'blur(2px)' }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: '100%', maxWidth: 760,
        background: drawerBg, zIndex: 50, display: 'flex', flexDirection: 'column',
        boxShadow: '-8px 0 40px rgba(0,0,0,0.35)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px', borderBottom: `1px solid ${divider}`, flexShrink: 0 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: t.text }}>{form ? 'Edit Form' : 'New Form'}</div>
            {form && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <span style={{ padding: '2px 8px', fontSize: 11, fontWeight: 600, background: statusBg(form.status), color: statusColor(form.status), borderRadius: 20 }}>{form.status}</span>
                <span style={{ fontSize: 12, color: t.textFaint }}>{form.intent_type}</span>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {!form && (
              <button onClick={handleCreate} disabled={saving}
                style={{ padding: '8px 18px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.6 : 1 }}>
                {saving ? 'Creating…' : 'Create Form'}
              </button>
            )}
            {form && (
              <>
                <button onClick={handlePublishScoring} disabled={publishingScore}
                  style={{ padding: '8px 14px', fontSize: 13, fontWeight: 600, background: isDark ? '#1e2330' : '#f0f4ff', color: t.accent, border: `1px solid ${t.accent}30`, borderRadius: 8, cursor: 'pointer', opacity: publishingScore ? 0.6 : 1 }}>
                  {publishingScore ? 'Saving…' : 'Save Scoring'}
                </button>
                <button onClick={handlePublishForm} disabled={publishing || questions.length === 0}
                  style={{ padding: '8px 18px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', opacity: publishing || questions.length === 0 ? 0.6 : 1 }}>
                  {publishing ? 'Publishing…' : 'Publish Form'}
                </button>
              </>
            )}
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: t.textMuted, fontSize: 20, cursor: 'pointer', lineHeight: 1, padding: '4px 8px' }}>×</button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 32 }}>
          {serverError && (
            <div style={{ padding: '10px 14px', background: isDark ? '#2d1a1a' : '#fff0f0', border: `1px solid ${t.red}40`, color: t.red, borderRadius: 8, fontSize: 13 }}>
              {serverError}
            </div>
          )}

          {/* Form name */}
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 6 }}>
              Form Name <span style={{ color: t.red }}>*</span>
            </label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Buyer Qualification Form"
              style={{ ...inputStyle, maxWidth: 400 }} disabled={!!form} />
            {form && <p style={{ fontSize: 11, color: t.textFaint, marginTop: 4 }}>Rename via the card menu.</p>}
          </div>

          {loading ? (
            <div style={{ color: t.textMuted, fontSize: 13 }}>Loading form data…</div>
          ) : form ? (
            <>
              {/* ── SECTION 1: Questions ── */}
              <div>
                <SectionHeader icon="📋" label="Form Questions" divider={divider} textFaint={t.textFaint} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {questions.map((q, qi) => (
                    <div key={qi} draggable onDragStart={() => setDragIndex(qi)}
                      onDragOver={e => handleDragOver(e, qi)} onDragEnd={() => setDragIndex(null)}
                      style={{ background: panelBg, border: `1px solid ${divider}`, borderRadius: 10, padding: 16, cursor: 'grab', opacity: dragIndex === qi ? 0.5 : 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 11, color: t.textFaint, fontWeight: 600 }}>Q{q.order} ⠿</span>
                        <button onClick={() => removeQuestion(qi)} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Remove</button>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div>
                          <label style={{ display: 'block', fontSize: 11, color: t.textFaint, marginBottom: 4 }}>Key</label>
                          <input value={q.question_key} onChange={e => updateQuestion(qi, { question_key: e.target.value })} placeholder="e.g. timeline" style={inputSm} />
                        </div>
                        <div>
                          <label style={{ display: 'block', fontSize: 11, color: t.textFaint, marginBottom: 4 }}>Type</label>
                          <select value={q.type} onChange={e => updateQuestion(qi, { type: e.target.value as Question['type'] })} style={inputSm}>
                            {QUESTION_TYPES.map(tp => <option key={tp} value={tp}>{tp}</option>)}
                          </select>
                        </div>
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: 11, color: t.textFaint, marginBottom: 4 }}>Label</label>
                        <input value={q.label} onChange={e => updateQuestion(qi, { label: e.target.value })} placeholder="Question shown to the lead" style={inputSm} />
                      </div>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: t.textMuted, cursor: 'pointer' }}>
                        <input type="checkbox" checked={q.required} onChange={e => updateQuestion(qi, { required: e.target.checked })} style={{ accentColor: t.accent }} />
                        Required
                      </label>
                      {(q.type === 'single_choice' || q.type === 'multi_select') && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: 11, color: t.textFaint }}>Options</span>
                            <button onClick={() => updateQuestion(qi, { options: [...q.options, { value: '', label: '' }] })}
                              style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>+ Add Option</button>
                          </div>
                          {q.options.map((opt, oi) => (
                            <div key={oi} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                              <input value={opt.value} onChange={e => updateQuestion(qi, { options: q.options.map((o, i) => i === oi ? { ...o, value: e.target.value } : o) })} placeholder="value" style={{ ...inputSm, flex: 1 }} />
                              <input value={opt.label} onChange={e => updateQuestion(qi, { options: q.options.map((o, i) => i === oi ? { ...o, label: e.target.value } : o) })} placeholder="label" style={{ ...inputSm, flex: 1 }} />
                              <button onClick={() => updateQuestion(qi, { options: q.options.filter((_, i) => i !== oi) })} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 14 }}>✕</button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  <button onClick={() => setQuestions(qs => [...qs, emptyQuestion(qs.length + 1)])}
                    style={{ padding: '10px', fontSize: 13, background: 'none', border: `1px dashed ${divider}`, borderRadius: 10, color: t.textMuted, cursor: 'pointer', textAlign: 'center' }}>
                    + Add Question
                  </button>
                </div>
              </div>

              {/* ── SECTION 2: Conditional Logic ── */}
              <div>
                <SectionHeader icon="🔀" label="Conditional Logic" divider={divider} textFaint={t.textFaint} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {logicRules.map((rule, ri) => (
                    <div key={ri} style={{ background: panelBg, border: `1px solid ${divider}`, borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 11, color: t.textFaint, fontWeight: 600 }}>Rule {ri + 1}</span>
                        <button onClick={() => setLogicRules(rs => rs.filter((_, i) => i !== ri))} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Remove</button>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div>
                          <label style={{ display: 'block', fontSize: 11, color: t.textFaint, marginBottom: 4 }}>If question key</label>
                          <input value={rule.if.question_key} onChange={e => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, if: { ...r.if, question_key: e.target.value } } : r))} placeholder="e.g. has_agent" style={inputSm} />
                        </div>
                        <div>
                          <label style={{ display: 'block', fontSize: 11, color: t.textFaint, marginBottom: 4 }}>equals answer</label>
                          <input value={rule.if.answer} onChange={e => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, if: { ...r.if, answer: e.target.value } } : r))} placeholder="e.g. yes" style={inputSm} />
                        </div>
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: 11, color: t.textFaint, marginBottom: 4 }}>Then hide (comma-separated keys)</label>
                        <input value={rule.then.hide.join(', ')} onChange={e => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, then: { hide: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } } : r))} placeholder="e.g. wants_tour, areas" style={inputSm} />
                      </div>
                    </div>
                  ))}
                  <button onClick={() => setLogicRules(rs => [...rs, { if: { question_key: '', answer: '' }, then: { hide: [] } }])}
                    style={{ padding: '10px', fontSize: 13, background: 'none', border: `1px dashed ${divider}`, borderRadius: 10, color: t.textMuted, cursor: 'pointer', textAlign: 'center' }}>
                    + Add Logic Rule
                  </button>
                </div>
              </div>

              {/* ── SECTION 3: Scoring ── */}
              <div>
                <SectionHeader icon="🎯" label="Lead Scoring" divider={divider} textFaint={t.textFaint} />

                {/* Thresholds */}
                <div style={{ background: panelBg, border: `1px solid ${divider}`, borderRadius: 10, padding: 16, marginBottom: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 12 }}>Bucket Thresholds</div>
                  <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                    {(['HOT', 'WARM'] as const).map(bucket => (
                      <div key={bucket}>
                        <label style={{ display: 'block', fontSize: 11, color: t.textFaint, marginBottom: 4 }}>{bucket} (score ≥)</label>
                        <input type="number" value={thresholds[bucket]}
                          onChange={e => setThresholds(th => ({ ...th, [bucket]: Number(e.target.value) }))}
                          style={{ ...inputSm, width: 80 }} />
                      </div>
                    ))}
                    <span style={{ fontSize: 11, color: t.textFaint, paddingBottom: 4 }}>NURTURE = below WARM</span>
                  </div>
                </div>

                {/* Scoring rules */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 80px 1fr 32px', gap: 8, padding: '0 4px' }}>
                    {['Question Key', 'Answer Value', 'Points', 'Reason', ''].map(h => (
                      <span key={h} style={{ fontSize: 10, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.4px' }}>{h}</span>
                    ))}
                  </div>
                  {scoringRules.map((rule, i) => (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 80px 1fr 32px', gap: 8, alignItems: 'center' }}>
                      <input value={rule.key} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, key: e.target.value } : r))} placeholder="question_key" style={inputSm} />
                      <input value={rule.answer_value} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, answer_value: e.target.value } : r))} placeholder="answer" style={inputSm} />
                      <input type="number" value={rule.points} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, points: Number(e.target.value) } : r))} style={inputSm} />
                      <input value={rule.reason} onChange={e => setScoringRules(rs => rs.map((r, j) => j === i ? { ...r, reason: e.target.value } : r))} placeholder="reason" style={inputSm} />
                      <button onClick={() => setScoringRules(rs => rs.filter((_, j) => j !== i))} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, textAlign: 'center' }}>✕</button>
                    </div>
                  ))}
                  <button onClick={() => setScoringRules(rs => [...rs, { key: '', answer_value: '', points: 0, reason: '' }])}
                    style={{ padding: '10px', fontSize: 13, background: 'none', border: `1px dashed ${divider}`, borderRadius: 10, color: t.textMuted, cursor: 'pointer', textAlign: 'center' }}>
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

// ─── Form Card ────────────────────────────────────────────────────────────────

const FormCard: React.FC<{
  form: FormTemplate;
  onEdit: () => void;
  onDelete: () => void;
  onRename: () => void;
}> = ({ form, onEdit, onDelete, onRename }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const [hovered, setHovered] = useState(false);

  const statusColor = form.status === 'active' ? t.green : form.status === 'draft' ? t.yellow : t.textFaint;
  const statusBg = form.status === 'active' ? t.greenBg : form.status === 'draft' ? t.yellowBg : t.bgBadge;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onEdit}
      style={{
        background: isDark ? '#1c1f26' : '#ffffff',
        border: `1px solid ${hovered ? t.accent + '60' : (isDark ? '#2a2d35' : '#e5e7eb')}`,
        borderRadius: 12, padding: '16px 20px', cursor: 'pointer', transition: 'all 0.15s',
        boxShadow: hovered ? `0 0 0 1px ${t.accent}30, 0 4px 20px rgba(0,0,0,0.15)` : isDark ? '0 1px 4px rgba(0,0,0,0.2)' : '0 1px 4px rgba(0,0,0,0.05)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{form.name}</span>
          <span style={{ padding: '2px 8px', fontSize: 11, fontWeight: 600, background: statusBg, color: statusColor, borderRadius: 20, flexShrink: 0 }}>{form.status}</span>
        </div>
        <div style={{ fontSize: 12, color: t.textFaint }}>
          {form.intent_type} · Created {new Date(form.created_at).toLocaleDateString()}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
        <button onClick={onEdit} style={{ padding: '5px 12px', fontSize: 12, fontWeight: 500, background: isDark ? '#1e2330' : '#f0f4ff', color: t.accent, border: `1px solid ${t.accent}30`, borderRadius: 6, cursor: 'pointer' }}>Edit</button>
        <button onClick={onRename} style={{ padding: '5px 12px', fontSize: 12, fontWeight: 500, background: isDark ? '#1e2330' : '#f5f5f7', color: t.textMuted, border: `1px solid ${isDark ? '#2a2d35' : '#e5e7eb'}`, borderRadius: 6, cursor: 'pointer' }}>Rename</button>
        <button onClick={onDelete} style={{ padding: '5px 12px', fontSize: 12, fontWeight: 500, background: isDark ? '#2d1a1a' : '#fff0f0', color: t.red, border: `1px solid ${t.red}30`, borderRadius: 6, cursor: 'pointer' }}>Delete</button>
      </div>
    </div>
  );
};

// ─── Rename Modal ─────────────────────────────────────────────────────────────

const RenameModal: React.FC<{
  form: FormTemplate;
  tenantId: string;
  onClose: () => void;
  onSaved: () => void;
}> = ({ form, tenantId, onClose, onSaved }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();
  const [name, setName] = useState(form.name);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim() || name === form.name) { onClose(); return; }
    setSaving(true);
    try {
      await axios.put(`${API}/buyer-leads/tenants/${tenantId}/forms/${form.id}`, { name: name.trim() });
      success('Renamed'); onSaved();
    } catch { toastError('Rename failed'); }
    finally { setSaving(false); }
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 60 }} />
      <div style={{
        position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        background: isDark ? '#1c1f26' : '#ffffff', borderRadius: 12, padding: 24,
        width: '100%', maxWidth: 400, zIndex: 70, display: 'flex', flexDirection: 'column', gap: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>Rename Form</div>
        <input value={name} onChange={e => setName(e.target.value)} autoFocus
          onKeyDown={e => e.key === 'Enter' && handleSave()}
          style={{ background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 13, color: t.text, outline: 'none', width: '100%', boxSizing: 'border-box' }} />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onClose} style={{ padding: '7px 14px', fontSize: 13, background: 'none', border: `1px solid ${isDark ? '#2a2d35' : '#e5e7eb'}`, borderRadius: 8, color: t.textMuted, cursor: 'pointer' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} style={{ padding: '7px 14px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', opacity: saving ? 0.6 : 1 }}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export const FormsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();
  const { user } = useAuth();

  // Use company_id from auth; fall back to '1' for platform_admin (no company)
  const tenantId = String(user?.company_id ?? 1);

  const [forms, setForms] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [drawerForm, setDrawerForm] = useState<FormTemplate | null | 'new'>(undefined as unknown as null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FormTemplate | null>(null);
  const [renameTarget, setRenameTarget] = useState<FormTemplate | null>(null);
  const [search, setSearch] = useState('');

  const fetchForms = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<FormTemplate[]>(`${API}/buyer-leads/tenants/${tenantId}/forms`);
      setForms(res.data ?? []);
      setFetchError(null);
    } catch { setFetchError('Failed to load forms'); }
    finally { setLoading(false); }
  }, [tenantId]);

  useEffect(() => { fetchForms(); }, [fetchForms]);

  const openCreate = () => { setDrawerForm(null); setDrawerOpen(true); };
  const openEdit = (form: FormTemplate) => { setDrawerForm(form); setDrawerOpen(true); };
  const closeDrawer = () => setDrawerOpen(false);
  const handleSaved = () => { closeDrawer(); fetchForms(); };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API}/buyer-leads/tenants/${tenantId}/forms/${deleteTarget.id}`);
      success('Form deleted');
      setForms(prev => prev.filter(f => f.id !== deleteTarget.id));
    } catch { toastError('Delete failed'); }
    finally { setDeleteTarget(null); }
  };

  const filtered = forms.filter(f => f.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Forms</h1>
          <p style={{ fontSize: 13, color: t.textMuted, marginTop: 4 }}>
            Qualification forms sent to leads — includes questions and scoring in one place.
          </p>
        </div>
        <button onClick={openCreate} style={{ padding: '8px 18px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> New Form
        </button>
      </div>

      {/* Search */}
      {forms.length > 0 && (
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search forms…"
          style={{ background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 13, color: t.text, outline: 'none', maxWidth: 320 }} />
      )}

      {/* Content */}
      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
          <span style={{ color: t.textMuted, fontSize: 14 }}>Loading forms…</span>
        </div>
      ) : fetchError ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
          <span style={{ color: t.red, fontSize: 14 }}>{fetchError}</span>
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ background: isDark ? '#1c1f26' : '#ffffff', border: `1px solid ${isDark ? '#2a2d35' : '#e5e7eb'}`, borderRadius: 12, padding: 48, textAlign: 'center' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: t.text, marginBottom: 6 }}>
            {search ? 'No forms match your search' : 'No forms yet'}
          </div>
          <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 20 }}>
            {search ? 'Try a different search term.' : 'Create your first qualification form with questions and scoring.'}
          </div>
          {!search && (
            <button onClick={openCreate} style={{ padding: '8px 18px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>Create Form</button>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(form => (
            <FormCard
              key={form.id}
              form={form}
              onEdit={() => openEdit(form)}
              onDelete={() => setDeleteTarget(form)}
              onRename={() => setRenameTarget(form)}
            />
          ))}
        </div>
      )}

      {/* Drawer */}
      {drawerOpen && (
        <FormDrawer
          form={drawerForm as FormTemplate | null}
          tenantId={tenantId}
          onClose={closeDrawer}
          onSaved={handleSaved}
        />
      )}

      {/* Rename modal */}
      {renameTarget && (
        <RenameModal
          form={renameTarget}
          tenantId={tenantId}
          onClose={() => setRenameTarget(null)}
          onSaved={() => { setRenameTarget(null); fetchForms(); }}
        />
      )}

      {/* Delete confirm */}
      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Delete Form"
        message={`Delete "${deleteTarget?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        isDangerous
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
};
