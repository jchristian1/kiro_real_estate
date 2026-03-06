/**
 * FormVersionEditor — drag-and-drop question ordering, logic rule builder,
 * JSON schema preview, and publish new version.
 * Requirements: 11.3, 11.4
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

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

interface LogicRule {
  if: { question_key: string; answer: string };
  then: { hide: string[] };
}

const QUESTION_TYPES = ['single_choice', 'multi_select', 'free_text', 'phone', 'email'] as const;

const emptyQuestion = (): Question => ({
  question_key: '',
  type: 'single_choice',
  label: '',
  required: true,
  options: [],
  order: 0,
});

export const FormVersionEditor: React.FC = () => {
  const { tenantId, formId } = useParams<{ tenantId: string; formId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();

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
      // Load questions from the active version if available
      const activeVersion = (versRes.data as { is_active: boolean; schema_json?: string }[])
        .find((v) => v.is_active);
      if (activeVersion?.schema_json) {
        const schema = JSON.parse(activeVersion.schema_json) as Question[];
        setQuestions(schema.sort((a, b) => a.order - b.order));
      }
    } catch {
      toastError('Failed to load form template');
    } finally {
      setLoading(false);
    }
  }, [tenantId, formId]);

  useEffect(() => { fetchTemplate(); }, [fetchTemplate]);

  // Drag-and-drop reordering
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
  const handleDragEnd = () => setDragIndex(null);

  const addQuestion = () => {
    setQuestions((qs) => [...qs, { ...emptyQuestion(), order: qs.length + 1 }]);
  };

  const updateQuestion = (index: number, patch: Partial<Question>) => {
    setQuestions((qs) => qs.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  };

  const removeQuestion = (index: number) => {
    setQuestions((qs) => qs.filter((_, i) => i !== index).map((q, i) => ({ ...q, order: i + 1 })));
  };

  const addOption = (qIndex: number) => {
    updateQuestion(qIndex, {
      options: [...questions[qIndex].options, { value: '', label: '' }],
    });
  };

  const updateOption = (qIndex: number, oIndex: number, patch: Partial<QuestionOption>) => {
    const opts = questions[qIndex].options.map((o, i) => (i === oIndex ? { ...o, ...patch } : o));
    updateQuestion(qIndex, { options: opts });
  };

  const removeOption = (qIndex: number, oIndex: number) => {
    updateQuestion(qIndex, { options: questions[qIndex].options.filter((_, i) => i !== oIndex) });
  };

  const addLogicRule = () => {
    setLogicRules((rs) => [...rs, { if: { question_key: '', answer: '' }, then: { hide: [] } }]);
  };

  const updateLogicRule = (index: number, patch: Partial<LogicRule>) => {
    setLogicRules((rs) => rs.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  };

  const removeLogicRule = (index: number) => {
    setLogicRules((rs) => rs.filter((_, i) => i !== index));
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      await axios.post(
        `${API}/buyer-leads/tenants/${tenantId}/forms/${formId}/versions`,
        { questions, logic_rules: logicRules }
      );
      success('New version published');
      navigate(`/buyer-leads/${tenantId}/forms`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Failed to publish version');
    } finally {
      setPublishing(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate(`/buyer-leads/${tenantId}/forms`)}
            className="text-sm text-blue-600 hover:text-blue-800 mb-1"
          >
            ← Back to Forms
          </button>
          <h2 className="text-lg font-semibold text-gray-700">{templateName}</h2>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowPreview((v) => !v)}
            className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md hover:bg-gray-50"
          >
            {showPreview ? 'Hide Preview' : 'JSON Preview'}
          </button>
          <button
            onClick={handlePublish}
            disabled={publishing || questions.length === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
          >
            {publishing ? 'Publishing…' : 'Publish Version'}
          </button>
        </div>
      </div>

      {showPreview && (
        <pre className="bg-gray-900 text-green-400 text-xs p-4 rounded-lg overflow-auto max-h-64">
          {JSON.stringify({ questions, logic_rules: logicRules }, null, 2)}
        </pre>
      )}

      {/* Questions */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Questions</h3>
          <button
            onClick={addQuestion}
            className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-md"
          >
            + Add Question
          </button>
        </div>

        {questions.map((q, qi) => (
          <div
            key={qi}
            draggable
            onDragStart={() => handleDragStart(qi)}
            onDragOver={(e) => handleDragOver(e, qi)}
            onDragEnd={handleDragEnd}
            className={`bg-white rounded-lg shadow p-4 space-y-3 cursor-grab ${dragIndex === qi ? 'opacity-50' : ''}`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400 font-medium">Q{q.order} ⠿</span>
              <button onClick={() => removeQuestion(qi)} className="text-red-400 hover:text-red-600 text-xs">
                Remove
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Question Key</label>
                <input
                  type="text"
                  value={q.question_key}
                  onChange={(e) => updateQuestion(qi, { question_key: e.target.value })}
                  placeholder="e.g. timeline"
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Type</label>
                <select
                  value={q.type}
                  onChange={(e) => updateQuestion(qi, { type: e.target.value as Question['type'] })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {QUESTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Label</label>
              <input
                type="text"
                value={q.label}
                onChange={(e) => updateQuestion(qi, { label: e.target.value })}
                placeholder="Question text shown to the lead"
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={q.required}
                onChange={(e) => updateQuestion(qi, { required: e.target.checked })}
                className="rounded"
              />
              Required
            </label>

            {(q.type === 'single_choice' || q.type === 'multi_select') && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Options</span>
                  <button onClick={() => addOption(qi)} className="text-xs text-blue-600 hover:text-blue-800">
                    + Add Option
                  </button>
                </div>
                {q.options.map((opt, oi) => (
                  <div key={oi} className="flex gap-2 items-center">
                    <input
                      type="text"
                      value={opt.value}
                      onChange={(e) => updateOption(qi, oi, { value: e.target.value })}
                      placeholder="value"
                      className="flex-1 px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <input
                      type="text"
                      value={opt.label}
                      onChange={(e) => updateOption(qi, oi, { label: e.target.value })}
                      placeholder="label"
                      className="flex-1 px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <button onClick={() => removeOption(qi, oi)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Logic Rules */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Conditional Logic Rules</h3>
          <button
            onClick={addLogicRule}
            className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-md"
          >
            + Add Rule
          </button>
        </div>

        {logicRules.map((rule, ri) => (
          <div key={ri} className="bg-white rounded-lg shadow p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500 font-medium">Rule {ri + 1}</span>
              <button onClick={() => removeLogicRule(ri)} className="text-red-400 hover:text-red-600 text-xs">Remove</button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">If question_key</label>
                <input
                  type="text"
                  value={rule.if.question_key}
                  onChange={(e) => updateLogicRule(ri, { if: { ...rule.if, question_key: e.target.value } })}
                  placeholder="e.g. has_agent"
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">equals answer</label>
                <input
                  type="text"
                  value={rule.if.answer}
                  onChange={(e) => updateLogicRule(ri, { if: { ...rule.if, answer: e.target.value } })}
                  placeholder="e.g. yes"
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Then hide (comma-separated question keys)</label>
              <input
                type="text"
                value={rule.then.hide.join(', ')}
                onChange={(e) =>
                  updateLogicRule(ri, {
                    then: { hide: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) },
                  })
                }
                placeholder="e.g. wants_tour, areas"
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
