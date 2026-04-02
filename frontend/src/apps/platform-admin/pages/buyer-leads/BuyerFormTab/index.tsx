import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '@/shared/contexts/ToastContext';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

interface FormTemplate { id: number; name: string; status: string; intent_type: string; created_at: string; }
interface FormVersion { id: number; version_number: number; is_active: boolean; published_at: string | null; }

export const BuyerFormTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();
  const t = useT();

  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<FormTemplate | null>(null);
  const [versions, setVersions] = useState<FormVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<FormTemplate[]>(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms`);
      setTemplates(res.data);
    } catch { toastError('Failed to load form templates'); } finally { setLoading(false); }
  }, [tenantId]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const fetchVersions = async (tmpl: FormTemplate) => {
    setSelectedTemplate(tmpl); setVersionsLoading(true);
    try {
      const res = await axios.get<FormVersion[]>(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${tmpl.id}/versions`);
      setVersions(res.data);
    } catch { toastError('Failed to load versions'); } finally { setVersionsLoading(false); }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await axios.post(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms`, { name: newName.trim(), intent_type: 'BUY' });
      success('Form template created'); setNewName(''); setShowCreate(false); fetchTemplates();
    } catch { toastError('Failed to create form template'); } finally { setCreating(false); }
  };

  const handleRename = async (tmpl: FormTemplate) => {
    if (!editName.trim() || editName === tmpl.name) { setEditingId(null); return; }
    try {
      await axios.put(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${tmpl.id}`, { name: editName.trim() });
      success('Renamed'); setEditingId(null); fetchTemplates();
    } catch { toastError('Rename failed'); }
  };

  const handleDelete = async (tmpl: FormTemplate) => {
    if (!confirm(`Delete "${tmpl.name}"?`)) return;
    try {
      await axios.delete(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${tmpl.id}`);
      success('Deleted');
      if (selectedTemplate?.id === tmpl.id) { setSelectedTemplate(null); setVersions([]); }
      fetchTemplates();
    } catch { toastError('Delete failed'); }
  };

  const handleRollback = async (templateId: number, versionId: number) => {
    try {
      await axios.post(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/forms/${templateId}/versions/${versionId}/rollback`);
      success('Rolled back to version');
      if (selectedTemplate) fetchVersions(selectedTemplate);
    } catch { toastError('Rollback failed'); }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, { bg: string; color: string }> = {
      active: { bg: t.greenBg, color: t.green },
      draft: { bg: t.yellowBg, color: t.yellow },
      archived: { bg: t.bgBadge, color: t.textMuted },
    };
    const c = colors[status] ?? { bg: t.bgBadge, color: t.textMuted };
    return <span className={styles.activeBadge} style={{ background: c.bg, color: c.color }}>{status}</span>;
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title} style={{ color: t.text }}>Buyer Qualification Forms</h2>
        <button onClick={() => setShowCreate(true)} style={t.btnPrimary}>New Form Template</button>
      </div>

      {showCreate && (
        <div className={styles.modalOverlay}>
          <div style={t.card} className={styles.modalContent}>
            <h3 className={styles.modalTitle} style={{ color: t.text }}>New Form Template</h3>
            <input type="text" placeholder="Template name" value={newName} onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()} style={t.input} autoFocus />
            <div className={styles.modalActions}>
              <button onClick={() => setShowCreate(false)} style={t.btnSecondary}>Cancel</button>
              <button onClick={handleCreate} disabled={creating || !newName.trim()} style={{ ...t.btnPrimary, opacity: creating || !newName.trim() ? 0.5 : 1 }}>
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className={styles.splitGrid}>
        <div style={t.card}>
          {loading ? (
            <div className={styles.loadingState} style={{ color: t.textMuted }}>Loading…</div>
          ) : templates.length === 0 ? (
            <div className={styles.emptyState} style={{ color: t.textMuted }}>No form templates yet</div>
          ) : (
            <table className={styles.table}>
              <thead><tr>
                {['Name', 'Status', ''].map(h => <th key={h} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {templates.map((tmpl) => (
                  <tr key={tmpl.id} onClick={() => { if (editingId !== tmpl.id) fetchVersions(tmpl); }}
                    style={{ borderBottom: `1px solid ${t.border}`, cursor: 'pointer', background: selectedTemplate?.id === tmpl.id ? t.accentBg : 'transparent' }}>
                    <td style={{ ...t.td, fontWeight: 500 }}>
                      {editingId === tmpl.id ? (
                        <input type="text" value={editName} autoFocus onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') handleRename(tmpl); if (e.key === 'Escape') setEditingId(null); }}
                          onClick={(e) => e.stopPropagation()} style={{ ...t.input, width: 'auto' }} />
                      ) : tmpl.name}
                    </td>
                    <td style={t.td}>{statusBadge(tmpl.status)}</td>
                    <td style={{ ...t.td, textAlign: 'right' }}>
                      <div className={styles.actionsCell}>
                        {editingId === tmpl.id ? (
                          <>
                            <button onClick={(e) => { e.stopPropagation(); handleRename(tmpl); }} className={styles.linkButtonBold} style={{ color: t.green }}>Save</button>
                            <button onClick={(e) => { e.stopPropagation(); setEditingId(null); }} className={styles.linkButton} style={{ color: t.textMuted }}>Cancel</button>
                          </>
                        ) : (
                          <>
                            <button onClick={(e) => { e.stopPropagation(); setEditingId(tmpl.id); setEditName(tmpl.name); }} className={styles.linkButton} style={{ color: t.textMuted }}>Rename</button>
                            <button onClick={(e) => { e.stopPropagation(); navigate(`/buyer-leads/${tenantId}/forms/${tmpl.id}`); }} className={styles.linkButtonBold} style={{ color: t.accent }}>Edit</button>
                            <button onClick={(e) => { e.stopPropagation(); handleDelete(tmpl); }} className={styles.linkButton} style={{ color: t.red }}>Delete</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selectedTemplate && (
          <div style={t.card}>
            <div style={t.sectionTitle} className={styles.versionSectionTitle}>Versions — {selectedTemplate.name}</div>
            {versionsLoading ? (
              <div className={styles.versionsLoadingState} style={{ color: t.textMuted }}>Loading…</div>
            ) : versions.length === 0 ? (
              <div className={styles.versionsEmptyState} style={{ color: t.textMuted }}>No versions published yet</div>
            ) : (
              <table className={styles.table}>
                <thead><tr>
                  {['Version', 'Published', 'Active', ''].map(h => <th key={h} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left' }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.id} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={t.td}>v{v.version_number}</td>
                      <td style={{ ...t.td, color: t.textMuted }}>{v.published_at ? new Date(v.published_at).toLocaleDateString() : '—'}</td>
                      <td style={t.td}>{v.is_active && <span className={styles.activeBadge} style={{ background: t.greenBg, color: t.green }}>Active</span>}</td>
                      <td style={{ ...t.td, textAlign: 'right' }}>
                        {!v.is_active && <button onClick={() => handleRollback(selectedTemplate.id, v.id)} className={styles.linkButtonBold} style={{ color: t.accent }}>Rollback</button>}
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
