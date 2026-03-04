import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { LeadSourceList, LeadSource } from '../components/LeadSourceList';
import { LeadSourceForm, LeadSourceFormValues, Template } from '../components/LeadSourceForm';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { RegexVersionHistory } from '../components/RegexVersionHistory';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

type View = 'list' | 'create' | 'edit';

export const LeadSourcesPage: React.FC = () => {
  const [leadSources, setLeadSources] = useState<LeadSource[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>('list');
  const [selected, setSelected] = useState<LeadSource | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LeadSource | null>(null);
  const [historyTarget, setHistoryTarget] = useState<LeadSource | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const fetchLeadSources = async () => {
    try {
      setLoading(true);
      const [lsRes, tplRes] = await Promise.all([
        axios.get<{ lead_sources: LeadSource[] }>(`${API_BASE_URL}/lead-sources`),
        axios.get<{ templates: Template[] }>(`${API_BASE_URL}/templates`),
      ]);
      setLeadSources(lsRes.data.lead_sources);
      setTemplates(tplRes.data.templates);
      setError(null);
    } catch {
      setError('Failed to load lead sources');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLeadSources(); }, []);

  const handleCreate = async (data: LeadSourceFormValues) => {
    setSubmitting(true);
    setServerError(null);
    try {
      await axios.post(`${API_BASE_URL}/lead-sources`, data);
      await fetchLeadSources();
      setView('list');
    } catch (err) {
      const e = err as AxiosError<{ message?: string }>;
      setServerError(e.response?.data?.message || 'Failed to create lead source');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = async (data: LeadSourceFormValues) => {
    if (!selected) return;
    setSubmitting(true);
    setServerError(null);
    try {
      await axios.put(`${API_BASE_URL}/lead-sources/${selected.id}`, data);
      await fetchLeadSources();
      setView('list');
      setSelected(null);
    } catch (err) {
      const e = err as AxiosError<{ message?: string }>;
      setServerError(e.response?.data?.message || 'Failed to update lead source');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API_BASE_URL}/lead-sources/${deleteTarget.id}`);
      setLeadSources((prev) => prev.filter((ls) => ls.id !== deleteTarget.id));
    } catch { /* silent */ } finally {
      setDeleteTarget(null);
    }
  };

  if (view === 'create') {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-800">Create Lead Source</h1>
        <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
          <LeadSourceForm onSubmit={handleCreate} onCancel={() => { setView('list'); setServerError(null); }}
            isSubmitting={submitting} serverError={serverError} templates={templates} />
        </div>
      </div>
    );
  }

  if (view === 'edit' && selected) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-800">Edit Lead Source</h1>
        <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
          <LeadSourceForm isEditMode initialValues={selected}
            onSubmit={handleEdit}
            onCancel={() => { setView('list'); setSelected(null); setServerError(null); }}
            isSubmitting={submitting} serverError={serverError} templates={templates} />
        </div>
      </div>
    );
  }

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-600">Loading lead sources...</div></div>;
  if (error)   return <div className="flex items-center justify-center h-64"><div className="text-red-600">{error}</div></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Lead Sources</h1>
        <button onClick={() => { setServerError(null); setView('create'); }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md transition-colors">
          Create Lead Source
        </button>
      </div>

      {leadSources.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="text-gray-500 mb-4">No lead sources configured</div>
          <div className="text-sm text-gray-400">Create your first lead source to start matching incoming leads</div>
        </div>
      ) : (
        <LeadSourceList leadSources={leadSources}
          onView={(ls) => { setSelected(ls); }}
          onEdit={(ls) => { setSelected(ls); setServerError(null); setView('edit'); }}
          onDelete={(ls) => setDeleteTarget(ls)}
          onViewHistory={(ls) => setHistoryTarget(ls)} />
      )}

      <ConfirmDialog isOpen={deleteTarget !== null} title="Delete Lead Source"
        message={`Are you sure you want to delete "${deleteTarget?.sender_email}"? This action cannot be undone.`}
        confirmLabel="Delete" isDangerous onConfirm={handleDeleteConfirm} onCancel={() => setDeleteTarget(null)} />

      {historyTarget && (
        <RegexVersionHistory leadSourceId={historyTarget.id} leadSourceName={historyTarget.sender_email}
          onClose={() => setHistoryTarget(null)}
          onRollbackSuccess={() => { setHistoryTarget(null); fetchLeadSources(); }} />
      )}
    </div>
  );
};
