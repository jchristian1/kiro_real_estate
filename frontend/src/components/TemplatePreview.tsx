import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useT } from '../utils/useT';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface PreviewResult { subject: string; body: string; }

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
      <div style={{ ...t.sectionTitle, marginBottom: 12 }}>Preview (with sample data)</div>
      {loading && <p style={{ fontSize: 13, color: t.textMuted }} data-testid="preview-loading">Loading preview…</p>}
      {error && <p style={{ fontSize: 13, color: t.red }} role="alert" data-testid="preview-error">{error}</p>}
      {preview && !loading && (
        <div data-testid="preview-content">
          <div style={{ marginBottom: 12 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Subject</span>
            <p style={{ marginTop: 6, fontSize: 13, color: t.text, background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px' }} data-testid="preview-subject">{preview.subject}</p>
          </div>
          <div>
            <span style={{ fontSize: 10, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Body</span>
            <pre style={{ marginTop: 6, fontSize: 12, color: t.text, background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px', whiteSpace: 'pre-wrap', fontFamily: 'inherit' }} data-testid="preview-body">{preview.body}</pre>
          </div>
        </div>
      )}
      {!loading && !error && !preview && (
        <p style={{ fontSize: 13, color: t.textFaint }} data-testid="preview-empty">Enter subject and body to see preview</p>
      )}
    </div>
  );
};
