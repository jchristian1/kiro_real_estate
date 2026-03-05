/**
 * BuyerFormTab — list form templates, publish versions, rollback.
 * Requirements: 11.1, 11.2, 11.5
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface FormTemplate {
  id: number;
  name: string;
  status: string;
  intent_type: string;
  created_at: string;
}

interface FormVersion {
  id: number;
  version_number: number;
  is_active: boolean;
  published_at: string | null;
}

export const BuyerFormTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();

  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  // Version panel state
  const [selectedTemplate, setSelectedTemplate] = useState<FormTemplate | null>(null);
  const [versions, setVersions] = useState<FormVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<FormTemplate[]>(
        `${API}/buyer-leads/tenants/${tenantId}/forms`
      );
      setTemplates(res.data);
    } catch {
      toastError('Failed to load form templates');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const fetchVersions = async (template: FormTemplate) => {
    setSelectedTemplate(template);
    setVersionsLoading(true);
    try {
      const res = await axios.get<FormVersion[]>(
        `${API}/buyer-leads/tenants/${tenantId}/forms/${template.id}/versions`
      );
      setVersions(res.data);
    } catch {
      toastError('Failed to load versions');
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/forms`, {
        name: newName.trim(),
        intent_type: 'BUY',
      });
      success('Form template created');
      setNewName('');
      setShowCreate(false);
      fetchTemplates();
    } catch {
      toastError('Failed to create form template');
    } finally {
      setCreating(false);
    }
  };

  const handleRollback = async (templateId: number, versionId: number) => {
    try {
      await axios.post(
        `${API}/buyer-leads/tenants/${tenantId}/forms/${templateId}/versions/${versionId}/rollback`
      );
      success('Rolled back to version');
      if (selectedTemplate) fetchVersions(selectedTemplate);
    } catch {
      toastError('Rollback failed');
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      active: 'bg-green-100 text-green-800',
      draft: 'bg-yellow-100 text-yellow-800',
      archived: 'bg-gray-100 text-gray-600',
    };
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${colors[status] ?? 'bg-gray-100 text-gray-600'}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-700">Buyer Qualification Forms</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md"
        >
          New Form Template
        </button>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-lg font-semibold">New Form Template</h3>
            <input
              type="text"
              placeholder="Template name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
              >
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Templates list */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-500">Loading…</div>
          ) : templates.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No form templates yet</div>
          ) : (
            <table className="min-w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {templates.map((t) => (
                  <tr
                    key={t.id}
                    className={`hover:bg-gray-50 cursor-pointer ${selectedTemplate?.id === t.id ? 'bg-blue-50' : ''}`}
                    onClick={() => fetchVersions(t)}
                  >
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{t.name}</td>
                    <td className="px-4 py-3">{statusBadge(t.status)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/buyer-leads/${tenantId}/forms/${t.id}`); }}
                        className="text-blue-600 hover:text-blue-800 text-xs"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Version panel */}
        {selectedTemplate && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <p className="text-sm font-semibold text-gray-700">
                Versions — {selectedTemplate.name}
              </p>
            </div>
            {versionsLoading ? (
              <div className="p-6 text-center text-gray-500">Loading…</div>
            ) : versions.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No versions published yet</div>
            ) : (
              <table className="min-w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Version</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Published</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Active</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {versions.map((v) => (
                    <tr key={v.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900">v{v.version_number}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {v.published_at ? new Date(v.published_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {v.is_active && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">Active</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {!v.is_active && (
                          <button
                            onClick={() => handleRollback(selectedTemplate.id, v.id)}
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
