/**
 * Forms Page — unified form + scoring builder.
 * Single view: card list + slide-in drawer with form questions AND scoring in one scroll.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { useToast } from '@/shared/contexts/ToastContext';
import { useAuth } from '@/apps/platform-admin/contexts';
import { ConfirmDialog } from '@/platformAdminComponents/ConfirmDialog';
import { FormDrawer, FormCard, RenameModal } from './components';
import styles from './index.module.css';

const API = '/api/v1';

interface FormTemplate {
  id: number;
  name: string;
  status: 'active' | 'draft' | 'archived';
  intent_type: string;
  created_at: string;
}

export const FormsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();
  const { user } = useAuth();

  const tenantId = String(user?.company_id ?? 1);

  const [forms, setForms] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [drawerForm, setDrawerForm] = useState<FormTemplate | null | 'new'>(undefined as unknown as null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FormTemplate | null>(null);
  const [renameTarget, setRenameTarget] = useState<FormTemplate | null>(null);
  const [search, setSearch] = useState('');

  const fetchForms = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<FormTemplate[]>(`${API}/buyer-leads/tenants/${tenantId}/forms`);
      setForms(res.data ?? []);
      setFetchError(null);
    } catch { setFetchError('Failed to load forms'); }
    finally { setLoading(false); }
  }, [tenantId]);

  useEffect(() => { fetchForms(); }, [fetchForms]);

  const openCreate = () => { setDrawerForm(null); setDrawerOpen(true); };
  const openEdit = (form: FormTemplate) => { setDrawerForm(form); setDrawerOpen(true); };
  const closeDrawer = () => setDrawerOpen(false);
  const handleSaved = () => { closeDrawer(); fetchForms(); };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API}/buyer-leads/tenants/${tenantId}/forms/${deleteTarget.id}`);
      success('Form deleted');
      setForms(prev => prev.filter(f => f.id !== deleteTarget.id));
    } catch { toastError('Delete failed'); }
    finally { setDeleteTarget(null); }
  };

  const filtered = forms.filter(f => f.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title} style={{ color: t.text }}>Forms</h1>
          <p className={styles.subtitle} style={{ color: t.textMuted }}>
            Qualification forms sent to leads — includes questions and scoring in one place.
          </p>
        </div>
        <button onClick={openCreate} className={styles.createButton} style={{ background: t.accent }}>
          <span className={styles.createButtonIcon}>+</span> New Form
        </button>
      </div>

      {forms.length > 0 && (
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search forms…"
          className={styles.searchInput}
          style={{ background: t.bgInput, border: `1px solid ${t.border}`, color: t.text }} />
      )}

      {loading ? (
        <div className={styles.centeredState}>
          <span className={styles.centeredStateText} style={{ color: t.textMuted }}>Loading forms…</span>
        </div>
      ) : fetchError ? (
        <div className={styles.centeredState}>
          <span className={styles.centeredStateText} style={{ color: t.red }}>{fetchError}</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className={styles.emptyState}
          style={{ background: isDark ? '#1c1f26' : '#ffffff', border: `1px solid ${isDark ? '#2a2d35' : '#e5e7eb'}` }}>
          <div className={styles.emptyStateIcon}>📋</div>
          <div className={styles.emptyStateTitle} style={{ color: t.text }}>
            {search ? 'No forms match your search' : 'No forms yet'}
          </div>
          <div className={styles.emptyStateSubtitle} style={{ color: t.textMuted }}>
            {search ? 'Try a different search term.' : 'Create your first qualification form with questions and scoring.'}
          </div>
          {!search && (
            <button onClick={openCreate} className={styles.createButton} style={{ background: t.accent }}>Create Form</button>
          )}
        </div>
      ) : (
        <div className={styles.formList}>
          {filtered.map(form => (
            <FormCard key={form.id} form={form}
              onEdit={() => openEdit(form)}
              onDelete={() => setDeleteTarget(form)}
              onRename={() => setRenameTarget(form)} />
          ))}
        </div>
      )}

      {drawerOpen && (
        <FormDrawer form={drawerForm as FormTemplate | null} tenantId={tenantId}
          onClose={closeDrawer} onSaved={handleSaved} />
      )}

      {renameTarget && (
        <RenameModal form={renameTarget} tenantId={tenantId}
          onClose={() => setRenameTarget(null)}
          onSaved={() => { setRenameTarget(null); fetchForms(); }} />
      )}

      <ConfirmDialog isOpen={deleteTarget !== null} title="Delete Form"
        message={`Delete "${deleteTarget?.name}"? This cannot be undone.`}
        confirmLabel="Delete" isDangerous
        onConfirm={handleDeleteConfirm} onCancel={() => setDeleteTarget(null)} />
    </div>
  );
};
