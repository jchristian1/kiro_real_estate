import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';
import { useT } from '../../utils/useT';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const SUPPORTED_VARS = ['lead_name','agent_name','property_address','form_url','score','bucket','tenant_name'];
const BUCKETS = ['HOT', 'WARM', 'NURTURE'] as const;
type Bucket = typeof BUCKETS[number];
interface BucketVariant { subject: string; body: string; }
type Variants = Partial<Record<Bucket, BucketVariant>>;
interface PreviewResult { subject: string; body: string; }
const KEY_LABELS: Record<string, string> = { INITIAL_INVITE_EMAIL: 'Initial Invite Email', POST_SUBMISSION_EMAIL: 'Post-Submission Email' };

export const TemplateVersionEditor: React.FC = () => {
  const { tenantId, templateId } = useParams<{ tenantId: string; templateId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();
  const t = useT();

  const [templateKey, setTemplateKey] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [variants, setVariants] = useState<Variants>({});
  const [hasVariants, setHasVariants] = useState(false);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [previewBucket, setPreviewBucket] = useState<Bucket>('HOT');
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const sampleContext = { lead_name: 'Jane Smith', agent_name: 'John Agent', property_address: '123 Main St', form_url: 'https://example.com/form/abc123', score: '85', bucket: previewBucket, tenant_name: 'Acme Realty' };

  const fetchTemplate = useCallback(async () => {
    setLoading(true);
    try {
      const [tmplRes, versRes] = await Promise.all([
        axios.get(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}`),
        axios.get(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/versions`),
      ]);
      setTemplateKey(tmplRes.data.key);
      setHasVariants(tmplRes.data.key === 'POST_SUBMISSION_EMAIL');
      const active = (versRes.data as { is_active: boolean; subject_template: string; body_template: string; variants_json?: string }[]).find(v => v.is_active);
      if (active) {
        setSubject(active.subject_template); setBody(active.body_template);
        if (active.variants_json) setVariants(JSON.parse(active.variants_json) as Variants);
      }
    } catch { toastError('Failed to load template'); } finally { setLoading(false); }
  }, [tenantId, templateId]);

  useEffect(() => { fetchTemplate(); }, [fetchTemplate]);

  const insertVar = (varName: string, field: 'subject' | 'body') => {
    const token = `{{${varName}}}`;
    if (field === 'subject') setSubject(s => s + token);
    else setBody(b => b + token);
  };

  const insertVarInVariant = (bucket: Bucket, varName: string, field: 'subject' | 'body') => {
    const token = `{{${varName}}}`;
    setVariants(vs => ({ ...vs, [bucket]: { subject: vs[bucket]?.subject ?? '', body: vs[bucket]?.body ?? '', [field]: (vs[bucket]?.[field] ?? '') + token } }));
  };

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      const res = await axios.post<PreviewResult>(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/preview`, {
        subject_template: hasVariants ? (variants[previewBucket]?.subject ?? subject) : subject,
        body_template: hasVariants ? (variants[previewBucket]?.body ?? body) : body,
        context: sampleContext,
      });
      setPreviewResult(res.data);
    } catch { toastError('Preview failed'); } finally { setPreviewing(false); }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/versions`, {
        subject_template: subject, body_template: body,
        variants_json: hasVariants ? JSON.stringify(variants) : undefined,
      });
      success('Template version published'); navigate('/templates');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Failed to publish template version');
    } finally { setPublishing(false); }
  };

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>;

  const varBtn: React.CSSProperties = { padding: '2px 8px', background: t.accentBg, color: t.accent, border: 'none', borderRadius: 6, fontSize: 11, cursor: 'pointer', fontFamily: 'monospace' };
  const bucketColors: Record<Bucket, { bg: string; color: string }> = {
    HOT: { bg: t.redBg, color: t.red },
    WARM: { bg: t.orangeBg, color: t.orange },
    NURTURE: { bg: t.accentBg, color: t.accent },
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <button onClick={() => navigate('/templates')} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, marginBottom: 6, padding: 0 }}>← Back to Templates</button>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: t.text, margin: 0 }}>{KEY_LABELS[templateKey] ?? templateKey}</h2>
        </div>
        <button onClick={handlePublish} disabled={publishing} style={{ ...t.btnPrimary, opacity: publishing ? 0.6 : 1 }}>
          {publishing ? 'Publishing…' : 'Publish Version'}
        </button>
      </div>

      {/* Variable picker */}
      <div style={t.card}>
        <div style={t.sectionTitle}>Available Variables</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {SUPPORTED_VARS.map(v => (
            <span key={v} style={{ padding: '3px 10px', background: t.bgBadge, color: t.textSecondary, fontSize: 11, borderRadius: 6, fontFamily: 'monospace' }}>{`{{${v}}}`}</span>
          ))}
        </div>
      </div>

      {!hasVariants ? (
        <div style={{ ...t.card, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={t.labelStyle}>Subject</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
              {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVar(v, 'subject')} style={varBtn}>+{v}</button>)}
            </div>
            <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} style={t.input} />
          </div>
          <div>
            <label style={t.labelStyle}>Body</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
              {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVar(v, 'body')} style={varBtn}>+{v}</button>)}
            </div>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8}
              style={{ ...t.input, fontFamily: 'monospace', resize: 'vertical' }} />
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {BUCKETS.map((bucket) => (
            <div key={bucket} style={{ ...t.card, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ padding: '2px 10px', fontSize: 11, fontWeight: 700, background: bucketColors[bucket].bg, color: bucketColors[bucket].color, borderRadius: 20 }}>{bucket}</span>
                <span style={{ fontSize: 13, fontWeight: 500, color: t.textSecondary }}>Variant</span>
              </div>
              <div>
                <label style={t.labelStyle}>Subject</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                  {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVarInVariant(bucket, v, 'subject')} style={varBtn}>+{v}</button>)}
                </div>
                <input type="text" value={variants[bucket]?.subject ?? ''} onChange={(e) => setVariants(vs => ({ ...vs, [bucket]: { subject: e.target.value, body: vs[bucket]?.body ?? '' } }))} style={t.input} />
              </div>
              <div>
                <label style={t.labelStyle}>Body</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                  {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVarInVariant(bucket, v, 'body')} style={varBtn}>+{v}</button>)}
                </div>
                <textarea value={variants[bucket]?.body ?? ''} onChange={(e) => setVariants(vs => ({ ...vs, [bucket]: { subject: vs[bucket]?.subject ?? '', body: e.target.value } }))} rows={6}
                  style={{ ...t.input, fontFamily: 'monospace', resize: 'vertical' }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Live preview */}
      <div style={t.card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={t.sectionTitle}>Live Preview</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {hasVariants && (
              <select value={previewBucket} onChange={(e) => setPreviewBucket(e.target.value as Bucket)} style={{ ...t.input, width: 'auto' }}>
                {BUCKETS.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            )}
            <button onClick={handlePreview} disabled={previewing} style={{ ...t.btnSecondary, opacity: previewing ? 0.6 : 1 }}>
              {previewing ? 'Rendering…' : 'Preview'}
            </button>
          </div>
        </div>
        {previewResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <p style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', marginBottom: 4 }}>Subject</p>
              <p style={{ fontSize: 13, color: t.text, background: t.bgInput, padding: '8px 12px', borderRadius: 8, margin: 0 }}>{previewResult.subject}</p>
            </div>
            <div>
              <p style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', marginBottom: 4 }}>Body</p>
              <pre style={{ fontSize: 12, color: t.text, background: t.bgInput, padding: '8px 12px', borderRadius: 8, margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{previewResult.body}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
