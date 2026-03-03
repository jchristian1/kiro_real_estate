/**
 * TemplatePreview Component
 * Requirements: 3.3, 13.3
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface PreviewResult {
  subject: string;
  body: string;
}

export interface TemplatePreviewProps {
  subject: string;
  body: string;
}

export const TemplatePreview: React.FC<TemplatePreviewProps> = ({ subject, body }) => {
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPreview = useCallback(async () => {
    if (!subject.trim() || !body.trim()) {
      setPreview(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post<PreviewResult>(`${API_BASE_URL}/templates/preview`, { subject, body });
      setPreview(res.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string; message?: string } } };
      setError(e.response?.data?.detail || e.response?.data?.message || 'Preview failed');
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [subject, body]);

  useEffect(() => {
    const timer = setTimeout(fetchPreview, 500);
    return () => clearTimeout(timer);
  }, [fetchPreview]);

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50" data-testid="template-preview">
      <h3 className="text-sm font-medium text-gray-700 mb-3">Preview (with sample data)</h3>
      {loading && <p className="text-sm text-gray-500" data-testid="preview-loading">Loading preview...</p>}
      {error && <p className="text-sm text-red-600" role="alert" data-testid="preview-error">{error}</p>}
      {preview && !loading && (
        <div data-testid="preview-content">
          <div className="mb-2">
            <span className="text-xs font-medium text-gray-500 uppercase">Subject</span>
            <p className="mt-1 text-sm text-gray-900 bg-white border border-gray-200 rounded px-3 py-2" data-testid="preview-subject">{preview.subject}</p>
          </div>
          <div>
            <span className="text-xs font-medium text-gray-500 uppercase">Body</span>
            <pre className="mt-1 text-sm text-gray-900 bg-white border border-gray-200 rounded px-3 py-2 whitespace-pre-wrap font-sans" data-testid="preview-body">{preview.body}</pre>
          </div>
        </div>
      )}
      {!loading && !error && !preview && (
        <p className="text-sm text-gray-400" data-testid="preview-empty">Enter subject and body to see preview</p>
      )}
    </div>
  );
};
