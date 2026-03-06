/**
 * Public Buyer Qualification Form
 * Accessible via the tokenized link sent in the invite email.
 * No authentication required.
 */
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const PUBLIC_API = API_BASE_URL.replace('/api/v1', '');

interface Option { value: string; label: string; }
interface Question {
  question_key: string;
  type: string;
  label: string;
  required: boolean;
  options?: Option[];
  order: number;
}

type Answers = Record<string, string | string[]>;

export const PublicFormPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Answers>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ total: number; bucket: string; explanation: string } | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!token) return;
    axios.get(`${PUBLIC_API}/public/buyer-qualification/${token}`)
      .then(r => {
        setQuestions((r.data.questions || []).sort((a: Question, b: Question) => a.order - b.order));
        setLoading(false);
      })
      .catch(e => {
        const msg = e.response?.data?.error || 'This link is invalid or has expired.';
        setError(msg);
        setLoading(false);
      });
  }, [token]);

  const handleChange = (key: string, value: string, multi = false) => {
    if (multi) {
      setAnswers(prev => {
        const current = (prev[key] as string[]) || [];
        return {
          ...prev,
          [key]: current.includes(value)
            ? current.filter(v => v !== value)
            : [...current, value],
        };
      });
    } else {
      setAnswers(prev => ({ ...prev, [key]: value }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Validate required
    for (const q of questions) {
      if (q.required) {
        const val = answers[q.question_key];
        if (!val || (Array.isArray(val) && val.length === 0)) {
          setError(`Please answer: "${q.label}"`);
          return;
        }
      }
    }
    setError(null);
    setSubmitting(true);
    try {
      const res = await axios.post(`${PUBLIC_API}/public/buyer-qualification/${token}/submit`, {
        answers,
      });
      setResult(res.data.score);
      setSubmitted(true);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const bucketColor = (b: string) => {
    if (b === 'HOT') return '#FF3B30';
    if (b === 'WARM') return '#FF9500';
    return '#8E8E93';
  };

  if (loading) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={{ textAlign: 'center', color: '#8E8E93', padding: 40 }}>Loading form…</div>
        </div>
      </div>
    );
  }

  if (error && !submitted && questions.length === 0) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={{ textAlign: 'center', padding: 40 }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🔗</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: '#1C1C1E', marginBottom: 8 }}>Link unavailable</div>
            <div style={{ fontSize: 15, color: '#8E8E93' }}>{error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={{ textAlign: 'center', padding: '32px 24px' }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#1C1C1E', marginBottom: 8 }}>
              Thanks for completing your profile!
            </div>
            {result && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, margin: '24px 0' }}>
                  <span style={{ fontSize: 52, fontWeight: 700, color: '#1C1C1E' }}>{result.total}</span>
                  <span style={{ background: bucketColor(result.bucket), color: '#fff', fontSize: 14, fontWeight: 700, padding: '5px 14px', borderRadius: 20 }}>
                    {result.bucket}
                  </span>
                </div>
                <div style={{ fontSize: 14, color: '#3C3C43', lineHeight: 1.6, maxWidth: 400, margin: '0 auto' }}>
                  {result.explanation}
                </div>
              </>
            )}
            <div style={{ marginTop: 24, fontSize: 14, color: '#8E8E93' }}>
              We'll be in touch soon. You can close this page.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={{ padding: '28px 28px 0' }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#1C1C1E', marginBottom: 4 }}>
            Buyer Qualification
          </div>
          <div style={{ fontSize: 14, color: '#8E8E93', marginBottom: 28 }}>
            Help us understand your home search so we can match you with the right properties.
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '0 28px 28px' }}>
          {questions.map((q, idx) => (
            <div key={q.question_key} style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: 15, fontWeight: 600, color: '#1C1C1E', marginBottom: 10 }}>
                {idx + 1}. {q.label}
                {q.required && <span style={{ color: '#FF3B30', marginLeft: 4 }}>*</span>}
              </label>

              {q.type === 'single_choice' && q.options && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {q.options.map(opt => (
                    <label key={opt.value} style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px',
                      borderRadius: 10, border: `1.5px solid ${answers[q.question_key] === opt.value ? '#007AFF' : '#E5E5EA'}`,
                      background: answers[q.question_key] === opt.value ? '#EAF4FF' : '#fff',
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}>
                      <input type="radio" name={q.question_key} value={opt.value}
                        checked={answers[q.question_key] === opt.value}
                        onChange={() => handleChange(q.question_key, opt.value)}
                        style={{ accentColor: '#007AFF' }} />
                      <span style={{ fontSize: 14, color: '#1C1C1E' }}>{opt.label}</span>
                    </label>
                  ))}
                </div>
              )}

              {q.type === 'multi_select' && q.options && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {q.options.map(opt => {
                    const selected = ((answers[q.question_key] as string[]) || []).includes(opt.value);
                    return (
                      <label key={opt.value} style={{
                        display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px',
                        borderRadius: 10, border: `1.5px solid ${selected ? '#007AFF' : '#E5E5EA'}`,
                        background: selected ? '#EAF4FF' : '#fff',
                        cursor: 'pointer', transition: 'all 0.15s',
                      }}>
                        <input type="checkbox" value={opt.value} checked={selected}
                          onChange={() => handleChange(q.question_key, opt.value, true)}
                          style={{ accentColor: '#007AFF' }} />
                        <span style={{ fontSize: 14, color: '#1C1C1E' }}>{opt.label}</span>
                      </label>
                    );
                  })}
                </div>
              )}

              {(q.type === 'free_text') && (
                <textarea value={(answers[q.question_key] as string) || ''} rows={3}
                  onChange={e => handleChange(q.question_key, e.target.value)}
                  style={styles.input} placeholder="Your answer…" />
              )}

              {(q.type === 'phone' || q.type === 'email') && (
                <input type={q.type === 'email' ? 'email' : 'tel'}
                  value={(answers[q.question_key] as string) || ''}
                  onChange={e => handleChange(q.question_key, e.target.value)}
                  style={styles.input}
                  placeholder={q.type === 'email' ? 'your@email.com' : '+1 (555) 000-0000'} />
              )}
            </div>
          ))}

          {error && (
            <div style={{ background: '#FFF2F2', border: '1px solid #FFD0D0', borderRadius: 10, padding: '12px 14px', marginBottom: 20, fontSize: 14, color: '#FF3B30' }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={submitting} style={{
            width: '100%', padding: '14px', background: submitting ? '#C7C7CC' : '#007AFF',
            color: '#fff', border: 'none', borderRadius: 12, fontSize: 16, fontWeight: 600,
            cursor: submitting ? 'not-allowed' : 'pointer', transition: 'background 0.15s',
          }}>
            {submitting ? 'Submitting…' : 'Submit'}
          </button>
        </form>
      </div>
    </div>
  );
};

const styles = {
  page: {
    minHeight: '100vh',
    background: '#F2F2F7',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    padding: '40px 16px 80px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif',
  } as React.CSSProperties,
  card: {
    background: '#fff',
    borderRadius: 20,
    boxShadow: '0 2px 20px rgba(0,0,0,0.08)',
    width: '100%',
    maxWidth: 560,
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '12px 14px',
    border: '1.5px solid #E5E5EA',
    borderRadius: 10,
    fontSize: 14,
    color: '#1C1C1E',
    outline: 'none',
    boxSizing: 'border-box',
  } as React.CSSProperties,
};
