import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../../../shared/contexts/ToastContext';
import { useT } from '../../../../shared/hooks/useT';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface QuestionOption { value: string; label: string; }
interface Question { question_key: string; type: string; label: string; required: boolean; options?: QuestionOption[]; order: number; }
interface BreakdownItem { question_key: string; answer: string; points: number; reason: string; }
interface SimulateResult { total: number; bucket: string; breakdown: BreakdownItem[]; explanation: string; email_preview?: { subject: string; body: string }; }

export const SimulationTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { error: toastError } = useToast();
  const t = useT();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [simulating, setSimulating] = useState(false);
  const [result, setResult] = useState<SimulateResult | null>(null);

  const fetchActiveForm = useCallback(async () => {
    setLoading(true);
    try {
      const formsRes = await axios.get(`${API}/buyer-leads/tenants/${tenantId}/forms`);
      const forms = formsRes.data as { id: number; status: string }[];
      const activeForm = forms.find((f) => f.status === 'active') ?? forms[0];
      if (!activeForm) { setLoading(false); return; }
      const versRes = await axios.get(`${API}/buyer-leads/tenants/${tenantId}/forms/${activeForm.id}/versions`);
      const activeVersion = (versRes.data as { is_active: boolean; schema_json: string }[]).find((v) => v.is_active);
      if (activeVersion?.schema_json) {
        const schema = JSON.parse(activeVersion.schema_json) as { questions: Question[] };
        const qs = Array.isArray(schema) ? schema : (schema.questions ?? []);
        setQuestions(qs.sort((a, b) => a.order - b.order));
      }
    } catch { toastError('Failed to load form questions'); } finally { setLoading(false); }
  }, [tenantId]);

  useEffect(() => { fetchActiveForm(); }, [fetchActiveForm]);

  const setAnswer = (key: string, value: string) => setAnswers(a => ({ ...a, [key]: value }));
  const toggleMultiAnswer = (key: string, value: string) => setAnswers(a => {
    const current = (a[key] as string[] | undefined) ?? [];
    return { ...a, [key]: current.includes(value) ? current.filter(v => v !== value) : [...current, value] };
  });

  const handleSimulate = async () => {
    setSimulating(true); setResult(null);
    try {
      const res = await axios.post<SimulateResult>(`${API}/buyer-leads/tenants/${tenantId}/simulate`, { answers });
      setResult(res.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Simulation failed');
    } finally { setSimulating(false); }
  };

  const bucketStyle = (bucket: string): React.CSSProperties => {
    if (bucket === 'HOT') return { background: t.redBg, border: `1px solid ${t.red}40`, color: t.red };
    if (bucket === 'WARM') return { background: t.orangeBg, border: `1px solid ${t.orange}40`, color: t.orange };
    return { background: t.accentBg, border: `1px solid ${t.accent}40`, color: t.accent };
  };

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>;
  if (questions.length === 0) return <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>No active form found. Publish a form version first.</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>Score Simulation</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ ...t.card, display: 'flex', flexDirection: 'column', gap: 16 }}>
            {questions.map((q) => (
              <div key={q.question_key}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: t.text, marginBottom: 8 }}>
                  {q.label}{q.required && <span style={{ color: t.red, marginLeft: 4 }}>*</span>}
                </label>
                {q.type === 'single_choice' && q.options && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {q.options.map((opt) => (
                      <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                        <input type="radio" name={q.question_key} value={opt.value}
                          checked={answers[q.question_key] === opt.value}
                          onChange={() => setAnswer(q.question_key, opt.value)}
                          style={{ accentColor: t.accent }} />
                        <span style={{ fontSize: 13, color: t.textSecondary }}>{opt.label}</span>
                      </label>
                    ))}
                  </div>
                )}
                {q.type === 'multi_select' && q.options && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {q.options.map((opt) => (
                      <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                        <input type="checkbox" value={opt.value}
                          checked={((answers[q.question_key] as string[]) ?? []).includes(opt.value)}
                          onChange={() => toggleMultiAnswer(q.question_key, opt.value)}
                          style={{ accentColor: t.accent }} />
                        <span style={{ fontSize: 13, color: t.textSecondary }}>{opt.label}</span>
                      </label>
                    ))}
                  </div>
                )}
                {(q.type === 'free_text' || q.type === 'phone' || q.type === 'email') && (
                  <input type={q.type === 'email' ? 'email' : q.type === 'phone' ? 'tel' : 'text'}
                    value={(answers[q.question_key] as string) ?? ''}
                    onChange={(e) => setAnswer(q.question_key, e.target.value)}
                    style={t.input} />
                )}
              </div>
            ))}
          </div>
          <button onClick={handleSimulate} disabled={simulating} style={{ ...t.btnPrimary, width: '100%', padding: '10px 18px', opacity: simulating ? 0.6 : 1 }}>
            {simulating ? 'Simulating…' : 'Simulate Score'}
          </button>
        </div>

        {/* Results */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ ...t.card, ...bucketStyle(result.bucket) }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', opacity: 0.7, margin: 0 }}>Score</p>
                  <p style={{ fontSize: 40, fontWeight: 700, margin: '4px 0 0' }}>{result.total}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', opacity: 0.7, margin: 0 }}>Bucket</p>
                  <p style={{ fontSize: 28, fontWeight: 700, margin: '4px 0 0' }}>{result.bucket}</p>
                </div>
              </div>
              {result.explanation && <p style={{ fontSize: 12, marginTop: 8, opacity: 0.8 }}>{result.explanation}</p>}
            </div>

            <div style={t.card}>
              <div style={t.sectionTitle}>Score Breakdown</div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>
                  {['Question', 'Answer', 'Points', 'Reason'].map(h => <th key={h} style={t.th}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {result.breakdown.map((item, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={{ ...t.td, fontSize: 12 }}>{item.question_key}</td>
                      <td style={{ ...t.td, fontSize: 12, color: t.textMuted }}>{item.answer}</td>
                      <td style={{ ...t.td, fontSize: 12, fontWeight: 600, color: item.points >= 0 ? t.green : t.red }}>{item.points >= 0 ? '+' : ''}{item.points}</td>
                      <td style={{ ...t.td, fontSize: 12, color: t.textMuted }}>{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {result.email_preview && (
              <div style={t.card}>
                <div style={t.sectionTitle}>Email Preview</div>
                <div style={{ marginBottom: 10 }}>
                  <p style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', marginBottom: 4 }}>Subject</p>
                  <p style={{ fontSize: 13, color: t.text, background: t.bgInput, padding: '8px 12px', borderRadius: 8, margin: 0 }}>{result.email_preview.subject}</p>
                </div>
                <div>
                  <p style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', marginBottom: 4 }}>Body</p>
                  <pre style={{ fontSize: 12, color: t.text, background: t.bgInput, padding: '8px 12px', borderRadius: 8, margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{result.email_preview.body}</pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
