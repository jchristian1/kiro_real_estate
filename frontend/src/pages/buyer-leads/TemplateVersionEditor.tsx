/**
 * TemplateVersionEditor — variable picker, live preview, per-bucket variant editor.
 * Requirements: 13.2, 13.3, 13.4
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const SUPPORTED_VARS = [
  'lead_name',
  'agent_name',
  'property_address',
  'form_url',
  'score',
  'bucket',
  'tenant_name',
];

const BUCKETS = ['HOT', 'WARM', 'NURTURE'] as const;
type Bucket = typeof BUCKETS[number];

interface BucketVariant { subject: string; body: string; }
type Variants = Partial<Record<Bucket, BucketVariant>>;

interface PreviewResult { subject: string; body: string; }

const KEY_LABELS: Record<string, string> = {
  INITIAL_INVITE_EMAIL: 'Initial Invite Email',
  POST_SUBMISSION_EMAIL: 'Post-Submission Email',
};

export const TemplateVersionEditor: React.FC = () => {
  const { tenantId, templateId } = useParams<{ tenantId: string; templateId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();

  const [templateKey, setTemplateKey] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [variants, setVariants] = useState<Variants>({});
  const [hasVariants, setHasVariants] = useState(false);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);

  // Preview state
  const [previewBucket, setPreviewBucket] = useState<Bucket>('HOT');
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);
  const [previewing, setPreviewing] = useState(false);

  // Sample context for preview
  const sampleContext = {
    lead_name: 'Jane Smith',
    agent_name: 'John Agent',
    property_address: '123 Main St',
    form_url: 'https://example.com/form/abc123',
    score: '85',
    bucket: previewBucket,
    tenant_name: 'Acme Realty',
  };

  const fetchTemplate = useCallback(async () => {
    setLoading(true);
    try {
      const [tmplRes, versRes] = await Promise.all([
        axios.get(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}`),
        axios.get(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/versions`),
      ]);
      setTemplateKey(tmplRes.data.key);
      const isPostSubmission = tmplRes.data.key === 'POST_SUBMISSION_EMAIL';
      setHasVariants(isPostSubmission);

      const active = (versRes.data as { is_active: boolean; subject_template: string; body_template: string; variants_json?: string }[])
        .find((v) => v.is_active);
      if (active) {
        setSubject(active.subject_template);
        setBody(active.body_template);
        if (active.variants_json) {
          setVariants(JSON.parse(active.variants_json) as Variants);
        }
      }
    } catch {
      toastError('Failed to load template');
    } finally {
      setLoading(false);
    }
  }, [tenantId, templateId]);

  useEffect(() => { fetchTemplate(); }, [fetchTemplate]);

  const insertVar = (varName: string, field: 'subject' | 'body') => {
    const token = `{{${varName}}}`;
    if (field === 'subject') setSubject((s) => s + token);
    else setBody((b) => b + token);
  };

  const insertVarInVariant = (bucket: Bucket, varName: string, field: 'subject' | 'body') => {
    const token = `{{${varName}}}`;
    setVariants((vs) => ({
      ...vs,
      [bucket]: {
        subject: vs[bucket]?.subject ?? '',
        body: vs[bucket]?.body ?? '',
        [field]: (vs[bucket]?.[field] ?? '') + token,
      },
    }));
  };

  const updateVariant = (bucket: Bucket, field: 'subject' | 'body', value: string) => {
    setVariants((vs) => ({
      ...vs,
      [bucket]: { subject: vs[bucket]?.subject ?? '', body: vs[bucket]?.body ?? '', [field]: value },
    }));
  };

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      const res = await axios.post<PreviewResult>(
        `${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/preview`,
        {
          subject_template: hasVariants ? (variants[previewBucket]?.subject ?? subject) : subject,
          body_template: hasVariants ? (variants[previewBucket]?.body ?? body) : body,
          context: sampleContext,
        }
      );
      setPreviewResult(res.data);
    } catch {
      toastError('Preview failed');
    } finally {
      setPreviewing(false);
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      await axios.post(
        `${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/versions`,
        {
          subject_template: subject,
          body_template: body,
          variants_json: hasVariants ? JSON.stringify(variants) : undefined,
        }
      );
      success('Template version published');
      navigate(`/templates`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Failed to publish template version');
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
            onClick={() => navigate(`/templates`)}
            className="text-sm text-blue-600 hover:text-blue-800 mb-1"
          >
            ← Back to Templates
          </button>
          <h2 className="text-lg font-semibold text-gray-700">
            {KEY_LABELS[templateKey] ?? templateKey}
          </h2>
        </div>
        <button
          onClick={handlePublish}
          disabled={publishing}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
        >
          {publishing ? 'Publishing…' : 'Publish Version'}
        </button>
      </div>

      {/* Variable picker */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">Available Variables</h3>
        <div className="flex flex-wrap gap-2">
          {SUPPORTED_VARS.map((v) => (
            <span
              key={v}
              className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded font-mono cursor-default"
              title={`Click to insert into subject or body`}
            >
              {`{{${v}}}`}
            </span>
          ))}
        </div>
      </div>

      {!hasVariants ? (
        /* Default template editor */
        <div className="bg-white rounded-lg shadow p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Subject</label>
            <div className="flex gap-2 mb-1 flex-wrap">
              {SUPPORTED_VARS.map((v) => (
                <button key={v} onClick={() => insertVar(v, 'subject')}
                  className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-xs rounded hover:bg-blue-100">
                  +{v}
                </button>
              ))}
            </div>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Body</label>
            <div className="flex gap-2 mb-1 flex-wrap">
              {SUPPORTED_VARS.map((v) => (
                <button key={v} onClick={() => insertVar(v, 'body')}
                  className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-xs rounded hover:bg-blue-100">
                  +{v}
                </button>
              ))}
            </div>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      ) : (
        /* Per-bucket variant editor */
        <div className="space-y-4">
          {BUCKETS.map((bucket) => (
            <div key={bucket} className="bg-white rounded-lg shadow p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                  bucket === 'HOT' ? 'bg-red-100 text-red-700' :
                  bucket === 'WARM' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-blue-100 text-blue-700'
                }`}>{bucket}</span>
                <span className="text-sm font-medium text-gray-600">Variant</span>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Subject</label>
                <div className="flex gap-1 mb-1 flex-wrap">
                  {SUPPORTED_VARS.map((v) => (
                    <button key={v} onClick={() => insertVarInVariant(bucket, v, 'subject')}
                      className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-xs rounded hover:bg-blue-100">
                      +{v}
                    </button>
                  ))}
                </div>
                <input
                  type="text"
                  value={variants[bucket]?.subject ?? ''}
                  onChange={(e) => updateVariant(bucket, 'subject', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Body</label>
                <div className="flex gap-1 mb-1 flex-wrap">
                  {SUPPORTED_VARS.map((v) => (
                    <button key={v} onClick={() => insertVarInVariant(bucket, v, 'body')}
                      className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-xs rounded hover:bg-blue-100">
                      +{v}
                    </button>
                  ))}
                </div>
                <textarea
                  value={variants[bucket]?.body ?? ''}
                  onChange={(e) => updateVariant(bucket, 'body', e.target.value)}
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Live preview */}
      <div className="bg-white rounded-lg shadow p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Live Preview</h3>
          <div className="flex items-center gap-3">
            {hasVariants && (
              <select
                value={previewBucket}
                onChange={(e) => setPreviewBucket(e.target.value as Bucket)}
                className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {BUCKETS.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            )}
            <button
              onClick={handlePreview}
              disabled={previewing}
              className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-md disabled:opacity-50"
            >
              {previewing ? 'Rendering…' : 'Preview'}
            </button>
          </div>
        </div>
        {previewResult && (
          <div className="space-y-2">
            <div>
              <p className="text-xs text-gray-400 uppercase mb-1">Subject</p>
              <p className="text-sm text-gray-800 bg-gray-50 px-3 py-2 rounded">{previewResult.subject}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase mb-1">Body</p>
              <pre className="text-sm text-gray-800 bg-gray-50 px-3 py-2 rounded whitespace-pre-wrap font-sans">
                {previewResult.body}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
