/**
 * EmailTemplatesTab — list email templates with create/delete, version history with rollback.
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

const KEY_OPTIONS = ['INITIAL_INVITE_EMAIL', 'POST_SUBMISSION_EMAIL'];

const KEY_LABELS: Record<string, string> = {
  INITIAL_INVITE_EMAIL: 'Initial Invite Email',
  POST_SUBMISSION_EMAIL: 'Post-Submission Email',
};

export const EmailTemplatesTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();

  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<MessageTemplate | null>(null);
  const [versions, setVersions] = useState<MessageTemplateVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState(KEY_OPTIONS[0]);
  const [creating, setCreating] = useState(false);

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

  const handleCreate = async () => {
    setCreating(true);
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/message-templates`, {
        key: newKey,
        intent_type: 'BUY',
      });
      success('Template created');
      setShowCreate(false);
      fetchTemplates();
    } catch {
      toastError('Failed to create template');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (t: MessageTemplate) => {
    if (!confirm(`Delete "${KEY_LABELS[t.key] ?? t.key}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${t.id}`);
      success('Deleted');
      if (selectedTemplate?.id === t.id) { setSelectedTemplate(null); setVersions([]); }
      fetchTemplates();
    } catch {
      toastError('Delete failed');
    }
  };

  const handleRollback = async (vid: number) => {
    if (!selectedTemplate) return;
    try {
      await axios.post(
        `${API}/buyer-leads/tenants/${tenantId}/message-templates/${selectedTemplate.id}/versions/${vid}/rollback`
      );
      success('Rolled back');
      fetchVersions(selectedTemplate);
    } catch {
      toastError('Rollback failed');
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-700">Email Templates</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md"
        >
          New Template
        </button>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-lg font-semibold">New Email Template</h3>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Template Type</label>
              <select
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {KEY_OPTIONS.map((k) => (
                  <option key={k} value={k}>{KEY_LABELS[k] ?? k}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
              <button
                onClick={handleCreate}
                disabled={creating}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
              >
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Template list */}
        <div className="space-y-3">
          {templates.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              No templates found. Run the seed script or create one above.
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
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(`/buyer-leads/${tenantId}/templates/${t.id}`); }}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-md"
                    >
                      Edit
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(t); }}
                      className="px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 text-xs font-medium rounded-md"
                    >
                      Delete
                    </button>
                  </div>
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
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
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
                      <td className="px-4 py-2 text-right">
                        {!v.is_active && (
                          <button
                            onClick={() => handleRollback(v.id)}
                            className="text-blue-600 hover:text-blue-800 text-xs"
                          >
                            Rollback
                          </button>
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
