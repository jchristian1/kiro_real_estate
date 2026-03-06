/**
 * Templates Page Component
 * Requirements: 3.1, 3.3, 3.5, 3.6, 3.7, 15.3, 15.5, 15.6
 *
 * Two tabs:
 *  - Auto-Response: legacy per-lead-source email templates
 *  - Qualification Emails: preapproval pipeline message templates (INITIAL_INVITE_EMAIL, POST_SUBMISSION_EMAIL)
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios, { AxiosError } from 'axios';
import { TemplateList, Template } from '../components/TemplateList';
import { TemplateEditor, TemplateFormValues } from '../components/TemplateEditor';
import { TemplatePreview } from '../components/TemplatePreview';
import { TemplateVersionHistory } from '../components/TemplateVersionHistory';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../contexts/ToastContext';
import { useAuth } from '../contexts/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

type View = 'list' | 'create' | 'edit';
type Tab = 'auto-response' | 'qualification';

// ---------------------------------------------------------------------------
// Qualification email types
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Qualification Emails sub-component
// ---------------------------------------------------------------------------
const QualificationEmailsTab: React.FC<{ tenantId: number }> = ({ tenantId }) => {
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();

  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<MessageTemplate | null>(null);
  const [versions, setVersions] = useState<MessageTemplateVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState(KEY_OPTIONS[0]);
  const [creating, setCreating] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<MessageTemplate[]>(
        `${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates`
      );
      setTemplates(res.data);
    } catch {
      toastError('Failed to load qualification email templates');
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
        `${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${template.id}/versions`
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
      await axios.post(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates`, {
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
      await axios.delete(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${t.id}`);
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
        `${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${selectedTemplate.id}/versions/${vid}/rollback`
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
        <div>
          <p className="text-sm text-gray-500">
            These emails are sent automatically during the buyer qualification pipeline.
            Use variables like <code className="bg-gray-100 px-1 rounded text-xs">{'{{lead.first_name}}'}</code>,{' '}
            <code className="bg-gray-100 px-1 rounded text-xs">{'{{form.link}}'}</code>,{' '}
            <code className="bg-gray-100 px-1 rounded text-xs">{'{{tenant.name}}'}</code>.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md"
        >
          New Template
        </button>
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-lg font-semibold">New Qualification Email Template</h3>
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
        <div className="space-y-3">
          {templates.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              No qualification email templates found. Create one above.
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
                    <p className="text-sm font-semibold text-gray-800">{KEY_LABELS[t.key] ?? t.key}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{t.key}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/qualification-templates/${tenantId}/message-templates/${t.id}`);
                      }}
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
              <div className="p-6 text-center text-gray-500">No versions yet. Click Edit to create one.</div>
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
                          <button onClick={() => handleRollback(v.id)} className="text-blue-600 hover:text-blue-800 text-xs">
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

// ---------------------------------------------------------------------------
// Main TemplatesPage
// ---------------------------------------------------------------------------
export const TemplatesPage: React.FC = () => {
  const { success, error: toastError } = useToast();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('auto-response');

  // Auto-response state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [view, setView] = useState<View>('list');
  const [editTarget, setEditTarget] = useState<Template | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Template | null>(null);
  const [historyTarget, setHistoryTarget] = useState<Template | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [previewSubject, setPreviewSubject] = useState('');
  const [previewBody, setPreviewBody] = useState('');

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get<{ templates: Template[] }>(`${API_BASE_URL}/templates`);
      setTemplates(res.data.templates);
      setFetchError(null);
    } catch {
      setFetchError('Failed to load templates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleCreate = async (data: TemplateFormValues) => {
    setIsSubmitting(true);
    setServerError(null);
    try {
      await axios.post(`${API_BASE_URL}/templates`, data);
      success('Template created successfully');
      setView('list');
      fetchTemplates();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      setServerError(e.response?.data?.detail || e.response?.data?.message || 'Failed to create template');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdate = async (data: TemplateFormValues) => {
    if (!editTarget) return;
    setIsSubmitting(true);
    setServerError(null);
    try {
      await axios.put(`${API_BASE_URL}/templates/${editTarget.id}`, data);
      success('Template updated successfully');
      setView('list');
      setEditTarget(null);
      fetchTemplates();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      setServerError(e.response?.data?.detail || e.response?.data?.message || 'Failed to update template');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API_BASE_URL}/templates/${deleteTarget.id}`);
      setTemplates((prev) => prev.filter((t) => t.id !== deleteTarget.id));
      success('Template deleted');
    } catch {
      toastError('Failed to delete template');
    } finally {
      setDeleteTarget(null);
    }
  };

  const openEdit = (t: Template) => {
    setEditTarget(t);
    setPreviewSubject(t.subject);
    setPreviewBody(t.body);
    setServerError(null);
    setView('edit');
  };

  const openCreate = () => {
    setEditTarget(null);
    setPreviewSubject('');
    setPreviewBody('');
    setServerError(null);
    setView('create');
  };

  // Determine tenant ID for qualification emails
  // Admin users use their company_id; fall back to 1 for super-admin
  const tenantId = user?.company_id ?? 1;

  const tabClass = (tab: Tab) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      activeTab === tab
        ? 'border-blue-600 text-blue-600'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
    }`;

  // Auto-response create/edit view
  if (activeTab === 'auto-response' && (view === 'create' || view === 'edit')) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <button onClick={() => setView('list')} className="text-sm text-blue-600 hover:text-blue-800">← Back</button>
          <h1 className="text-2xl font-bold text-gray-800">{view === 'create' ? 'Create Template' : 'Edit Template'}</h1>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <TemplateEditor
              initialValues={editTarget ?? undefined}
              isEditMode={view === 'edit'}
              onSubmit={view === 'create' ? handleCreate : handleUpdate}
              onCancel={() => setView('list')}
              isSubmitting={isSubmitting}
              serverError={serverError}
            />
          </div>
          <div>
            <TemplatePreview subject={previewSubject} body={previewBody} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Templates</h1>

      {/* Tab bar */}
      <nav className="flex border-b border-gray-200 space-x-1">
        <button className={tabClass('auto-response')} onClick={() => setActiveTab('auto-response')}>
          Auto-Response
        </button>
        <button className={tabClass('qualification')} onClick={() => setActiveTab('qualification')}>
          Qualification Emails
        </button>
      </nav>

      {/* Auto-Response tab */}
      {activeTab === 'auto-response' && (
        <>
          {loading ? (
            <div className="flex items-center justify-center h-64"><div className="text-gray-600">Loading templates...</div></div>
          ) : fetchError ? (
            <div className="flex items-center justify-center h-64"><div className="text-red-600">{fetchError}</div></div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500">Automatic email replies sent when a new lead email is received.</p>
                <button onClick={openCreate} className="px-4 py-2 bg-blue-500 hover:bg-blue-700 text-white font-medium rounded-md transition-colors">
                  Create Template
                </button>
              </div>

              {templates.length === 0 ? (
                <div className="bg-white rounded-lg shadow p-8 text-center">
                  <div className="text-gray-500 mb-4">No templates configured</div>
                  <div className="text-sm text-gray-400">Create your first email response template</div>
                </div>
              ) : (
                <TemplateList templates={templates} onEdit={openEdit} onDelete={(t) => setDeleteTarget(t)} onViewHistory={(t) => setHistoryTarget(t)} />
              )}

              <ConfirmDialog
                isOpen={deleteTarget !== null}
                title="Delete Template"
                message={`Are you sure you want to delete template "${deleteTarget?.name}"? This action cannot be undone.`}
                confirmLabel="Delete"
                isDangerous
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeleteTarget(null)}
              />

              {historyTarget && (
                <TemplateVersionHistory
                  templateId={historyTarget.id}
                  templateName={historyTarget.name}
                  onClose={() => setHistoryTarget(null)}
                  onRollbackSuccess={() => { setHistoryTarget(null); fetchTemplates(); }}
                />
              )}
            </>
          )}
        </>
      )}

      {/* Qualification Emails tab */}
      {activeTab === 'qualification' && (
        <QualificationEmailsTab tenantId={tenantId} />
      )}
    </div>
  );
};
