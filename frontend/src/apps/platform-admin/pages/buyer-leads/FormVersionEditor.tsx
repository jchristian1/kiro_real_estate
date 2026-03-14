import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../../../shared/contexts/ToastContext';
import { useT } from '../../../../shared/hooks/useT';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

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
        axios.get(`${API}/buyer-leads/tenants/${tenantId}/forms/${formId}`),
        axios.get(`${API}/buyer-leads/tenants/${tenantId}/forms/${formId}/versions`),
      ]);
      setTemplateName(tmplRes.data.name);
      const activeVersion = (versRes.data as { is_active: boolean; schema_json?: string }[]).find(v => v.is_active);
      if (activeVersion?.schema_json) {
        const schema = JSON.parse(activeVersion.schema_json) as Question[];
        setQuestions(schema.sort((a, b) => a.order - b.order));
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
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/forms/${formId}/versions`, { questions, logic_rules: logicRules });
      success('New version published');
      navigate(`/buyer-leads/${tenantId}/forms`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Failed to publish version');
    } finally { setPublishing(false); }
  };

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>;

  const inputSm: React.CSSProperties = { ...t.input, padding: '6px 10px', fontSize: 12 };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <button onClick={() => navigate(`/buyer-leads/${tenantId}/forms`)} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, marginBottom: 6, padding: 0 }}>← Back to Forms</button>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: t.text, margin: 0 }}>{templateName}</h2>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setShowPreview(v => !v)} style={t.btnSecondary}>{showPreview ? 'Hide Preview' : 'JSON Preview'}</button>
          <button onClick={handlePublish} disabled={publishing || questions.length === 0} style={{ ...t.btnPrimary, opacity: publishing || questions.length === 0 ? 0.5 : 1 }}>
            {publishing ? 'Publishing…' : 'Publish Version'}
          </button>
        </div>
      </div>

      {showPreview && (
        <pre style={{ background: '#0d1117', color: '#7ee787', fontSize: 11, padding: 16, borderRadius: 12, overflow: 'auto', maxHeight: 240, border: `1px solid ${t.border}` }}>
          {JSON.stringify({ questions, logic_rules: logicRules }, null, 2)}
        </pre>
      )}

      {/* Questions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={t.sectionTitle}>Questions</div>
          <button onClick={() => setQuestions(qs => [...qs, { ...emptyQuestion(), order: qs.length + 1 }])} style={t.btnSecondary}>+ Add Question</button>
        </div>

        {questions.map((q, qi) => (
          <div key={qi} draggable onDragStart={() => handleDragStart(qi)} onDragOver={(e) => handleDragOver(e, qi)} onDragEnd={() => setDragIndex(null)}
            style={{ ...t.card, cursor: 'grab', opacity: dragIndex === qi ? 0.5 : 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, color: t.textFaint, fontWeight: 500 }}>Q{q.order} ⠿</span>
              <button onClick={() => removeQuestion(qi)} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Remove</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
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
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: t.textSecondary, cursor: 'pointer' }}>
              <input type="checkbox" checked={q.required} onChange={(e) => updateQuestion(qi, { required: e.target.checked })} style={{ accentColor: t.accent }} />
              Required
            </label>
            {(q.type === 'single_choice' || q.type === 'multi_select') && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 11, color: t.textMuted }}>Options</span>
                  <button onClick={() => addOption(qi)} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>+ Add Option</button>
                </div>
                {q.options.map((opt, oi) => (
                  <div key={oi} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input type="text" value={opt.value} onChange={(e) => updateOption(qi, oi, { value: e.target.value })} placeholder="value" style={{ ...inputSm, flex: 1 }} />
                    <input type="text" value={opt.label} onChange={(e) => updateOption(qi, oi, { label: e.target.value })} placeholder="label" style={{ ...inputSm, flex: 1 }} />
                    <button onClick={() => updateQuestion(qi, { options: q.options.filter((_, i) => i !== oi) })} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 14 }}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Logic Rules */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={t.sectionTitle}>Conditional Logic Rules</div>
          <button onClick={() => setLogicRules(rs => [...rs, { if: { question_key: '', answer: '' }, then: { hide: [] } }])} style={t.btnSecondary}>+ Add Rule</button>
        </div>
        {logicRules.map((rule, ri) => (
          <div key={ri} style={{ ...t.card, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 500 }}>Rule {ri + 1}</span>
              <button onClick={() => setLogicRules(rs => rs.filter((_, i) => i !== ri))} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Remove</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
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
