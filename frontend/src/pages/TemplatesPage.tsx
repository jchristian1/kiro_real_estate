/**
 * Templates Page — Auto-Response + Qualification Emails tabs.
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
import { useT } from '../utils/useT';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const PAGE_SIZE = 20;

type View = 'list' | 'create' | 'edit';
type Tab = 'auto-response' | 'qualification';

interface MsgTemplate { id: number; key: string; intent_type: string; created_at: string; }
interface MsgVersion { id: number; version_number: number; is_active: boolean; published_at: string | null; subject_template: string; }

const KEY_OPTIONS = ['INITIAL_INVITE_EMAIL', 'POST_SUBMISSION_EMAIL'];
const KEY_LABELS: Record<string, string> = {
  INITIAL_INVITE_EMAIL: 'Initial Invite Email',
  POST_SUBMISSION_EMAIL: 'Post-Submission Email',
};

// ---------------------------------------------------------------------------
// Qualification Emails tab
// ---------------------------------------------------------------------------
const QualificationEmailsTab: React.FC<{ tenantId: number }> = ({ tenantId }) => {
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();
  const t = useT();

  const [templates, setTemplates] = useState<MsgTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<MsgTemplate | null>(null);
  const [versions, setVersions] = useState<MsgVersion[]>([]);
  const [versLoading, setVersLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState(KEY_OPTIONS[0]);
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get<MsgTemplate[]>(`${API}/buyer-leads/tenants/${tenantId}/message-templates`);
      setTemplates(r.data);
    } catch { toastError('Failed to load templates'); }
    finally { setLoading(false); }
  }, [tenantId]);

  useEffect(() => { load(); }, [load]);

  const loadVersions = async (tmpl: MsgTemplate) => {
    setSelected(tmpl); setVersLoading(true);
    try {
      const r = await axios.get<MsgVersion[]>(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${tmpl.id}/versions`);
      setVersions(r.data);
    } catch { toastError('Failed to load versions'); }
    finally { setVersLoading(false); }
  };

  const handleCreate = async () => {
    setCreating(true);
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/message-templates`, { key: newKey, intent_type: 'BUY' });
      success('Template created'); setShowCreate(false); load();
    } catch { toastError('Failed to create template'); }
    finally { setCreating(false); }
  };

  const handleDelete = async (tmpl: MsgTemplate) => {
    if (!confirm(`Delete "${KEY_LABELS[tmpl.key] ?? tmpl.key}"?`)) return;
    try {
      await axios.delete(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${tmpl.id}`);
      success('Deleted');
      if (selected?.id === tmpl.id) { setSelected(null); setVersions([]); }
      load();
    } catch { toastError('Delete failed'); }
  };

  const handleRollback = async (vid: number) => {
    if (!selected) return;
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${selected.id}/versions/${vid}/rollback`);
      success('Rolled back'); loadVersions(selected);
    } catch { toastError('Rollback failed'); }
  };

  const totalPages = Math.max(1, Math.ceil(templates.length / PAGE_SIZE));
  const paged = templates.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <p style={{ fontSize: 13, color: t.textMuted, maxWidth: 520, margin: 0 }}>
          Emails sent automatically during the buyer qualification pipeline. Use variables like{' '}
          <code style={{ background: t.bgInput, padding: '1px 5px', borderRadius: 4, fontSize: 11, color: t.accent }}>{'{{lead.first_name}}'}</code>,{' '}
          <code style={{ background: t.bgInput, padding: '1px 5px', borderRadius: 4, fontSize: 11, color: t.accent }}>{'{{form.link}}'}</code>,{' '}
          <code style={{ background: t.bgInput, padding: '1px 5px', borderRadius: 4, fontSize: 11, color: t.accent }}>{'{{tenant.name}}'}</code>.
        </p>
        <button style={t.btnPrimary} onClick={() => setShowCreate(true)}>New Template</button>
      </div>

      {showCreate && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ ...t.card, width: '100%', maxWidth: 420, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>New Qualification Email Template</h3>
            <div>
              <label style={t.labelStyle}>Template Type</label>
              <select value={newKey} onChange={(e) => setNewKey(e.target.value)} style={{ ...t.input }}>
                {KEY_OPTIONS.map((k) => <option key={k} value={k}>{KEY_LABELS[k] ?? k}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button style={t.btnSecondary} onClick={() => setShowCreate(false)}>Cancel</button>
              <button style={{ ...t.btnPrimary, opacity: creating ? 0.6 : 1 }} onClick={handleCreate} disabled={creating}>
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1fr' : '1fr', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {paged.length === 0 ? (
            <div style={{ ...t.card, textAlign: 'center', color: t.textMuted, padding: 32 }}>
              No qualification email templates found. Create one above.
            </div>
          ) : paged.map((tmpl) => (
            <div
              key={tmpl.id}
              onClick={() => loadVersions(tmpl)}
              style={{
                ...t.card,
                cursor: 'pointer',
                outline: selected?.id === tmpl.id ? `2px solid ${t.accent}` : 'none',
                outlineOffset: 2,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ fontSize: 13, fontWeight: 600, color: t.text, margin: 0 }}>{KEY_LABELS[tmpl.key] ?? tmpl.key}</p>
                  <p style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>{tmpl.key}</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    style={{ ...t.btnPrimary, padding: '5px 12px', fontSize: 12 }}
                    onClick={(e) => { e.stopPropagation(); navigate(`/qualification-templates/${tenantId}/message-templates/${tmpl.id}`); }}
                  >Edit</button>
                  <button
                    style={{ ...t.btnDanger, padding: '5px 12px', fontSize: 12 }}
                    onClick={(e) => { e.stopPropagation(); handleDelete(tmpl); }}
                  >Delete</button>
                </div>
              </div>
            </div>
          ))}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, paddingTop: 8 }}>
              <button style={{ ...t.btnSecondary, padding: '4px 12px', fontSize: 12 }} disabled={page === 1} onClick={() => setPage(p => p - 1)}>Prev</button>
              <span style={{ fontSize: 12, color: t.textMuted, alignSelf: 'center' }}>{page} / {totalPages}</span>
              <button style={{ ...t.btnSecondary, padding: '4px 12px', fontSize: 12 }} disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
            </div>
          )}
        </div>

        {selected && (
          <div style={{ ...t.card, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', borderBottom: `1px solid ${t.border}` }}>
              <p style={{ fontSize: 13, fontWeight: 600, color: t.text, margin: 0 }}>
                Versions — {KEY_LABELS[selected.key] ?? selected.key}
              </p>
            </div>
            {versLoading ? (
              <div style={{ padding: 24, textAlign: 'center', color: t.textMuted }}>Loading…</div>
            ) : versions.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: t.textMuted }}>No versions yet. Click Edit to create one.</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Version', 'Subject', 'Active', 'Actions'].map((h, i) => (
                      <th key={h} style={{ ...t.th, padding: '10px 16px', textAlign: i === 3 ? 'right' : 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.id} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={{ ...t.td, padding: '10px 16px' }}>v{v.version_number}</td>
                      <td style={{ ...t.td, padding: '10px 16px', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v.subject_template}</td>
                      <td style={{ padding: '10px 16px' }}>
                        {v.is_active && <span style={{ padding: '2px 8px', fontSize: 11, fontWeight: 600, background: t.greenBg, color: t.green, borderRadius: 20 }}>Active</span>}
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'right' }}>
                        {!v.is_active && (
                          <button style={{ background: 'none', border: 'none', color: t.accent, fontSize: 12, cursor: 'pointer' }} onClick={() => handleRollback(v.id)}>
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
  const t = useT();
  const [activeTab, setActiveTab] = useState<Tab>('auto-response');

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
  const [page, setPage] = useState(1);

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get<{ templates: Template[] }>(`${API}/templates`);
      setTemplates(res.data.templates);
      setFetchError(null);
    } catch { setFetchError('Failed to load templates'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleCreate = async (data: TemplateFormValues) => {
    setIsSubmitting(true); setServerError(null);
    try {
      await axios.post(`${API}/templates`, data);
      success('Template created'); setView('list'); fetchTemplates();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      setServerError(e.response?.data?.detail || e.response?.data?.message || 'Failed to create template');
    } finally { setIsSubmitting(false); }
  };

  const handleUpdate = async (data: TemplateFormValues) => {
    if (!editTarget) return;
    setIsSubmitting(true); setServerError(null);
    try {
      await axios.put(`${API}/templates/${editTarget.id}`, data);
      success('Template updated'); setView('list'); setEditTarget(null); fetchTemplates();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      setServerError(e.response?.data?.detail || e.response?.data?.message || 'Failed to update template');
    } finally { setIsSubmitting(false); }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API}/templates/${deleteTarget.id}`);
      setTemplates((prev) => prev.filter((tmpl) => tmpl.id !== deleteTarget.id));
      success('Template deleted');
    } catch { toastError('Failed to delete template'); }
    finally { setDeleteTarget(null); }
  };

  const openEdit = (tmpl: Template) => {
    setEditTarget(tmpl); setPreviewSubject(tmpl.subject); setPreviewBody(tmpl.body);
    setServerError(null); setView('edit');
  };

  const openCreate = () => {
    setEditTarget(null); setPreviewSubject(''); setPreviewBody('');
    setServerError(null); setView('create');
  };

  const tenantId = user?.company_id ?? 1;

  const tabStyle = (tab: Tab): React.CSSProperties => ({
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 500,
    background: 'none',
    border: 'none',
    borderBottom: activeTab === tab ? `2px solid ${t.accent}` : '2px solid transparent',
    color: activeTab === tab ? t.accent : t.textMuted,
    cursor: 'pointer',
    transition: 'all 0.15s',
  });

  const totalPages = Math.max(1, Math.ceil(templates.length / PAGE_SIZE));
  const paged = templates.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (activeTab === 'auto-response' && (view === 'create' || view === 'edit')) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button style={{ background: 'none', border: 'none', color: t.accent, fontSize: 13, cursor: 'pointer' }} onClick={() => setView('list')}>← Back</button>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>{view === 'create' ? 'Create Template' : 'Edit Template'}</h1>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 24 }}>
          <div style={t.card}>
            <TemplateEditor
              initialValues={editTarget ?? undefined}
              isEditMode={view === 'edit'}
              onSubmit={view === 'create' ? handleCreate : handleUpdate}
              onCancel={() => setView('list')}
              isSubmitting={isSubmitting}
              serverError={serverError}
            />
          </div>
          <div><TemplatePreview subject={previewSubject} body={previewBody} /></div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Templates</h1>

      <nav style={{ display: 'flex', borderBottom: `1px solid ${t.border}`, gap: 4 }}>
        <button style={tabStyle('auto-response')} onClick={() => setActiveTab('auto-response')}>Auto-Response</button>
        <button style={tabStyle('qualification')} onClick={() => setActiveTab('qualification')}>Qualification Emails</button>
      </nav>

      {activeTab === 'auto-response' && (
        <>
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
              <span style={{ color: t.textMuted }}>Loading templates...</span>
            </div>
          ) : fetchError ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
              <span style={{ color: t.red }}>{fetchError}</span>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
                <p style={{ fontSize: 13, color: t.textMuted, margin: 0 }}>Automatic email replies sent when a new lead email is received.</p>
                <button style={t.btnPrimary} onClick={openCreate}>Create Template</button>
              </div>

              {templates.length === 0 ? (
                <div style={{ ...t.card, textAlign: 'center', padding: 40 }}>
                  <div style={{ color: t.textMuted, marginBottom: 8 }}>No templates configured</div>
                  <div style={{ fontSize: 12, color: t.textFaint }}>Create your first email response template</div>
                </div>
              ) : (
                <>
                  <TemplateList templates={paged} onEdit={openEdit} onDelete={(tmpl) => setDeleteTarget(tmpl)} onViewHistory={(tmpl) => setHistoryTarget(tmpl)} />
                  {totalPages > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
                      <button style={{ ...t.btnSecondary, padding: '4px 12px', fontSize: 12 }} disabled={page === 1} onClick={() => setPage(p => p - 1)}>Prev</button>
                      <span style={{ fontSize: 12, color: t.textMuted, alignSelf: 'center' }}>{page} / {totalPages}</span>
                      <button style={{ ...t.btnSecondary, padding: '4px 12px', fontSize: 12 }} disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
                    </div>
                  )}
                </>
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

      {activeTab === 'qualification' && <QualificationEmailsTab tenantId={tenantId} />}
    </div>
  );
};
