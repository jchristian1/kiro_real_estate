/**
 * Templates Settings — visual pipeline flow.
 * Shows the 4-step email sequence as a journey the lead goes through,
 * with plain-English explanations and inline template management per step.
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import {
  useAgentTemplates, useCreateTemplate, useUpdateTemplate,
  useActivateTemplate, useDeleteTemplate, Template,
} from '../../hooks/useAgentQueries';
import { getAgentErrorMessage } from '../../api/agentApi';

// ── Pipeline step definitions ─────────────────────────────────────────────

const PIPELINE_STEPS = [
  {
    type: 'INITIAL_INVITE',
    step: 1,
    emoji: '👋',
    title: 'First Contact',
    trigger: 'Sent automatically when a new lead comes in',
    description: 'This is the very first email your lead receives. It introduces you and invites them to fill out a short form so you can understand their needs.',
    color: '#6366f1',
    colorBg: 'rgba(99,102,241,0.1)',
  },
  {
    type: 'POST_HOT',
    step: 2,
    emoji: '🔥',
    title: 'Hot Lead Follow-up',
    trigger: 'Sent after the form is submitted — for high-scoring leads',
    description: 'This lead is ready to move fast. They scored high on your criteria (pre-approved, short timeline, wants a tour). Send an urgent, personal response.',
    color: '#ef4444',
    colorBg: 'rgba(239,68,68,0.1)',
  },
  {
    type: 'POST_WARM',
    step: 3,
    emoji: '🌤️',
    title: 'Warm Lead Follow-up',
    trigger: 'Sent after the form is submitted — for mid-scoring leads',
    description: 'This lead is interested but not in a rush. They have some qualifying factors. Send a helpful, informative response with next steps.',
    color: '#f59e0b',
    colorBg: 'rgba(245,158,11,0.1)',
  },
  {
    type: 'POST_NURTURE',
    step: 4,
    emoji: '🌱',
    title: 'Nurture Follow-up',
    trigger: 'Sent after the form is submitted — for lower-scoring leads',
    description: 'This lead is early in their journey. Keep the door open with a friendly, low-pressure message. They may convert later.',
    color: '#10b981',
    colorBg: 'rgba(16,185,129,0.1)',
  },
];

const TONES = ['PROFESSIONAL', 'FRIENDLY', 'SHORT'];

const PLACEHOLDERS = [
  { key: '{lead_name}',   label: 'Lead Name' },
  { key: '{agent_name}',  label: 'Your Name' },
  { key: '{agent_phone}', label: 'Your Phone' },
  { key: '{agent_email}', label: 'Your Email' },
  { key: '{form_link}',   label: 'Form Link' },
];

const SAMPLE = {
  lead_name: 'Jane Smith', agent_name: 'You', agent_phone: '555-0100',
  agent_email: 'you@example.com', form_link: 'https://app.leadsync.io/form/abc',
};

function renderPreview(text: string | undefined | null): string {
  if (!text) return '';
  return text
    .replace(/\{lead_name\}/g, SAMPLE.lead_name)
    .replace(/\{agent_name\}/g, SAMPLE.agent_name)
    .replace(/\{agent_phone\}/g, SAMPLE.agent_phone)
    .replace(/\{agent_email\}/g, SAMPLE.agent_email)
    .replace(/\{form_link\}/g, SAMPLE.form_link);
}

interface EditorState {
  mode: 'edit' | 'new';
  templateId?: number;
  type: string;
  name: string;
  subject: string;
  body: string;
  tone: string;
}

export const TemplatesSettingsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data, isLoading, error: loadError } = useAgentTemplates();
  const createTemplate = useCreateTemplate();
  const updateTemplate = useUpdateTemplate();
  const activateTemplate = useActivateTemplate();
  const deleteTemplate = useDeleteTemplate();

  const [editor, setEditor] = useState<EditorState | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok');

  const flash = (text: string, type: 'ok' | 'err') => {
    setMsg(text); setMsgType(type);
    setTimeout(() => setMsg(''), 3500);
  };

  const getStepTemplates = (type: string) => {
    const all = (data?.templates || []).filter(tpl => tpl.type === type);
    const platformDefault = all.find(tpl => tpl.id == null) ?? null;
    const dbTemplates = all
      .filter(tpl => tpl.id != null)
      .sort((a, b) => (b.is_active ? 1 : 0) - (a.is_active ? 1 : 0));
    return { platformDefault, dbTemplates };
  };

  const openNew = (type: string) => {
    const { platformDefault } = getStepTemplates(type);
    setEditor({
      mode: 'new', type,
      name: '', subject: platformDefault?.subject ?? '', body: platformDefault?.body ?? '', tone: 'PROFESSIONAL',
    });
  };

  const openEdit = (tpl: Template) => setEditor({
    mode: 'edit', templateId: tpl.id, type: tpl.type,
    name: tpl.name || '', subject: tpl.subject, body: tpl.body, tone: tpl.tone || 'PROFESSIONAL',
  });

  const insertPlaceholder = (key: string) => {
    if (!editor) return;
    setEditor(prev => prev ? { ...prev, body: prev.body + key } : prev);
  };

  const handleSave = async () => {
    if (!editor) return;
    if (!editor.name.trim()) { flash('Template name is required', 'err'); return; }
    if (!editor.subject.trim()) { flash('Subject is required', 'err'); return; }
    if (!editor.body.trim()) { flash('Body is required', 'err'); return; }
    setSaving(true);
    try {
      if (editor.mode === 'new') {
        await createTemplate.mutateAsync({
          template_type: editor.type, name: editor.name,
          subject: editor.subject, body: editor.body, tone: editor.tone, activate: false,
        });
        flash('Template created', 'ok');
      } else if (editor.templateId) {
        await updateTemplate.mutateAsync({
          id: editor.templateId, name: editor.name,
          subject: editor.subject, body: editor.body, tone: editor.tone,
        });
        flash('Template saved', 'ok');
      }
      setEditor(null);
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (id: number) => {
    try {
      await activateTemplate.mutateAsync(id);
      flash('Template activated — this will now be used for new leads', 'ok');
    } catch (err) { flash(getAgentErrorMessage(err), 'err'); }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteTemplate.mutateAsync(id);
      flash('Template deleted', 'ok');
    } catch (err) { flash(getAgentErrorMessage(err), 'err'); }
  };

  const toggleExpand = (key: string) =>
    setExpandedId(prev => prev === key ? null : key);

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 13px',
    background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 10, fontSize: 13, color: t.text,
    outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
  };
  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: 11, fontWeight: 600,
    color: t.textFaint, marginBottom: 5, letterSpacing: '0.5px', textTransform: 'uppercase',
  };

  if (isLoading) return <div style={{ color: t.textMuted, fontSize: 14, padding: 20 }}>Loading templates…</div>;
  if (loadError) return <div style={{ color: t.red, fontSize: 14, padding: 20 }}>Failed to load templates. Please refresh.</div>;

  // ── Editor overlay ────────────────────────────────────────────────────────
  if (editor) {
    const stepInfo = PIPELINE_STEPS.find(s => s.type === editor.type)!;
    return (
      <div style={{ maxWidth: 720 }}>
        {msg && (
          <div style={{
            marginBottom: 14, padding: '9px 14px', borderRadius: 9, fontSize: 13,
            background: msgType === 'ok' ? t.greenBg : t.redBg,
            color: msgType === 'ok' ? t.green : t.red,
          }}>{msg}</div>
        )}
        <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '24px' }}>
          {/* Editor header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 18 }}>{stepInfo.emoji}</span>
                <span style={{ fontSize: 15, fontWeight: 700, color: t.text }}>
                  {editor.mode === 'new' ? 'New Template' : 'Edit Template'}
                </span>
                <span style={{
                  padding: '2px 8px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                  background: stepInfo.colorBg, color: stepInfo.color,
                }}>Step {stepInfo.step} — {stepInfo.title}</span>
              </div>
              <div style={{ fontSize: 12, color: t.textFaint }}>{stepInfo.trigger}</div>
            </div>
            <button onClick={() => setEditor(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 20, color: t.textMuted }}>×</button>
          </div>

          <div style={{ marginBottom: 13 }}>
            <label style={labelStyle}>Template Name</label>
            <input value={editor.name} onChange={e => setEditor(p => p ? { ...p, name: e.target.value } : p)}
              placeholder="e.g. Friendly Intro" style={inputStyle} />
          </div>

          <div style={{ marginBottom: 13 }}>
            <label style={labelStyle}>Tone</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {TONES.map(tn => (
                <button key={tn} onClick={() => setEditor(p => p ? { ...p, tone: tn } : p)} style={{
                  padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  background: editor.tone === tn ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgPage,
                  border: `1px solid ${editor.tone === tn ? 'transparent' : t.border}`,
                  color: editor.tone === tn ? '#fff' : t.textMuted,
                }}>{tn.charAt(0) + tn.slice(1).toLowerCase()}</button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 13 }}>
            <label style={labelStyle}>Subject Line</label>
            <input value={editor.subject} onChange={e => setEditor(p => p ? { ...p, subject: e.target.value } : p)}
              placeholder="Email subject line" style={inputStyle} />
          </div>

          <div style={{ marginBottom: 10 }}>
            <label style={labelStyle}>Email Body</label>
            <textarea value={editor.body} onChange={e => setEditor(p => p ? { ...p, body: e.target.value } : p)}
              rows={9} style={{ ...inputStyle, resize: 'vertical' }} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: t.textFaint, marginBottom: 6 }}>Insert placeholder:</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {PLACEHOLDERS.map(ph => (
                <button key={ph.key} onClick={() => insertPlaceholder(ph.key)} style={{
                  padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 500, cursor: 'pointer',
                  background: t.accentBg, border: `1px solid ${t.accent}40`, color: t.accent,
                }}>{ph.label}</button>
              ))}
            </div>
          </div>

          {showPreview && (
            <div style={{ marginBottom: 16, padding: '16px', background: t.bgPage, borderRadius: 10, border: `1px solid ${t.border}` }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Preview with sample data</div>
              <div style={{ fontSize: 12, color: t.textFaint, marginBottom: 12 }}>Lead: {SAMPLE.lead_name} · Agent: {SAMPLE.agent_name}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 3, textTransform: 'uppercase' }}>Subject</div>
              <div style={{ fontSize: 13, color: t.text, fontWeight: 500, marginBottom: 12, padding: '8px 10px', background: t.bgCard, borderRadius: 7 }}>{renderPreview(editor.subject)}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 3, textTransform: 'uppercase' }}>Body</div>
              <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7, padding: '8px 10px', background: t.bgCard, borderRadius: 7 }}>{renderPreview(editor.body)}</div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => setShowPreview(v => !v)} style={{
              padding: '9px 14px', background: t.bgPage, border: `1px solid ${t.border}`,
              borderRadius: 10, fontSize: 13, color: t.textMuted, cursor: 'pointer',
            }}>{showPreview ? 'Hide Preview' : '👁 Preview'}</button>
            <button onClick={() => setEditor(null)} style={{
              padding: '9px 14px', background: t.bgPage, border: `1px solid ${t.border}`,
              borderRadius: 10, fontSize: 13, color: t.textMuted, cursor: 'pointer',
            }}>Cancel</button>
            <button onClick={handleSave} disabled={saving} style={{
              flex: 1, padding: '9px 14px',
              background: saving ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 600, color: '#fff',
              cursor: saving ? 'not-allowed' : 'pointer',
            }}>{saving ? 'Saving…' : 'Save Template'}</button>
          </div>
        </div>
      </div>
    );
  }

  // ── Pipeline view ─────────────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 760 }}>
      {msg && (
        <div style={{
          marginBottom: 14, padding: '9px 14px', borderRadius: 9, fontSize: 13,
          background: msgType === 'ok' ? t.greenBg : t.redBg,
          color: msgType === 'ok' ? t.green : t.red,
          border: `1px solid ${msgType === 'ok' ? t.green : t.red}30`,
        }}>{msg}</div>
      )}

      {/* Page intro */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 6 }}>Your Email Sequence</div>
        <div style={{ fontSize: 13, color: t.textMuted, lineHeight: 1.6 }}>
          When a new lead comes in, your system automatically sends a series of emails. Here you can customize what each email says.
          Each step below is triggered automatically — you just write the message.
        </div>
      </div>

      {/* Pipeline steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {PIPELINE_STEPS.map((step, idx) => {
          const { platformDefault, dbTemplates } = getStepTemplates(step.type);
          const activeTemplate = dbTemplates.find(t => t.is_active) ?? null;
          const usingDefault = !activeTemplate;
          const isLast = idx === PIPELINE_STEPS.length - 1;

          return (
            <div key={step.type}>
              {/* Step card */}
              <div style={{
                background: t.bgCard,
                border: `1px solid ${t.border}`,
                borderRadius: 14,
                overflow: 'hidden',
              }}>
                {/* Step header */}
                <div style={{
                  display: 'flex', alignItems: 'flex-start', gap: 14, padding: '18px 20px',
                  borderBottom: expandedId === step.type ? `1px solid ${t.border}` : 'none',
                }}>
                  {/* Step number + icon */}
                  <div style={{
                    width: 44, height: 44, borderRadius: 12, flexShrink: 0,
                    background: step.colorBg, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: 20,
                  }}>{step.emoji}</div>

                  {/* Step info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3, flexWrap: 'wrap' }}>
                      <span style={{
                        fontSize: 10, fontWeight: 700, color: step.color,
                        background: step.colorBg, padding: '2px 7px', borderRadius: 20,
                      }}>STEP {step.step}</span>
                      <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{step.title}</span>
                      {usingDefault ? (
                        <span style={{ fontSize: 10, fontWeight: 600, color: t.textFaint, background: t.bgBadge, padding: '2px 7px', borderRadius: 20 }}>
                          Using default
                        </span>
                      ) : (
                        <span style={{ fontSize: 10, fontWeight: 700, color: '#10b981', background: 'rgba(16,185,129,0.12)', padding: '2px 7px', borderRadius: 20 }}>
                          ✓ Custom template active
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: t.textFaint, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600 }}>When: </span>{step.trigger}
                    </div>
                    <div style={{ fontSize: 12, color: t.textMuted, lineHeight: 1.5 }}>{step.description}</div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: 8, flexShrink: 0, alignItems: 'center' }}>
                    <button onClick={() => toggleExpand(step.type)} style={{
                      padding: '6px 14px', background: t.bgPage, border: `1px solid ${t.border}`,
                      borderRadius: 8, fontSize: 12, color: t.textMuted, cursor: 'pointer',
                    }}>{expandedId === step.type ? 'Hide' : 'Manage'}</button>
                    <button onClick={() => openNew(step.type)} style={{
                      padding: '6px 14px',
                      background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                      border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 600,
                      color: '#fff', cursor: 'pointer',
                    }}>+ New</button>
                  </div>
                </div>

                {/* Expanded: template list */}
                {expandedId === step.type && (
                  <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>

                    {/* Platform default */}
                    {platformDefault && (
                      <TemplateRow
                        name="Platform Default"
                        subject={platformDefault.subject}
                        body={platformDefault.body}
                        isActive={platformDefault.is_active}
                        isReadOnly
                        t={t}
                      />
                    )}

                    {/* Custom templates */}
                    {dbTemplates.map(tpl => (
                      <TemplateRow
                        key={tpl.id}
                        name={tpl.name || 'My Template'}
                        subject={tpl.subject}
                        body={tpl.body}
                        isActive={tpl.is_active}
                        version={tpl.version}
                        onActivate={!tpl.is_active && tpl.id ? () => handleActivate(tpl.id!) : undefined}
                        onEdit={() => openEdit(tpl)}
                        onDelete={tpl.id ? () => handleDelete(tpl.id!) : undefined}
                        t={t}
                      />
                    ))}

                    {dbTemplates.length === 0 && (
                      <div style={{ fontSize: 12, color: t.textFaint, padding: '4px 0 8px' }}>
                        No custom templates yet — the platform default is being used. Click "+ New" to write your own.
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Connector arrow between steps */}
              {!isLast && (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '6px 0' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                    <div style={{ width: 1, height: 12, background: t.border }} />
                    <div style={{ fontSize: 12, color: t.textFaint }}>↓</div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{
        marginTop: 24, padding: '14px 16px', background: t.bgCard,
        border: `1px solid ${t.border}`, borderRadius: 12,
        display: 'flex', gap: 20, flexWrap: 'wrap',
      }}>
        <div style={{ fontSize: 12, color: t.textFaint, fontWeight: 600, alignSelf: 'center' }}>How it works:</div>
        <div style={{ fontSize: 12, color: t.textMuted }}>📥 Lead arrives → Step 1 fires immediately</div>
        <div style={{ fontSize: 12, color: t.textMuted }}>📋 Lead fills form → Step 2, 3, or 4 fires based on their score</div>
        <div style={{ fontSize: 12, color: t.textMuted }}>✏️ "Custom template active" means your version is being used</div>
      </div>
    </div>
  );
};

// ── TemplateRow sub-component ─────────────────────────────────────────────

interface TemplateRowProps {
  name: string;
  subject: string;
  body: string;
  isActive: boolean;
  isReadOnly?: boolean;
  version?: number;
  onActivate?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  t: ReturnType<typeof getTokens>;
}

const TemplateRow: React.FC<TemplateRowProps> = ({
  name, subject, body, isActive, isReadOnly, version,
  onActivate, onEdit, onDelete, t,
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{
      background: t.bgPage,
      border: `1px solid ${isActive ? '#10b98140' : t.border}`,
      borderRadius: 10,
      overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2, flexWrap: 'wrap' }}>
            {isActive && (
              <span style={{ fontSize: 10, fontWeight: 700, color: '#10b981', background: 'rgba(16,185,129,0.12)', padding: '1px 7px', borderRadius: 20 }}>
                ✓ Active
              </span>
            )}
            <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{name}</span>
            {version !== undefined && version > 0 && (
              <span style={{ fontSize: 11, color: t.textFaint }}>v{version}</span>
            )}
            {isReadOnly && (
              <span style={{ fontSize: 10, color: t.textFaint, background: t.bgBadge, padding: '1px 7px', borderRadius: 20 }}>read-only</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: t.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {subject}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <button onClick={() => setExpanded(v => !v)} style={{
            padding: '4px 10px', background: 'none', border: `1px solid ${t.border}`,
            borderRadius: 7, fontSize: 11, color: t.textMuted, cursor: 'pointer',
          }}>{expanded ? 'Hide' : 'Preview'}</button>

          {onActivate && (
            <button onClick={onActivate} style={{
              padding: '4px 10px', background: t.accentBg, border: `1px solid ${t.accent}40`,
              borderRadius: 7, fontSize: 11, fontWeight: 600, color: t.accent, cursor: 'pointer',
            }}>Use This</button>
          )}

          {!isReadOnly && onEdit && (
            <button onClick={onEdit} style={{
              padding: '4px 10px', background: 'none', border: `1px solid ${t.border}`,
              borderRadius: 7, fontSize: 11, color: t.textMuted, cursor: 'pointer',
            }}>Edit</button>
          )}

          {!isReadOnly && onDelete && (
            <button onClick={onDelete} style={{
              padding: '4px 10px', background: t.redBg, border: `1px solid ${t.red}30`,
              borderRadius: 7, fontSize: 11, color: t.red, cursor: 'pointer',
            }}>Delete</button>
          )}
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '12px 14px', borderTop: `1px solid ${t.border}`, background: t.bgCard }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 3, textTransform: 'uppercase' }}>Subject</div>
          <div style={{ fontSize: 13, color: t.text, fontWeight: 500, marginBottom: 10 }}>{renderPreview(subject)}</div>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 3, textTransform: 'uppercase' }}>Body</div>
          <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{renderPreview(body)}</div>
        </div>
      )}
    </div>
  );
};
