/**
 * EmailTemplatesTab — list email templates with create/delete, version history with rollback.
 * Requirements: 13.1
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../../../shared/contexts/ToastContext';
import { useT } from '../../../../shared/hooks/useT';

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

// Pagination
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

  const handleDelete = async (tmpl: MessageTemplate) => {
    if (!confirm(`Delete "${KEY_LABELS[tmpl.key] ?? tmpl.key}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API}/buyer-leads/tenants/${tenantId}/message-templates/${tmpl.id}`);
      success('Deleted');
      if (selectedTemplate?.id === tmpl.id) { setSelectedTemplate(null); setVersions([]); }
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

  const totalPages = Math.max(1, Math.ceil(templates.length / PAGE_SIZE));
  const paged = templates.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: t.textMuted }}>Loading…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>Email Templates</h2>
        <button onClick={() => setShowCreate(true)} style={t.btnPrimary}>
          New Template
        </button>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
        }}>
          <div style={{
            ...t.card,
            width: '100%', maxWidth: 420,
            display: 'flex', flexDirection: 'column', gap: 16,
          }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: t.text, margin: 0 }}>New Email Template</h3>
            <div>
              <label style={t.labelStyle}>Template Type</label>
              <select
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                style={t.input}
              >
                {KEY_OPTIONS.map((k) => (
                  <option key={k} value={k}>{KEY_LABELS[k] ?? k}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowCreate(false)} style={t.btnSecondary}>Cancel</button>
              <button onClick={handleCreate} disabled={creating} style={{ ...t.btnPrimary, opacity: creating ? 0.6 : 1 }}>
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Template list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {paged.length === 0 ? (
            <div style={{ ...t.card, textAlign: 'center', color: t.textMuted, padding: 40 }}>
              No templates found. Run the seed script or create one above.
            </div>
          ) : (
            paged.map((tmpl) => (
              <div
                key={tmpl.id}
                onClick={() => fetchVersions(tmpl)}
                style={{
                  ...t.card,
                  cursor: 'pointer',
                  outline: selectedTemplate?.id === tmpl.id ? `2px solid ${t.accent}` : 'none',
                  outlineOffset: -2,
                  padding: '14px 18px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: t.text, margin: 0 }}>
                      {KEY_LABELS[tmpl.key] ?? tmpl.key}
                    </p>
                    <p style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>{tmpl.key}</p>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(`/buyer-leads/${tenantId}/templates/${tmpl.id}`); }}
                      style={{ ...t.btnPrimary, padding: '5px 12px', fontSize: 12 }}
                    >
                      Edit
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(tmpl); }}
                      style={{ ...t.btnDanger, padding: '5px 12px', fontSize: 12 }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 8 }}>
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                style={{ ...t.btnSecondary, padding: '5px 12px', fontSize: 12, opacity: page === 1 ? 0.4 : 1 }}
              >
                ‹ Prev
              </button>
              <span style={{ fontSize: 12, color: t.textMuted }}>
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                style={{ ...t.btnSecondary, padding: '5px 12px', fontSize: 12, opacity: page === totalPages ? 0.4 : 1 }}
              >
                Next ›
              </button>
            </div>
          )}
        </div>

        {/* Version panel */}
        {selectedTemplate && (
          <div style={{ ...t.card, padding: 0, overflow: 'hidden' }}>
            <div style={{
              padding: '12px 18px',
              borderBottom: `1px solid ${t.border}`,
              background: t.bgCardHover,
            }}>
              <p style={{ fontSize: 13, fontWeight: 600, color: t.text, margin: 0 }}>
                Versions — {KEY_LABELS[selectedTemplate.key] ?? selectedTemplate.key}
              </p>
            </div>
            {versionsLoading ? (
              <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>
            ) : versions.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>No versions yet</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Version', 'Subject', 'Active', 'Actions'].map((h, i) => (
                      <th key={h} style={{
                        ...t.th,
                        padding: '10px 16px',
                        textAlign: i === 3 ? 'right' : 'left',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.id} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={{ ...t.td, padding: '10px 16px' }}>v{v.version_number}</td>
                      <td style={{ ...t.td, padding: '10px 16px', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {v.subject_template}
                      </td>
                      <td style={{ ...t.td, padding: '10px 16px' }}>
                        {v.is_active && (
                          <span style={{
                            padding: '2px 8px', fontSize: 11, fontWeight: 600,
                            background: t.greenBg, color: t.green, borderRadius: 20,
                          }}>Active</span>
                        )}
                      </td>
                      <td style={{ ...t.td, padding: '10px 16px', textAlign: 'right' }}>
                        {!v.is_active && (
                          <button
                            onClick={() => handleRollback(v.id)}
                            style={{ ...t.btnSecondary, padding: '4px 10px', fontSize: 11 }}
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
