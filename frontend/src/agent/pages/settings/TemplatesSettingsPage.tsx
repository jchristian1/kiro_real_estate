/**
 * Templates Settings — per-pipeline-step template library.
 * Shows platform default (read-only) + all agent templates.
 * Agent can create, edit, delete, activate, and preview any template.
 */

import React, { useState } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';
import { getTokens } from '../../../utils/theme';
import {
  useAgentTemplates, useCreateTemplate, useUpdateTemplate,
  useActivateTemplate, useDeleteTemplate, Template,
} from '../../hooks/useAgentQueries';
import { getAgentErrorMessage } from '../../api/agentApi';

const PIPELINE_STEPS = [
  { type: 'INITIAL_INVITE', label: 'Initial Outreach',    desc: 'Sent when a new lead is detected' },
  { type: 'POST_HOT',       label: 'Post Form — Hot',     desc: 'Sent after form submitted, score ≥ hot threshold' },
  { type: 'POST_WARM',      label: 'Post Form — Warm',    desc: 'Sent after form submitted, warm score' },
  { type: 'POST_NURTURE',   label: 'Post Form — Nurture', desc: 'Sent after form submitted, nurture score' },
];

const TONES = ['PROFESSIONAL', 'FRIENDLY', 'SHORT'];

const PLACEHOLDERS = [
  { key: '{lead_name}',   label: 'Lead Name' },
  { key: '{agent_name}',  label: 'Agent Name' },
  { key: '{agent_phone}', label: 'Phone' },
  { key: '{agent_email}', label: 'Email' },
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

  const [activeStep, setActiveStep] = useState('INITIAL_INVITE');
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

  // All templates for the active step
  const allTemplates: Template[] = (data?.templates || []).filter(tpl => tpl.type === activeStep);
  // Platform default is the one with id=null
  const platformDefault = allTemplates.find(tpl => tpl.id == null) ?? null;
  // All DB templates (is_custom=true), sorted: active first
  const dbTemplates = allTemplates
    .filter(tpl => tpl.id != null)
    .sort((a, b) => (b.is_active ? 1 : 0) - (a.is_active ? 1 : 0));

  const openNew = () => setEditor({
    mode: 'new', type: activeStep,
    name: '', subject: platformDefault?.subject ?? '', body: platformDefault?.body ?? '', tone: 'PROFESSIONAL',
  });

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
  const cardStyle: React.CSSProperties = {
    background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '18px',
  };

  const currentStep = PIPELINE_STEPS.find(s => s.type === activeStep)!;

  if (isLoading) return <div style={{ color: t.textMuted, fontSize: 14, padding: 20 }}>Loading templates…</div>;
  if (loadError) return <div style={{ color: t.red, fontSize: 14, padding: 20 }}>Failed to load templates. Please refresh.</div>;

  return (
    <div style={{ maxWidth: 800 }}>
      {msg && (
        <div style={{
          marginBottom: 14, padding: '9px 14px', borderRadius: 9, fontSize: 13,
          background: msgType === 'ok' ? t.greenBg : t.redBg,
          color: msgType === 'ok' ? t.green : t.red,
          border: `1px solid ${msgType === 'ok' ? t.green : t.red}30`,
        }}>{msg}</div>
      )}

      {/* Pipeline step tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {PIPELINE_STEPS.map(step => (
          <button key={step.type} onClick={() => { setActiveStep(step.type); setEditor(null); setExpandedId(null); }} style={{
            padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 500, cursor: 'pointer',
            background: activeStep === step.type ? t.accentBg : t.bgCard,
            border: `1.5px solid ${activeStep === step.type ? t.accent : t.border}`,
            color: activeStep === step.type ? t.accent : t.textMuted,
          }}>
            {step.label}
          </button>
        ))}
      </div>

      {/* Editor panel */}
      {editor ? (
        <div style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>
              {editor.mode === 'new' ? 'New Template' : 'Edit Template'}
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
                  padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  background: editor.tone === tn ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgPage,
                  border: `1px solid ${editor.tone === tn ? 'transparent' : t.border}`,
                  color: editor.tone === tn ? '#fff' : t.textMuted,
                }}>{tn.charAt(0) + tn.slice(1).toLowerCase()}</button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 13 }}>
            <label style={labelStyle}>Subject</label>
            <input value={editor.subject} onChange={e => setEditor(p => p ? { ...p, subject: e.target.value } : p)}
              placeholder="Email subject line" style={inputStyle} />
          </div>

          <div style={{ marginBottom: 10 }}>
            <label style={labelStyle}>Body</label>
            <textarea value={editor.body} onChange={e => setEditor(p => p ? { ...p, body: e.target.value } : p)}
              rows={8} style={{ ...inputStyle, resize: 'vertical' }} />
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
            <div style={{ marginBottom: 16, padding: '14px', background: t.bgPage, borderRadius: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Subject Preview</div>
              <div style={{ fontSize: 13, color: t.text, marginBottom: 12 }}>{renderPreview(editor.subject)}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Body Preview</div>
              <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{renderPreview(editor.body)}</div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => setShowPreview(v => !v)} style={{
              padding: '9px 14px', background: t.bgPage, border: `1px solid ${t.border}`,
              borderRadius: 10, fontSize: 13, color: t.textMuted, cursor: 'pointer',
            }}>{showPreview ? 'Hide Preview' : 'Preview'}</button>
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
      ) : (
        <>
          {/* Step header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>{currentStep.label}</div>
              <div style={{ fontSize: 12, color: t.textFaint, marginTop: 2 }}>{currentStep.desc}</div>
            </div>
            <button onClick={openNew} style={{
              padding: '8px 16px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 10, fontSize: 12, fontWeight: 600, color: '#fff',
              cursor: 'pointer', boxShadow: '0 2px 8px rgba(99,102,241,0.3)',
            }}>+ New Template</button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

            {/* Platform default — always shown, read-only */}
            {platformDefault && (
              <TemplateCard
                id="platform-default"
                name="Platform Default"
                subject={platformDefault.subject}
                body={platformDefault.body}
                isActive={platformDefault.is_active}
                isReadOnly
                badge="read-only"
                isExpanded={expandedId === 'platform-default'}
                onToggleExpand={() => toggleExpand('platform-default')}
                t={t}
              />
            )}

            {/* All DB templates */}
            {dbTemplates.map(tpl => (
              <TemplateCard
                key={tpl.id}
                id={String(tpl.id)}
                name={tpl.name || 'My Template'}
                subject={tpl.subject}
                body={tpl.body}
                isActive={tpl.is_active}
                version={tpl.version}
                isExpanded={expandedId === String(tpl.id)}
                onToggleExpand={() => toggleExpand(String(tpl.id))}
                onActivate={!tpl.is_active && tpl.id ? () => handleActivate(tpl.id!) : undefined}
                onEdit={() => openEdit(tpl)}
                onDelete={tpl.id ? () => handleDelete(tpl.id!) : undefined}
                t={t}
              />
            ))}

            {dbTemplates.length === 0 && (
              <div style={{ fontSize: 13, color: t.textFaint, padding: '10px 0' }}>
                No custom templates yet — the platform default will be used. Click "+ New Template" to create one.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

// ── TemplateCard sub-component ────────────────────────────────────────────

interface TemplateCardProps {
  id: string;
  name: string;
  subject: string;
  body: string;
  isActive: boolean;
  isReadOnly?: boolean;
  badge?: string;
  version?: number;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onActivate?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  t: ReturnType<typeof getTokens>;
}

const TemplateCard: React.FC<TemplateCardProps> = ({
  name, subject, body, isActive, isReadOnly, badge, version,
  isExpanded, onToggleExpand, onActivate, onEdit, onDelete, t,
}) => {
  const cardStyle: React.CSSProperties = {
    background: t.bgCard,
    border: `1px solid ${isActive ? '#10b98140' : t.border}`,
    borderRadius: 14, padding: '16px',
  };

  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            {isActive && (
              <span style={{ padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: '#10b98120', color: '#10b981' }}>
                ✓ Active
              </span>
            )}
            <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{name}</span>
            {version !== undefined && version > 0 && (
              <span style={{ fontSize: 11, color: t.textFaint }}>v{version}</span>
            )}
            {badge && (
              <span style={{
                padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 600,
                background: t.bgPage, border: `1px solid ${t.border}`, color: t.textFaint,
              }}>{badge}</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: t.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {subject}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6, flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button onClick={onToggleExpand} style={{
            padding: '5px 12px', background: t.bgPage, border: `1px solid ${t.border}`,
            borderRadius: 8, fontSize: 12, color: t.textMuted, cursor: 'pointer',
          }}>{isExpanded ? 'Hide' : 'Preview'}</button>

          {onActivate && (
            <button onClick={onActivate} style={{
              padding: '5px 12px', background: t.accentBg, border: `1px solid ${t.accent}40`,
              borderRadius: 8, fontSize: 12, fontWeight: 600, color: t.accent, cursor: 'pointer',
            }}>Use This</button>
          )}

          {!isReadOnly && onEdit && (
            <button onClick={onEdit} style={{
              padding: '5px 10px', background: t.bgCard, border: `1px solid ${t.border}`,
              borderRadius: 8, fontSize: 12, color: t.textMuted, cursor: 'pointer',
            }}>Edit</button>
          )}

          {!isReadOnly && onDelete && (
            <button onClick={onDelete} style={{
              padding: '5px 10px', background: t.redBg, border: `1px solid ${t.red}30`,
              borderRadius: 8, fontSize: 12, color: t.red, cursor: 'pointer',
            }}>Delete</button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div style={{ marginTop: 14, padding: '14px', background: t.bgPage, borderRadius: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Subject</div>
          <div style={{ fontSize: 13, color: t.text, fontWeight: 500, marginBottom: 12 }}>{renderPreview(subject)}</div>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Body</div>
          <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{renderPreview(body)}</div>
        </div>
      )}
    </div>
  );
};
