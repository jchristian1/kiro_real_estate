/**
 * SimulationTab — render active form questions, simulate scoring, show breakdown + email preview.
 * Requirements: 15.1, 15.2, 15.3
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface QuestionOption { value: string; label: string; }

interface Question {
  question_key: string;
  type: string;
  label: string;
  required: boolean;
  options?: QuestionOption[];
  order: number;
}

interface BreakdownItem {
  question_key: string;
  answer: string;
  points: number;
  reason: string;
}

interface SimulateResult {
  total: number;
  bucket: string;
  breakdown: BreakdownItem[];
  explanation: string;
  email_preview?: { subject: string; body: string };
}

const bucketColor = (bucket: string) => {
  if (bucket === 'HOT') return 'bg-red-100 text-red-700 border-red-200';
  if (bucket === 'WARM') return 'bg-yellow-100 text-yellow-700 border-yellow-200';
  return 'bg-blue-100 text-blue-700 border-blue-200';
};

export const SimulationTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { error: toastError } = useToast();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [simulating, setSimulating] = useState(false);
  const [result, setResult] = useState<SimulateResult | null>(null);

  const fetchActiveForm = useCallback(async () => {
    setLoading(true);
    try {
      // Get active form version for this tenant
      const formsRes = await axios.get(`${API}/buyer-leads/tenants/${tenantId}/forms`);
      const forms = formsRes.data as { id: number; status: string }[];
      const activeForm = forms.find((f) => f.status === 'active') ?? forms[0];
      if (!activeForm) { setLoading(false); return; }

      const versRes = await axios.get(
        `${API}/buyer-leads/tenants/${tenantId}/forms/${activeForm.id}/versions`
      );
      const activeVersion = (versRes.data as { is_active: boolean; schema_json: string }[])
        .find((v) => v.is_active);
      if (activeVersion?.schema_json) {
        const schema = JSON.parse(activeVersion.schema_json) as { questions: Question[] };
        const qs = Array.isArray(schema) ? schema : (schema.questions ?? []);
        setQuestions(qs.sort((a, b) => a.order - b.order));
      }
    } catch {
      toastError('Failed to load form questions');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchActiveForm(); }, [fetchActiveForm]);

  const setAnswer = (key: string, value: string) => {
    setAnswers((a) => ({ ...a, [key]: value }));
  };

  const toggleMultiAnswer = (key: string, value: string) => {
    setAnswers((a) => {
      const current = (a[key] as string[] | undefined) ?? [];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...a, [key]: next };
    });
  };

  const handleSimulate = async () => {
    setSimulating(true);
    setResult(null);
    try {
      const res = await axios.post<SimulateResult>(
        `${API}/buyer-leads/tenants/${tenantId}/simulate`,
        { answers }
      );
      setResult(res.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Simulation failed');
    } finally {
      setSimulating(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading…</div>;

  if (questions.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500">
        No active form found. Publish a form version first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-700">Score Simulation</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow p-4 space-y-4">
            {questions.map((q) => (
              <div key={q.question_key}>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {q.label}
                  {q.required && <span className="text-red-500 ml-1">*</span>}
                </label>

                {q.type === 'single_choice' && q.options && (
                  <div className="space-y-1">
                    {q.options.map((opt) => (
                      <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          name={q.question_key}
                          value={opt.value}
                          checked={answers[q.question_key] === opt.value}
                          onChange={() => setAnswer(q.question_key, opt.value)}
                          className="text-blue-600"
                        />
                        <span className="text-sm text-gray-700">{opt.label}</span>
                      </label>
                    ))}
                  </div>
                )}

                {q.type === 'multi_select' && q.options && (
                  <div className="space-y-1">
                    {q.options.map((opt) => (
                      <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          value={opt.value}
                          checked={((answers[q.question_key] as string[]) ?? []).includes(opt.value)}
                          onChange={() => toggleMultiAnswer(q.question_key, opt.value)}
                          className="rounded text-blue-600"
                        />
                        <span className="text-sm text-gray-700">{opt.label}</span>
                      </label>
                    ))}
                  </div>
                )}

                {(q.type === 'free_text' || q.type === 'phone' || q.type === 'email') && (
                  <input
                    type={q.type === 'email' ? 'email' : q.type === 'phone' ? 'tel' : 'text'}
                    value={(answers[q.question_key] as string) ?? ''}
                    onChange={(e) => setAnswer(q.question_key, e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                )}
              </div>
            ))}
          </div>

          <button
            onClick={handleSimulate}
            disabled={simulating}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
          >
            {simulating ? 'Simulating…' : 'Simulate Score'}
          </button>
        </div>

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Score + bucket */}
            <div className={`rounded-lg border-2 p-4 ${bucketColor(result.bucket)}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide opacity-70">Score</p>
                  <p className="text-3xl font-bold">{result.total}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-medium uppercase tracking-wide opacity-70">Bucket</p>
                  <p className="text-2xl font-bold">{result.bucket}</p>
                </div>
              </div>
              {result.explanation && (
                <p className="text-xs mt-2 opacity-80">{result.explanation}</p>
              )}
            </div>

            {/* Breakdown */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Score Breakdown</h3>
              </div>
              <table className="min-w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Question</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Answer</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Points</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {result.breakdown.map((item, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-xs text-gray-700">{item.question_key}</td>
                      <td className="px-4 py-2 text-xs text-gray-500">{item.answer}</td>
                      <td className={`px-4 py-2 text-xs font-medium ${item.points >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                        {item.points >= 0 ? '+' : ''}{item.points}
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500">{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Email preview */}
            {result.email_preview && (
              <div className="bg-white rounded-lg shadow p-4 space-y-2">
                <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Email Preview</h3>
                <div>
                  <p className="text-xs text-gray-400 uppercase mb-1">Subject</p>
                  <p className="text-sm text-gray-800 bg-gray-50 px-3 py-2 rounded">{result.email_preview.subject}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase mb-1">Body</p>
                  <pre className="text-sm text-gray-800 bg-gray-50 px-3 py-2 rounded whitespace-pre-wrap font-sans">
                    {result.email_preview.body}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
