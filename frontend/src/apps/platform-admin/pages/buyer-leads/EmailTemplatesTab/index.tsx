/**
 * EmailTemplatesTab — list email templates with create/delete, version history with rollback.
 * Requirements: 13.1
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '@/shared/contexts/ToastContext';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

interface MessageTemplate { id: number; key: string; intent_type: string; created_at: string; }
interface MessageTemplateVersion { id: number; version_number: number; is_active: boolean; published_at: string | null; subject_template: string; }

const KEY_OPTIONS = ['INITIAL_INVITE_EMAIL', 'POST_SUBMISSION_EMAIL'];
const KEY_LABELS: Record<string, string> = {
  INITIAL_INVITE_EMAIL: 'Initial Invite Email',
  POST_SUBMISSION_EMAIL: 'Post-Submission Email',
};
const PAGE_SIZE = 20;

export const EmailTemplatesTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();
  const t = useT();

  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<MessageTemplate | null>(null);
  const [versions, setVersions] = useState<MessageTemplateVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState(KEY_OPTIONS[0]);
  const [creating, setCreating] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<MessageTemplate[]>(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates`);
      setTemplates(res.data);
    } catch { toastError('Failed to load message templates'); } finally { setLoading(false); }
  }, [tenantId]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const fetchVersions = async (template: MessageTemplate) => {
    setSelectedTemplate(template); setVersionsLoading(true);
    try {
      const res = await axios.get<MessageTemplateVersion[]>(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${template.id}/versions`);
      setVersions(res.data);
    } catch { toastError('Failed to load template versions'); } finally { setVersionsLoading(false); }
  };

  const handleCreate = async () => {
    setCreating(true);
    try {
      await axios.post(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates`, { key: newKey, intent_type: 'BUY' });
      success('Template created'); setShowCreate(false); fetchTemplates();
    } catch { toastError('Failed to create template'); } finally { setCreating(false); }
  };

  const handleDelete = async (tmpl: MessageTemplate) => {
    if (!confirm(`Delete "${KEY_LABELS[tmpl.key] ?? tmpl.key}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${tmpl.id}`);
      success('Deleted');
      if (selectedTemplate?.id === tmpl.id) { setSelectedTemplate(null); setVersions([]); }
      fetchTemplates();
    } catch { toastError('Delete failed'); }
  };

  const handleRollback = async (vid: number) => {
    if (!selectedTemplate) return;
    try {
      await axios.post(`${API_BASE_URL}/buyer-leads/tenants/${tenantId}/message-templates/${selectedTemplate.id}/versions/${vid}/rollback`);
      success('Rolled back'); fetchVersions(selectedTemplate);
    } catch { toastError('Rollback failed'); }
  };

  const totalPages = Math.max(1, Math.ceil(templates.length / PAGE_SIZE));
  const paged = templates.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) return <div className={styles.loadingState} style={{ color: t.textMuted }}>Loading…</div>;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title} style={{ color: t.text }}>Email Templates</h2>
        <button onClick={() => setShowCreate(true)} style={t.btnPrimary}>New Template</button>
      </div>

      {showCreate && (
        <div className={styles.modalOverlay}>
          <div style={t.card} className={styles.modalContent}>
            <h3 className={styles.modalTitle} style={{ color: t.text }}>New Email Template</h3>
            <div>
              <label style={t.labelStyle}>Template Type</label>
              <select value={newKey} onChange={(e) => setNewKey(e.target.value)} style={t.input}>
                {KEY_OPTIONS.map((k) => <option key={k} value={k}>{KEY_LABELS[k] ?? k}</option>)}
              </select>
            </div>
            <div className={styles.modalActions}>
              <button onClick={() => setShowCreate(false)} style={t.btnSecondary}>Cancel</button>
              <button onClick={handleCreate} disabled={creating} style={{ ...t.btnPrimary, opacity: creating ? 0.6 : 1 }}>
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className={styles.splitGrid}>
        <div className={styles.templateList}>
          {paged.length === 0 ? (
            <div style={{ ...t.card, color: t.textMuted }} className={styles.emptyState}>
              No templates found. Run the seed script or create one above.
            </div>
          ) : (
            paged.map((tmpl) => (
              <div key={tmpl.id} onClick={() => fetchVersions(tmpl)}
                style={{ ...t.card, outline: selectedTemplate?.id === tmpl.id ? `2px solid ${t.accent}` : 'none', outlineOffset: -2 }}
                className={styles.templateCard}>
                <div className={styles.templateCardInner}>
                  <div>
                    <p className={styles.templateName} style={{ color: t.text }}>{KEY_LABELS[tmpl.key] ?? tmpl.key}</p>
                    <p className={styles.templateKey} style={{ color: t.textFaint }}>{tmpl.key}</p>
                  </div>
                  <div className={styles.templateActions}>
                    <button onClick={(e) => { e.stopPropagation(); navigate(`/buyer-leads/${tenantId}/templates/${tmpl.id}`); }}
                      className={styles.actionButton} style={t.btnPrimary}>Edit</button>
                    <button onClick={(e) => { e.stopPropagation(); handleDelete(tmpl); }}
                      className={styles.actionButton} style={t.btnDanger}>Delete</button>
                  </div>
                </div>
              </div>
            ))
          )}

          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className={styles.paginationButton} style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>‹ Prev</button>
              <span className={styles.paginationText} style={{ color: t.textMuted }}>{page} / {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className={styles.paginationButton} style={{ ...t.btnSecondary, opacity: page === totalPages ? 0.4 : 1 }}>Next ›</button>
            </div>
          )}
        </div>

        {selectedTemplate && (
          <div style={t.card} className={styles.versionPanel}>
            <div className={styles.versionPanelHeader} style={{ borderBottom: `1px solid ${t.border}`, background: t.bgCardHover }}>
              <p className={styles.versionPanelTitle} style={{ color: t.text }}>
                Versions — {KEY_LABELS[selectedTemplate.key] ?? selectedTemplate.key}
              </p>
            </div>
            {versionsLoading ? (
              <div className={styles.versionLoadingState} style={{ color: t.textMuted }}>Loading…</div>
            ) : versions.length === 0 ? (
              <div className={styles.versionEmptyState} style={{ color: t.textMuted }}>No versions yet</div>
            ) : (
              <table className={styles.table}>
                <thead><tr>
                  {['Version', 'Subject', 'Active', 'Actions'].map((h, i) => (
                    <th key={h} style={{ ...t.th, padding: '10px 16px', textAlign: i === 3 ? 'right' : 'left' }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.id} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={{ ...t.td }} className={styles.versionCell}>v{v.version_number}</td>
                      <td style={{ ...t.td, color: t.textMuted }} className={styles.subjectCell}>{v.subject_template}</td>
                      <td style={{ ...t.td }} className={styles.versionCell}>
                        {v.is_active && <span className={styles.activeBadge} style={{ background: t.greenBg, color: t.green }}>Active</span>}
                      </td>
                      <td style={{ ...t.td, textAlign: 'right' }} className={styles.versionCell}>
                        {!v.is_active && <button onClick={() => handleRollback(v.id)} className={styles.rollbackButton} style={t.btnSecondary}>Rollback</button>}
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
