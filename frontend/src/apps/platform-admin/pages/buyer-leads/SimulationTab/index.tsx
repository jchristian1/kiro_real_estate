import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '@/shared/contexts/ToastContext';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

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
      const formsRes = await axios.get(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms`);
      const forms = formsRes.data as { id: number; status: string }[];
      const activeForm = forms.find((f) => f.status === 'active') ?? forms[0];
      if (!activeForm) { setLoading(false); return; }
      const versRes = await axios.get(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${activeForm.id}/versions`);
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
      const res = await axios.post<SimulateResult>(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/simulate`, { answers });
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

  if (loading) return <div className={styles.loadingState} style={{ color: t.textMuted }}>Loading…</div>;
  if (questions.length === 0) return <div className={styles.emptyState} style={{ color: t.textMuted }}>No active form found. Publish a form version first.</div>;

  return (
    <div className={styles.container}>
      <h2 className={styles.title} style={{ color: t.text }}>Score Simulation</h2>

      <div className={styles.splitGrid}>
        <div className={styles.formColumn}>
          <div style={t.card} className={styles.formCard}>
            {questions.map((q) => (
              <div key={q.question_key}>
                <label className={styles.questionLabel} style={{ color: t.text }}>
                  {q.label}{q.required && <span className={styles.requiredMark} style={{ color: t.red }}>*</span>}
                </label>
                {q.type === 'single_choice' && q.options && (
                  <div className={styles.optionsList}>
                    {q.options.map((opt) => (
                      <label key={opt.value} className={styles.optionLabel}>
                        <input type="radio" name={q.question_key} value={opt.value}
                          checked={answers[q.question_key] === opt.value}
                          onChange={() => setAnswer(q.question_key, opt.value)}
                          style={{ accentColor: t.accent }} />
                        <span className={styles.optionText} style={{ color: t.textSecondary }}>{opt.label}</span>
                      </label>
                    ))}
                  </div>
                )}
                {q.type === 'multi_select' && q.options && (
                  <div className={styles.optionsList}>
                    {q.options.map((opt) => (
                      <label key={opt.value} className={styles.optionLabel}>
                        <input type="checkbox" value={opt.value}
                          checked={((answers[q.question_key] as string[]) ?? []).includes(opt.value)}
                          onChange={() => toggleMultiAnswer(q.question_key, opt.value)}
                          style={{ accentColor: t.accent }} />
                        <span className={styles.optionText} style={{ color: t.textSecondary }}>{opt.label}</span>
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
          <button onClick={handleSimulate} disabled={simulating}
            className={styles.simulateButton} style={{ ...t.btnPrimary, opacity: simulating ? 0.6 : 1 }}>
            {simulating ? 'Simulating…' : 'Simulate Score'}
          </button>
        </div>

        {result && (
          <div className={styles.resultsColumn}>
            <div style={{ ...t.card, ...bucketStyle(result.bucket) }}>
              <div className={styles.scoreBucketRow}>
                <div>
                  <p className={styles.scoreLabel}>Score</p>
                  <p className={styles.scoreValue}>{result.total}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p className={styles.scoreLabel}>Bucket</p>
                  <p className={styles.bucketValue}>{result.bucket}</p>
                </div>
              </div>
              {result.explanation && <p className={styles.explanation}>{result.explanation}</p>}
            </div>

            <div style={t.card}>
              <div style={t.sectionTitle}>Score Breakdown</div>
              <table className={styles.table}>
                <thead><tr>
                  {['Question', 'Answer', 'Points', 'Reason'].map(h => <th key={h} style={t.th}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {result.breakdown.map((item, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={t.td} className={styles.breakdownCell}>{item.question_key}</td>
                      <td style={{ ...t.td, color: t.textMuted }} className={styles.breakdownCell}>{item.answer}</td>
                      <td style={{ ...t.td, fontWeight: 600, color: item.points >= 0 ? t.green : t.red }} className={styles.breakdownCell}>{item.points >= 0 ? '+' : ''}{item.points}</td>
                      <td style={{ ...t.td, color: t.textMuted }} className={styles.breakdownCell}>{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {result.email_preview && (
              <div style={t.card}>
                <div style={t.sectionTitle}>Email Preview</div>
                <div style={{ marginBottom: 10 }}>
                  <p className={styles.previewLabel} style={{ color: t.textFaint }}>Subject</p>
                  <p className={styles.previewSubject} style={{ color: t.text, background: t.bgInput }}>{result.email_preview.subject}</p>
                </div>
                <div>
                  <p className={styles.previewLabel} style={{ color: t.textFaint }}>Body</p>
                  <pre className={styles.previewBody} style={{ color: t.text, background: t.bgInput }}>{result.email_preview.body}</pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
