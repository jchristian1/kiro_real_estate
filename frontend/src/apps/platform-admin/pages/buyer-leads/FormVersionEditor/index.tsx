import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '@/shared/contexts/ToastContext';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

interface QuestionOption { value: string; label: string; }
interface Question {
  question_key: string;
  type: 'single_choice' | 'multi_select' | 'free_text' | 'phone' | 'email';
  label: string;
  required: boolean;
  options: QuestionOption[];
  order: number;
}
interface LogicRule { if: { question_key: string; answer: string }; then: { hide: string[] }; }

const QUESTION_TYPES = ['single_choice', 'multi_select', 'free_text', 'phone', 'email'] as const;
const emptyQuestion = (): Question => ({ question_key: '', type: 'single_choice', label: '', required: true, options: [], order: 0 });

export const FormVersionEditor: React.FC = () => {
  const { tenantId, formId } = useParams<{ tenantId: string; formId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();
  const t = useT();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [logicRules, setLogicRules] = useState<LogicRule[]>([]);
  const [templateName, setTemplateName] = useState('');
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const fetchTemplate = useCallback(async () => {
    setLoading(true);
    try {
      const [tmplRes, versRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${formId}`),
        axios.get(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${formId}/versions`),
      ]);
      setTemplateName(tmplRes.data.name);
      const activeVersion = (versRes.data as { is_active: boolean; schema_json?: string }[]).find(v => v.is_active);
      if (activeVersion?.schema_json) {
        const schema = JSON.parse(activeVersion.schema_json) as { questions?: Question[]; logic_rules?: LogicRule[] } | Question[];
        const rawQuestions = Array.isArray(schema) ? schema : (schema.questions ?? []);
        const logicRules = Array.isArray(schema) ? [] : (schema.logic_rules ?? []);
        const questions = rawQuestions.map((q: any) => ({
          ...q,
          options: q.options ?? (q.options_json ? JSON.parse(q.options_json) : []),
        }));
        const parsedLogicRules = logicRules.map((r: any) =>
          typeof r.rule_json === 'string' ? JSON.parse(r.rule_json) : r
        );
        setQuestions(questions.sort((a, b) => a.order - b.order));
        setLogicRules(parsedLogicRules);
      }
    } catch { toastError('Failed to load form template'); } finally { setLoading(false); }
  }, [tenantId, formId]);

  useEffect(() => { fetchTemplate(); }, [fetchTemplate]);

  const handleDragStart = (index: number) => setDragIndex(index);
  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === index) return;
    const reordered = [...questions];
    const [moved] = reordered.splice(dragIndex, 1);
    reordered.splice(index, 0, moved);
    setQuestions(reordered.map((q, i) => ({ ...q, order: i + 1 })));
    setDragIndex(index);
  };

  const updateQuestion = (index: number, patch: Partial<Question>) =>
    setQuestions(qs => qs.map((q, i) => i === index ? { ...q, ...patch } : q));

  const removeQuestion = (index: number) =>
    setQuestions(qs => qs.filter((_, i) => i !== index).map((q, i) => ({ ...q, order: i + 1 })));

  const addOption = (qIndex: number) =>
    updateQuestion(qIndex, { options: [...questions[qIndex].options, { value: '', label: '' }] });

  const updateOption = (qIndex: number, oIndex: number, patch: Partial<QuestionOption>) => {
    const opts = questions[qIndex].options.map((o, i) => i === oIndex ? { ...o, ...patch } : o);
    updateQuestion(qIndex, { options: opts });
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      const payload = {
        questions: questions.map(q => ({
          question_key: q.question_key, type: q.type, label: q.label, required: q.required, order: q.order,
          options_json: q.options.length > 0 ? JSON.stringify(q.options) : null, validation_json: null,
        })),
        logic_rules: logicRules.map(r => ({ rule_json: JSON.stringify(r) })),
      };
      console.log('Publishing payload:', JSON.stringify(payload, null, 2));
      await axios.post(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${formId}/versions`, payload);
      success('New version published');
      navigate(`/buyer-leads/${tenantId}/forms`);
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { detail?: string; message?: string } } })?.response?.data;
      const msg = data?.detail || data?.message;
      toastError(msg || 'Failed to publish version');
      console.error('Publish error:', (err as { response?: unknown })?.response);
    } finally { setPublishing(false); }
  };

  if (loading) return <div className={styles.loadingState} style={{ color: t.textMuted }}>Loading…</div>;

  const inputSm: React.CSSProperties = { ...t.input, padding: '6px 10px', fontSize: 12 };

  return (
    <div className={styles.container}>
      <div className={styles.headerRow}>
        <div>
          <button onClick={() => navigate(`/buyer-leads/${tenantId}/forms`)} className={styles.backButton} style={{ color: t.accent }}>← Back to Forms</button>
          <h2 className={styles.pageTitle} style={{ color: t.text }}>{templateName}</h2>
        </div>
        <div className={styles.headerActions}>
          <button onClick={() => setShowPreview(v => !v)} style={t.btnSecondary}>{showPreview ? 'Hide Preview' : 'JSON Preview'}</button>
          <button onClick={handlePublish} disabled={publishing || questions.length === 0} style={{ ...t.btnPrimary, opacity: publishing || questions.length === 0 ? 0.5 : 1 }}>
            {publishing ? 'Publishing…' : 'Publish Version'}
          </button>
        </div>
      </div>

      {showPreview && (
        <pre className={styles.jsonPreview} style={{ border: `1px solid ${t.border}` }}>
          {JSON.stringify({ questions, logic_rules: logicRules }, null, 2)}
        </pre>
      )}

      <div className={styles.questionsContainer}>
        <div className={styles.sectionHeader}>
          <div style={t.sectionTitle}>Questions</div>
          <button onClick={() => setQuestions(qs => [...qs, { ...emptyQuestion(), order: qs.length + 1 }])} style={t.btnSecondary}>+ Add Question</button>
        </div>

        {questions.map((q, qi) => (
          <div key={qi} draggable onDragStart={() => handleDragStart(qi)} onDragOver={(e) => handleDragOver(e, qi)} onDragEnd={() => setDragIndex(null)}
            style={t.card} className={`${styles.questionCard} ${dragIndex === qi ? styles.questionCardDragging : ''}`}>
            <div className={styles.questionHeader}>
              <span className={styles.questionOrder} style={{ color: t.textFaint }}>Q{q.order} ⠿</span>
              <button onClick={() => removeQuestion(qi)} className={styles.removeButton} style={{ color: t.red }}>Remove</button>
            </div>
            <div className={styles.twoColGrid}>
              <div>
                <label style={t.labelStyle}>Question Key</label>
                <input type="text" value={q.question_key} onChange={(e) => updateQuestion(qi, { question_key: e.target.value })} placeholder="e.g. timeline" style={inputSm} />
              </div>
              <div>
                <label style={t.labelStyle}>Type</label>
                <select value={q.type} onChange={(e) => updateQuestion(qi, { type: e.target.value as Question['type'] })} style={inputSm}>
                  {QUESTION_TYPES.map(tp => <option key={tp} value={tp}>{tp}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label style={t.labelStyle}>Label</label>
              <input type="text" value={q.label} onChange={(e) => updateQuestion(qi, { label: e.target.value })} placeholder="Question text shown to the lead" style={inputSm} />
            </div>
            <label className={styles.checkboxLabel} style={{ color: t.textSecondary }}>
              <input type="checkbox" checked={q.required} onChange={(e) => updateQuestion(qi, { required: e.target.checked })} style={{ accentColor: t.accent }} />
              Required
            </label>
            {(q.type === 'single_choice' || q.type === 'multi_select') && (
              <div className={styles.optionsContainer}>
                <div className={styles.optionsHeader}>
                  <span className={styles.optionsLabel} style={{ color: t.textMuted }}>Options</span>
                  <button onClick={() => addOption(qi)} className={styles.addOptionButton} style={{ color: t.accent }}>+ Add Option</button>
                </div>
                {q.options.map((opt, oi) => (
                  <div key={oi} className={styles.optionRow}>
                    <input type="text" value={opt.value} onChange={(e) => updateOption(qi, oi, { value: e.target.value })} placeholder="value" style={inputSm} className={styles.optionInput} />
                    <input type="text" value={opt.label} onChange={(e) => updateOption(qi, oi, { label: e.target.value })} placeholder="label" style={inputSm} className={styles.optionInput} />
                    <button onClick={() => updateQuestion(qi, { options: q.options.filter((_, i) => i !== oi) })} className={styles.removeOptionButton} style={{ color: t.red }}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className={styles.logicRulesContainer}>
        <div className={styles.sectionHeader}>
          <div style={t.sectionTitle}>Conditional Logic Rules</div>
          <button onClick={() => setLogicRules(rs => [...rs, { if: { question_key: '', answer: '' }, then: { hide: [] } }])} style={t.btnSecondary}>+ Add Rule</button>
        </div>
        {logicRules.map((rule, ri) => (
          <div key={ri} style={t.card} className={styles.ruleCard}>
            <div className={styles.ruleHeader}>
              <span className={styles.ruleLabel} style={{ color: t.textMuted }}>Rule {ri + 1}</span>
              <button onClick={() => setLogicRules(rs => rs.filter((_, i) => i !== ri))} className={styles.removeButton} style={{ color: t.red }}>Remove</button>
            </div>
            <div className={styles.twoColGrid}>
              <div>
                <label style={t.labelStyle}>If question_key</label>
                <input type="text" value={rule.if.question_key} onChange={(e) => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, if: { ...r.if, question_key: e.target.value } } : r))} placeholder="e.g. has_agent" style={inputSm} />
              </div>
              <div>
                <label style={t.labelStyle}>equals answer</label>
                <input type="text" value={rule.if.answer} onChange={(e) => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, if: { ...r.if, answer: e.target.value } } : r))} placeholder="e.g. yes" style={inputSm} />
              </div>
            </div>
            <div>
              <label style={t.labelStyle}>Then hide (comma-separated question keys)</label>
              <input type="text" value={rule.then.hide.join(', ')}
                onChange={(e) => setLogicRules(rs => rs.map((r, i) => i === ri ? { ...r, then: { hide: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } } : r))}
                placeholder="e.g. wants_tour, areas" style={inputSm} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
