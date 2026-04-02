import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useT } from '@/shared/hooks';
import { PreviewResult } from '@/models/app-model';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

export interface TemplatePreviewProps { subject: string; body: string; }

export const TemplatePreview: React.FC<TemplatePreviewProps> = ({ subject, body }) => {
  const t = useT();
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPreview = useCallback(async () => {
    if (!subject.trim() || !body.trim()) { setPreview(null); return; }
    setLoading(true); setError(null);
    try {
      const res = await axios.post<PreviewResult>(`${API_BASE_URL}/templates/preview`, { subject, body });
      setPreview(res.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string; message?: string } } };
      setError(e.response?.data?.detail || e.response?.data?.message || 'Preview failed');
      setPreview(null);
    } finally { setLoading(false); }
  }, [subject, body]);

  useEffect(() => {
    const timer = setTimeout(fetchPreview, 500);
    return () => clearTimeout(timer);
  }, [fetchPreview]);

  return (
    <div style={{ ...t.card, background: t.bgInput }} data-testid="template-preview">
      <div className={styles.sectionTitle} style={t.sectionTitle}>Preview (with sample data)</div>
      {loading && <p className={styles.statusText} style={{ color: t.textMuted }} data-testid="preview-loading">Loading preview…</p>}
      {error && <p className={styles.statusText} style={{ color: t.red }} role="alert" data-testid="preview-error">{error}</p>}
      {preview && !loading && (
        <div data-testid="preview-content">
          <div className={styles.subjectSection}>
            <span className={styles.sectionLabel} style={{ color: t.textFaint }}>Subject</span>
            <p className={styles.previewSubject} style={{ color: t.text, background: t.bgCard, border: `1px solid ${t.border}` }} data-testid="preview-subject">{preview.subject}</p>
          </div>
          <div>
            <span className={styles.sectionLabel} style={{ color: t.textFaint }}>Body</span>
            <pre className={styles.previewBody} style={{ color: t.text, background: t.bgCard, border: `1px solid ${t.border}` }} data-testid="preview-body">{preview.body}</pre>
          </div>
        </div>
      )}
      {!loading && !error && !preview && (
        <p className={styles.statusText} style={{ color: t.textFaint }} data-testid="preview-empty">Enter subject and body to see preview</p>
      )}
    </div>
  );
};
