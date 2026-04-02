import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '@/shared/contexts/ToastContext';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

const SUPPORTED_VARS = ['lead_name', 'agent_name', 'property_address', 'form_url', 'score', 'bucket', 'tenant_name'];
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
        axios.get(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}`),
        axios.get(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/versions`),
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
      const res = await axios.post<PreviewResult>(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/preview`, {
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
      await axios.post(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${templateId}/versions`, {
        subject_template: subject, body_template: body,
        variants_json: hasVariants ? JSON.stringify(variants) : undefined,
      });
      success('Template version published'); navigate('/templates');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Failed to publish template version');
    } finally { setPublishing(false); }
  };

  if (loading) return <div className={styles.loadingState} style={{ color: t.textMuted }}>Loading…</div>;

  const bucketColors: Record<Bucket, { bg: string; color: string }> = {
    HOT: { bg: t.redBg, color: t.red },
    WARM: { bg: t.orangeBg, color: t.orange },
    NURTURE: { bg: t.accentBg, color: t.accent },
  };

  return (
    <div className={styles.container}>
      <div className={styles.headerRow}>
        <div>
          <button onClick={() => navigate('/templates')} className={styles.backButton} style={{ color: t.accent }}>← Back to Templates</button>
          <h2 className={styles.pageTitle} style={{ color: t.text }}>{KEY_LABELS[templateKey] ?? templateKey}</h2>
        </div>
        <button onClick={handlePublish} disabled={publishing} style={{ ...t.btnPrimary, opacity: publishing ? 0.6 : 1 }}>
          {publishing ? 'Publishing…' : 'Publish Version'}
        </button>
      </div>

      <div style={t.card}>
        <div style={t.sectionTitle}>Available Variables</div>
        <div className={styles.variablesRow}>
          {SUPPORTED_VARS.map(v => (
            <span key={v} className={styles.variableTag} style={{ background: t.bgBadge, color: t.textSecondary }}>{`{{${v}}}`}</span>
          ))}
        </div>
      </div>

      {!hasVariants ? (
        <div style={t.card} className={styles.editorCard}>
          <div>
            <label style={t.labelStyle}>Subject</label>
            <div className={styles.varButtonsRow}>
              {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVar(v, 'subject')} className={styles.varButton} style={{ background: t.accentBg, color: t.accent }}>+{v}</button>)}
            </div>
            <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} style={t.input} />
          </div>
          <div>
            <label style={t.labelStyle}>Body</label>
            <div className={styles.varButtonsRow}>
              {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVar(v, 'body')} className={styles.varButton} style={{ background: t.accentBg, color: t.accent }}>+{v}</button>)}
            </div>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8}
              style={{ ...t.input }} className={styles.textarea} />
          </div>
        </div>
      ) : (
        <div className={styles.variantsContainer}>
          {BUCKETS.map((bucket) => (
            <div key={bucket} style={t.card} className={styles.variantCard}>
              <div className={styles.bucketHeader}>
                <span className={styles.bucketBadge} style={{ background: bucketColors[bucket].bg, color: bucketColors[bucket].color }}>{bucket}</span>
                <span className={styles.bucketLabel} style={{ color: t.textSecondary }}>Variant</span>
              </div>
              <div>
                <label style={t.labelStyle}>Subject</label>
                <div className={styles.varButtonsRow}>
                  {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVarInVariant(bucket, v, 'subject')} className={styles.varButton} style={{ background: t.accentBg, color: t.accent }}>+{v}</button>)}
                </div>
                <input type="text" value={variants[bucket]?.subject ?? ''} onChange={(e) => setVariants(vs => ({ ...vs, [bucket]: { subject: e.target.value, body: vs[bucket]?.body ?? '' } }))} style={t.input} />
              </div>
              <div>
                <label style={t.labelStyle}>Body</label>
                <div className={styles.varButtonsRow}>
                  {SUPPORTED_VARS.map(v => <button key={v} onClick={() => insertVarInVariant(bucket, v, 'body')} className={styles.varButton} style={{ background: t.accentBg, color: t.accent }}>+{v}</button>)}
                </div>
                <textarea value={variants[bucket]?.body ?? ''} onChange={(e) => setVariants(vs => ({ ...vs, [bucket]: { subject: vs[bucket]?.subject ?? '', body: e.target.value } }))} rows={6}
                  style={{ ...t.input }} className={styles.textarea} />
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={t.card}>
        <div className={styles.previewHeader}>
          <div style={t.sectionTitle}>Live Preview</div>
          <div className={styles.previewActions}>
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
          <div className={styles.previewContent}>
            <div>
              <p className={styles.previewLabel} style={{ color: t.textFaint }}>Subject</p>
              <p className={styles.previewSubject} style={{ color: t.text, background: t.bgInput }}>{previewResult.subject}</p>
            </div>
            <div>
              <p className={styles.previewLabel} style={{ color: t.textFaint }}>Body</p>
              <pre className={styles.previewBody} style={{ color: t.text, background: t.bgInput }}>{previewResult.body}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
