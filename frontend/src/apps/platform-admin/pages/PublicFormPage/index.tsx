/**
 * Public Buyer Qualification Form
 * Accessible via the tokenized link sent in the invite email.
 * No authentication required.
 */
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import { FormQuestion } from './components';
import styles from './index.module.css';

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
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!token) return;
    axios.get(`${API_BASE_URL}/public/buyer-qualification/${token}`)
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
      await axios.post(`${API_BASE_URL}/public/buyer-qualification/${token}/submit`, { answers });
      setSubmitted(true);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.card}>
          <div className={styles.centeredMessage}>Loading form…</div>
        </div>
      </div>
    );
  }

  if (error && !submitted && questions.length === 0) {
    return (
      <div className={styles.page}>
        <div className={styles.card}>
          <div className={styles.centeredMessage}>
            <div className={styles.errorIcon}>🔗</div>
            <div className={styles.errorTitle}>Link unavailable</div>
            <div className={styles.errorSubtitle}>{error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className={styles.page}>
        <div className={styles.card}>
          <div className={styles.successContainer}>
            <div className={styles.successIcon}>✅</div>
            <div className={styles.successTitle}>Thank you!</div>
            <div className={styles.successMessage}>
              We've received your information and will be in touch with you shortly. You can close this page.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.formHeader}>
          <div className={styles.formTitle}>Buyer Qualification</div>
          <div className={styles.formSubtitle}>
            Help us understand your home search so we can match you with the right properties.
          </div>
        </div>

        <form onSubmit={handleSubmit} className={styles.formBody}>
          {questions.map((q, idx) => (
            <FormQuestion
              key={q.question_key}
              index={idx}
              questionKey={q.question_key}
              type={q.type}
              label={q.label}
              required={q.required}
              options={q.options}
              value={answers[q.question_key]}
              onChange={handleChange}
            />
          ))}

          {error && <div className={styles.errorAlert}>{error}</div>}

          <button type="submit" disabled={submitting}
            className={`${styles.submitButton} ${submitting ? styles.submitButtonDisabled : styles.submitButtonActive}`}>
            {submitting ? 'Submitting…' : 'Submit'}
          </button>
        </form>
      </div>
    </div>
  );
};
