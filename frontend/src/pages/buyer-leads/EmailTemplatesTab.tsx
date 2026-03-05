/**
 * EmailTemplatesTab — list INITIAL_INVITE_EMAIL and POST_SUBMISSION_EMAIL templates.
 * Requirements: 13.1
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface MessageTemplate {
  id: number;
  key: string;
  intent_type: string;
  created_at: string;
}

interface MessageTemplateVersion {
  id: number;
  version_number: number;
  is_active: boolean;
  published_at: string | null;
  subject_template: string;
}

const KEY_LABELS: Record<string, string> = {
  INITIAL_INVITE_EMAIL: 'Initial Invite Email',
  POST_SUBMISSION_EMAIL: 'Post-Submission Email',
};

export const EmailTemplatesTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const { error: toastError } = useToast();

  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<MessageTemplate | null>(null);
  const [versions, setVersions] = useState<MessageTemplateVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<MessageTemplate[]>(
        `${API}/buyer-leads/tenants/${tenantId}/message-templates`
      );
      setTemplates(res.data);
    } catch {
      toastError('Failed to load message templates');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const fetchVersions = async (template: MessageTemplate) => {
    setSelectedTemplate(template);
    setVersionsLoading(true);
    try {
      const res = await axios.get<MessageTemplateVersion[]>(
        `${API}/buyer-leads/tenants/${tenantId}/message-templates/${template.id}/versions`
      );
      setVersions(res.data);
    } catch {
      toastError('Failed to load template versions');
    } finally {
      setVersionsLoading(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading…</div>;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-700">Email Templates</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Template list */}
        <div className="space-y-3">
          {templates.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              No templates found. Run the seed script to create defaults.
            </div>
          ) : (
            templates.map((t) => (
              <div
                key={t.id}
                onClick={() => fetchVersions(t)}
                className={`bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-md transition-shadow ${
                  selectedTemplate?.id === t.id ? 'ring-2 ring-blue-500' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">
                      {KEY_LABELS[t.key] ?? t.key}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">{t.key}</p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/buyer-leads/${tenantId}/templates/${t.id}`);
                    }}
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-md"
                  >
                    Edit
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Version panel */}
        {selectedTemplate && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <p className="text-sm font-semibold text-gray-700">
                Versions — {KEY_LABELS[selectedTemplate.key] ?? selectedTemplate.key}
              </p>
            </div>
            {versionsLoading ? (
              <div className="p-6 text-center text-gray-500">Loading…</div>
            ) : versions.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No versions yet</div>
            ) : (
              <table className="min-w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Version</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Subject</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Active</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {versions.map((v) => (
                    <tr key={v.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-sm text-gray-900">v{v.version_number}</td>
                      <td className="px-4 py-2 text-sm text-gray-500 truncate max-w-xs">{v.subject_template}</td>
                      <td className="px-4 py-2">
                        {v.is_active && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">Active</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
