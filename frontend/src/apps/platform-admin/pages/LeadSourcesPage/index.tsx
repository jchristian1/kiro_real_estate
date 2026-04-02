import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { LeadSourceList } from '@/platformAdminComponents/LeadSourceList';
import { LeadSourceForm } from '@/platformAdminComponents/LeadSourceForm';
import { ConfirmDialog } from '@/platformAdminComponents/ConfirmDialog';
import { RegexVersionHistory } from '@/platformAdminComponents/RegexVersionHistory';
import { useT } from '@/shared/hooks/useT';
import { LeadSource, LeadSourceFormValues, Template } from '@/models';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';
const PAGE_SIZE = 20;

type View = 'list' | 'create' | 'edit';

export const LeadSourcesPage: React.FC = () => {
  const t = useT();
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
  const [page, setPage] = useState(1);

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
      <div className={styles.formContainer}>
        <h1 className={styles.title} style={{ color: t.text }}>Create Lead Source</h1>
        <div style={{ ...t.card }} className={styles.formCard}>
          <LeadSourceForm onSubmit={handleCreate} onCancel={() => { setView('list'); setServerError(null); }}
            isSubmitting={submitting} serverError={serverError} templates={templates} />
        </div>
      </div>
    );
  }

  if (view === 'edit' && selected) {
    return (
      <div className={styles.formContainer}>
        <h1 className={styles.title} style={{ color: t.text }}>Edit Lead Source</h1>
        <div style={{ ...t.card }} className={styles.formCard}>
          <LeadSourceForm isEditMode initialValues={selected}
            onSubmit={handleEdit}
            onCancel={() => { setView('list'); setSelected(null); setServerError(null); }}
            isSubmitting={submitting} serverError={serverError} templates={templates} />
        </div>
      </div>
    );
  }

  if (loading) return (
    <div className={styles.loadingContainer} style={{ color: t.textMuted }}>
      Loading lead sources…
    </div>
  );
  if (error) return (
    <div className={styles.errorContainer} style={{ color: t.red }}>
      {error}
    </div>
  );

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title} style={{ color: t.text }}>Lead Sources</h1>
        <button onClick={() => { setServerError(null); setView('create'); }} style={t.btnPrimary}>
          Create Lead Source
        </button>
      </div>

      {leadSources.length === 0 ? (
        <div style={{ ...t.card }} className={styles.emptyState}>
          <div className={styles.emptyStateText} style={{ color: t.textMuted }}>No lead sources configured</div>
          <div className={styles.emptyStateSubtext} style={{ color: t.textFaint }}>Create your first lead source to start matching incoming leads</div>
        </div>
      ) : (
        <>
          <LeadSourceList
            leadSources={leadSources.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)}
            onView={(ls) => { setSelected(ls); }}
            onEdit={(ls) => { setSelected(ls); setServerError(null); setView('edit'); }}
            onDelete={(ls) => setDeleteTarget(ls)}
            onViewHistory={(ls) => setHistoryTarget(ls)}
          />
          {Math.ceil(leadSources.length / PAGE_SIZE) > 1 && (
            <div className={styles.paginationContainer}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>Previous</button>
              <span className={styles.paginationText} style={{ color: t.textMuted }}>Page {page} of {Math.ceil(leadSources.length / PAGE_SIZE)}</span>
              <button onClick={() => setPage(p => Math.min(Math.ceil(leadSources.length / PAGE_SIZE), p + 1))} disabled={page === Math.ceil(leadSources.length / PAGE_SIZE)}
                style={{ ...t.btnSecondary, opacity: page === Math.ceil(leadSources.length / PAGE_SIZE) ? 0.4 : 1 }}>Next</button>
            </div>
          )}
        </>
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
