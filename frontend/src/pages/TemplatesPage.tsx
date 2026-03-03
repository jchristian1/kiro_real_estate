/**
 * Templates Page Component
 * Requirements: 3.1, 3.3, 3.5, 3.6, 3.7, 15.3, 15.5, 15.6
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios, { AxiosError } from 'axios';
import { TemplateList, Template } from '../components/TemplateList';
import { TemplateEditor, TemplateFormValues } from '../components/TemplateEditor';
import { TemplatePreview } from '../components/TemplatePreview';
import { TemplateVersionHistory } from '../components/TemplateVersionHistory';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../contexts/ToastContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

type View = 'list' | 'create' | 'edit';

export const TemplatesPage: React.FC = () => {
  const { success, error: toastError } = useToast();
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

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-600">Loading templates...</div></div>;
  if (fetchError) return <div className="flex items-center justify-center h-64"><div className="text-red-600">{fetchError}</div></div>;

  if (view === 'create' || view === 'edit') {
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
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Templates</h1>
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
    </div>
  );
};
