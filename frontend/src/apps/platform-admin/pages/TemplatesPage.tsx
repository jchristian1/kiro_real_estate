/**
 * Templates Page — Premium redesign.
 * Single unified list + slide-in drawer editor with live preview.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import axios, { AxiosError } from 'axios';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { useToast } from '../../../shared/contexts/ToastContext';
import { ConfirmDialog } from '../components/ConfirmDialog';

const API = '/api/v1';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Template {
  id: number;
  name: string;
  subject: string;
  body: string;
  created_at: string;
  updated_at: string;
}

interface TemplateVersion {
  id: number;
  version_number: number;
  is_active: boolean;
  published_at: string | null;
  subject_template: string;
}

const PLACEHOLDERS = ['{lead_name}', '{agent_name}', '{agent_phone}', '{agent_email}'];

// ─── Live Preview ─────────────────────────────────────────────────────────────

const SAMPLE: Record<string, string> = {
  '{lead_name}': 'John Doe',
  '{agent_name}': 'Agent Smith',
  '{agent_phone}': '555-9999',
  '{agent_email}': 'agent@example.com',
};

function renderPreview(text: string): string {
  return PLACEHOLDERS.reduce((s, p) => s.split(p).join(SAMPLE[p] ?? p), text);
}

// ─── Template Drawer ──────────────────────────────────────────────────────────

interface DrawerProps {
  template: Template | null; // null = create mode
  onClose: () => void;
  onSaved: () => void;
}

const TemplateDrawer: React.FC<DrawerProps> = ({ template, onClose, onSaved }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();

  const [name, setName] = useState(template?.name ?? '');
  const [subject, setSubject] = useState(template?.subject ?? '');
  const [body, setBody] = useState(template?.body ?? '');
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'edit' | 'history'>('edit');
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [versLoading, setVersLoading] = useState(false);

  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const subjectRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setName(template?.name ?? '');
    setSubject(template?.subject ?? '');
    setBody(template?.body ?? '');
    setServerError(null);
    setActiveTab('edit');
  }, [template]);

  const loadVersions = useCallback(async () => {
    if (!template) return;
    setVersLoading(true);
    try {
      const r = await axios.get<{ versions: TemplateVersion[] }>(`${API}/templates/${template.id}/versions`);
      setVersions(r.data.versions ?? []);
    } catch { toastError('Failed to load version history'); }
    finally { setVersLoading(false); }
  }, [template]);

  useEffect(() => {
    if (activeTab === 'history') loadVersions();
  }, [activeTab, loadVersions]);

  const insertPlaceholder = (field: 'subject' | 'body', p: string) => {
    if (field === 'subject') {
      const el = subjectRef.current;
      if (!el) { setSubject(s => s + p); return; }
      const start = el.selectionStart ?? subject.length;
      const end = el.selectionEnd ?? subject.length;
      const next = subject.slice(0, start) + p + subject.slice(end);
      setSubject(next);
      setTimeout(() => { el.focus(); el.setSelectionRange(start + p.length, start + p.length); }, 0);
    } else {
      const el = bodyRef.current;
      if (!el) { setBody(b => b + p); return; }
      const start = el.selectionStart ?? body.length;
      const end = el.selectionEnd ?? body.length;
      const next = body.slice(0, start) + p + body.slice(end);
      setBody(next);
      setTimeout(() => { el.focus(); el.setSelectionRange(start + p.length, start + p.length); }, 0);
    }
  };

  const handleSave = async () => {
    if (!name.trim() || !subject.trim() || !body.trim()) {
      setServerError('Name, subject, and body are required.');
      return;
    }
    setSaving(true); setServerError(null);
    try {
      if (template) {
        await axios.put(`${API}/templates/${template.id}`, { name, subject, body });
        success('Template updated');
      } else {
        await axios.post(`${API}/templates`, { name, subject, body });
        success('Template created');
      }
      onSaved();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      setServerError(e.response?.data?.detail || e.response?.data?.message || 'Save failed');
    } finally { setSaving(false); }
  };

  const handleRollback = async (versionNumber: number) => {
    if (!template) return;
    try {
      await axios.post(`${API}/templates/${template.id}/rollback`, { version: versionNumber });
      success('Rolled back'); loadVersions(); onSaved();
    } catch { toastError('Rollback failed'); }
  };

  const previewSubject = renderPreview(subject);
  const previewBody = renderPreview(body);

  const drawerBg = isDark ? '#16181d' : '#ffffff';
  const panelBg = isDark ? '#1c1f26' : '#f8f9fb';
  const divider = isDark ? '#2a2d35' : '#e5e7eb';
  const tabActive = { color: t.accent, borderBottom: `2px solid ${t.accent}` };
  const tabInactive = { color: t.textMuted, borderBottom: '2px solid transparent' };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 40, backdropFilter: 'blur(2px)' }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: '100%', maxWidth: 900,
        background: drawerBg, zIndex: 50, display: 'flex', flexDirection: 'column',
        boxShadow: '-8px 0 40px rgba(0,0,0,0.35)',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 24px', borderBottom: `1px solid ${divider}`, flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: t.text }}>
              {template ? 'Edit Template' : 'New Template'}
            </div>
            {template && (
              <div style={{ fontSize: 12, color: t.textFaint, marginTop: 2 }}>
                Last updated {new Date(template.updated_at).toLocaleDateString()}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{ padding: '8px 18px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.6 : 1, minWidth: 100 }}
            >
              {saving ? 'Saving…' : template ? 'Save Changes' : 'Create'}
            </button>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: t.textMuted, fontSize: 20, cursor: 'pointer', lineHeight: 1, padding: '4px 8px' }}
            >×</button>
          </div>
        </div>

        {/* Tabs (only when editing) */}
        {template && (
          <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${divider}`, flexShrink: 0, padding: '0 24px' }}>
            {(['edit', 'history'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: '10px 16px', fontSize: 13, fontWeight: 500,
                  ...(activeTab === tab ? tabActive : tabInactive),
                  transition: 'all 0.15s',
                }}
              >
                {tab === 'edit' ? 'Editor' : 'Version History'}
              </button>
            ))}
          </div>
        )}

        {/* Body */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
          {activeTab === 'edit' ? (
            <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', overflow: 'hidden' }}>
              {/* Left: Editor */}
              <div style={{ padding: 24, overflowY: 'auto', borderRight: `1px solid ${divider}`, display: 'flex', flexDirection: 'column', gap: 20 }}>
                {serverError && (
                  <div style={{ padding: '10px 14px', background: isDark ? '#2d1a1a' : '#fff0f0', border: `1px solid ${t.red}40`, color: t.red, borderRadius: 8, fontSize: 13 }}>
                    {serverError}
                  </div>
                )}

                {/* Placeholder chips */}
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                    Insert Variable
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {PLACEHOLDERS.map(p => (
                      <div key={p} style={{ display: 'flex', gap: 4 }}>
                        <button
                          type="button"
                          onClick={() => insertPlaceholder('subject', p)}
                          title={`Insert ${p} into subject`}
                          style={{
                            padding: '3px 8px', fontSize: 11, background: isDark ? '#1e2330' : '#f0f4ff',
                            color: t.textMuted, border: `1px solid ${divider}`, borderRadius: '6px 0 0 6px',
                            cursor: 'pointer', fontFamily: 'monospace',
                          }}
                        >S</button>
                        <button
                          type="button"
                          onClick={() => insertPlaceholder('body', p)}
                          title={`Insert ${p} into body`}
                          style={{
                            padding: '3px 8px', fontSize: 11, background: isDark ? '#1a2035' : '#eef2ff',
                            color: t.accent, border: `1px solid ${t.accent}40`, borderRadius: '0 6px 6px 0',
                            cursor: 'pointer', fontFamily: 'monospace',
                          }}
                        >{p}</button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Name */}
                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 6 }}>
                    Template Name <span style={{ color: t.red }}>*</span>
                  </label>
                  <input
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="e.g. Welcome Email"
                    style={{ background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 13, color: t.text, outline: 'none', width: '100%', boxSizing: 'border-box' }}
                  />
                </div>

                {/* Subject */}
                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 6 }}>
                    Subject Line <span style={{ color: t.red }}>*</span>
                  </label>
                  <input
                    ref={subjectRef}
                    value={subject}
                    onChange={e => setSubject(e.target.value)}
                    placeholder="e.g. Hi {lead_name}, let's connect"
                    style={{ background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 13, color: t.text, outline: 'none', width: '100%', boxSizing: 'border-box' }}
                  />
                </div>

                {/* Body */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 6 }}>
                    Email Body <span style={{ color: t.red }}>*</span>
                  </label>
                  <textarea
                    ref={bodyRef}
                    value={body}
                    onChange={e => setBody(e.target.value)}
                    placeholder="Write your email body here…"
                    rows={14}
                    style={{ background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 13, color: t.text, outline: 'none', width: '100%', boxSizing: 'border-box', resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.6 }}
                  />
                </div>
              </div>

              {/* Right: Live Preview */}
              <div style={{ padding: 24, overflowY: 'auto', background: panelBg, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Live Preview
                </div>

                {/* Email mock */}
                <div style={{
                  background: isDark ? '#1a1d24' : '#ffffff',
                  border: `1px solid ${divider}`, borderRadius: 10, overflow: 'hidden',
                  boxShadow: isDark ? '0 2px 12px rgba(0,0,0,0.3)' : '0 2px 12px rgba(0,0,0,0.06)',
                }}>
                  {/* Email header bar */}
                  <div style={{ padding: '12px 16px', borderBottom: `1px solid ${divider}`, background: isDark ? '#1e2230' : '#f5f7fa' }}>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                      {['#ff5f57', '#febc2e', '#28c840'].map(c => (
                        <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />
                      ))}
                    </div>
                    <div style={{ fontSize: 11, color: t.textFaint }}>
                      <span style={{ color: t.textMuted }}>From:</span> {SAMPLE['{agent_name}']} &lt;{SAMPLE['{agent_email}']}&gt;
                    </div>
                    <div style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>
                      <span style={{ color: t.textMuted }}>To:</span> {SAMPLE['{lead_name}']}
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: t.text, marginTop: 6 }}>
                      {previewSubject || <span style={{ color: t.textFaint, fontStyle: 'italic' }}>Subject preview…</span>}
                    </div>
                  </div>
                  <div style={{ padding: '16px', fontSize: 13, color: t.text, lineHeight: 1.7, whiteSpace: 'pre-wrap', minHeight: 120 }}>
                    {previewBody || <span style={{ color: t.textFaint, fontStyle: 'italic' }}>Body preview…</span>}
                  </div>
                </div>

                {/* Variable legend */}
                <div style={{ padding: 12, background: isDark ? '#1a1d24' : '#f0f4ff', borderRadius: 8, border: `1px solid ${isDark ? '#2a2d35' : '#dde3f5'}` }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                    Sample Values Used
                  </div>
                  {PLACEHOLDERS.map(p => (
                    <div key={p} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                      <code style={{ color: t.accent, fontFamily: 'monospace' }}>{p}</code>
                      <span style={{ color: t.textMuted }}>{SAMPLE[p]}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Version History */
            <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
              {versLoading ? (
                <div style={{ color: t.textMuted, fontSize: 13 }}>Loading history…</div>
              ) : versions.length === 0 ? (
                <div style={{ color: t.textFaint, fontSize: 13 }}>No version history yet.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Version', 'Subject', 'Status', 'Published', ''].map((h, i) => (
                        <th key={h} style={{
                          padding: '8px 12px', fontSize: 11, fontWeight: 600, color: t.textFaint,
                          textTransform: 'uppercase', letterSpacing: '0.5px',
                          textAlign: i === 4 ? 'right' : 'left',
                          borderBottom: `1px solid ${divider}`,
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map(v => (
                      <tr key={v.id} style={{ borderBottom: `1px solid ${divider}` }}>
                        <td style={{ padding: '10px 12px', fontSize: 13, color: t.text }}>v{v.version_number}</td>
                        <td style={{ padding: '10px 12px', fontSize: 13, color: t.textMuted, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v.subject_template}</td>
                        <td style={{ padding: '10px 12px' }}>
                          {v.is_active && (
                            <span style={{ padding: '2px 8px', fontSize: 11, fontWeight: 600, background: isDark ? '#0d2e1a' : '#dcfce7', color: '#22c55e', borderRadius: 20 }}>
                              Active
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px', fontSize: 12, color: t.textFaint }}>
                          {v.published_at ? new Date(v.published_at).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                          {!v.is_active && (
                            <button
                              onClick={() => handleRollback(v.version_number)}
                              style={{ background: 'none', border: `1px solid ${t.accent}40`, color: t.accent, fontSize: 12, cursor: 'pointer', padding: '4px 10px', borderRadius: 6 }}
                            >
                              Restore
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
    </>
  );
};

// ─── Template Card ────────────────────────────────────────────────────────────

const TemplateCard: React.FC<{
  template: Template;
  onEdit: () => void;
  onDelete: () => void;
}> = ({ template, onEdit, onDelete }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: isDark ? '#1c1f26' : '#ffffff',
        border: `1px solid ${hovered ? t.accent + '60' : (isDark ? '#2a2d35' : '#e5e7eb')}`,
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        transition: 'all 0.15s',
        boxShadow: hovered
          ? `0 0 0 1px ${t.accent}30, 0 4px 20px rgba(0,0,0,0.15)`
          : isDark ? '0 1px 4px rgba(0,0,0,0.2)' : '0 1px 4px rgba(0,0,0,0.05)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
      onClick={onEdit}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {template.name}
          </div>
          <div style={{ fontSize: 12, color: t.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {template.subject}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
          <button
            onClick={onEdit}
            style={{
              padding: '5px 12px', fontSize: 12, fontWeight: 500,
              background: isDark ? '#1e2330' : '#f0f4ff',
              color: t.accent, border: `1px solid ${t.accent}30`,
              borderRadius: 6, cursor: 'pointer',
            }}
          >Edit</button>
          <button
            onClick={onDelete}
            style={{
              padding: '5px 12px', fontSize: 12, fontWeight: 500,
              background: isDark ? '#2d1a1a' : '#fff0f0',
              color: t.red, border: `1px solid ${t.red}30`,
              borderRadius: 6, cursor: 'pointer',
            }}
          >Delete</button>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          fontSize: 11, color: t.textFaint,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
        }}>
          {template.body.slice(0, 80)}{template.body.length > 80 ? '…' : ''}
        </div>
        <div style={{ fontSize: 11, color: t.textFaint, flexShrink: 0 }}>
          {new Date(template.updated_at).toLocaleDateString()}
        </div>
      </div>
    </div>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export const TemplatesPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { success, error: toastError } = useToast();

  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [drawerTarget, setDrawerTarget] = useState<Template | null | 'new'>(undefined as unknown as null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Template | null>(null);
  const [search, setSearch] = useState('');

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<{ templates: Template[] }>(`${API}/templates`);
      setTemplates(res.data.templates ?? []);
      setFetchError(null);
    } catch { setFetchError('Failed to load templates'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const openCreate = () => { setDrawerTarget(null); setDrawerOpen(true); };
  const openEdit = (tmpl: Template) => { setDrawerTarget(tmpl); setDrawerOpen(true); };
  const closeDrawer = () => setDrawerOpen(false);

  const handleSaved = () => { closeDrawer(); fetchTemplates(); };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API}/templates/${deleteTarget.id}`);
      success('Template deleted');
      setTemplates(prev => prev.filter(t => t.id !== deleteTarget.id));
    } catch { toastError('Delete failed'); }
    finally { setDeleteTarget(null); }
  };

  const filtered = templates.filter(tmpl =>
    tmpl.name.toLowerCase().includes(search.toLowerCase()) ||
    tmpl.subject.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Templates</h1>
          <p style={{ fontSize: 13, color: t.textMuted, marginTop: 4 }}>
            Email templates used in pipeline stage actions.
          </p>
        </div>
        <button onClick={openCreate} style={{ padding: '8px 18px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> New Template
        </button>
      </div>

      {/* Search */}
      {templates.length > 0 && (
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search templates…"
          style={{ background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 13, color: t.text, outline: 'none', maxWidth: 320 }}
        />
      )}

      {/* Content */}
      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
          <span style={{ color: t.textMuted, fontSize: 14 }}>Loading templates…</span>
        </div>
      ) : fetchError ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
          <span style={{ color: t.red, fontSize: 14 }}>{fetchError}</span>
        </div>
      ) : filtered.length === 0 ? (
        <div style={{
          background: isDark ? '#1c1f26' : '#ffffff',
          border: `1px solid ${isDark ? '#2a2d35' : '#e5e7eb'}`,
          borderRadius: 12, padding: 48, textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>✉️</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: t.text, marginBottom: 6 }}>
            {search ? 'No templates match your search' : 'No templates yet'}
          </div>
          <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 20 }}>
            {search ? 'Try a different search term.' : 'Create your first email template to use in pipeline actions.'}
          </div>
          {!search && (
            <button onClick={openCreate} style={{ padding: '8px 18px', fontSize: 13, fontWeight: 600, background: t.accent, color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>Create Template</button>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(tmpl => (
            <TemplateCard
              key={tmpl.id}
              template={tmpl}
              onEdit={() => openEdit(tmpl)}
              onDelete={() => setDeleteTarget(tmpl)}
            />
          ))}
        </div>
      )}

      {/* Drawer */}
      {drawerOpen && (
        <TemplateDrawer
          template={drawerTarget as Template | null}
          onClose={closeDrawer}
          onSaved={handleSaved}
        />
      )}

      {/* Delete confirm */}
      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Delete Template"
        message={`Delete "${deleteTarget?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        isDangerous
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
};
