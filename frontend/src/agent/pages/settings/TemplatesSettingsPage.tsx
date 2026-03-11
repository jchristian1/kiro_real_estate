/**
 * Templates Settings — multi-template library with per-step activation.
 * Default templates are read-only; custom templates can be edited/deleted.
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

function renderPreview(text: string): string {
  return text
    .replace(/{lead_name}/g, SAMPLE.lead_name)
    .replace(/{agent_name}/g, SAMPLE.agent_name)
    .replace(/{agent_phone}/g, SAMPLE.agent_phone)
    .replace(/{agent_email}/g, SAMPLE.agent_email)
    .replace(/{form_link}/g, SAMPLE.form_link);
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
  const { data, isLoading } = useAgentTemplates();
  const createTemplate = useCreateTemplate();
  const updateTemplate = useUpdateTemplate();
  const activateTemplate = useActivateTemplate();
  const deleteTemplate = useDeleteTemplate();

  const [activeStep, setActiveStep] = useState('INITIAL_INVITE');
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null); // 'default' or template id
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok');

  const flash = (text: string, type: 'ok' | 'err') => {
    setMsg(text); setMsgType(type);
    setTimeout(() => setMsg(''), 3000);
  };

  const templates = data?.templates || [];
  const stepTemplates = templates.filter(tpl => tpl.type === activeStep);
  // The default entry (is_custom=false) — always present
  const defaultTpl = stepTemplates.find(tpl => !tpl.is_custom) ?? null;
  // Custom templates
  const customTemplates = stepTemplates.filter(tpl => tpl.is_custom);
  // Active template (custom active, or default if no custom active)
  const activeTpl = customTemplates.find(tpl => tpl.is_active) ?? defaultTpl;

  const openNew = () => setEditor({
    mode: 'new', type: activeStep,
    name: '', subject: defaultTpl?.subject ?? '', body: defaultTpl?.body ?? '', tone: 'PROFESSIONAL',
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
      flash('Template activated', 'ok');
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

  const inputStyle = {
    width: '100%', padding: '10px 13px',
    background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 10, fontSize: 13, color: t.text,
    outline: 'none', boxSizing: 'border-box' as const, fontFamily: 'inherit',
  };
  const labelStyle = {
    display: 'block', fontSize: 11, fontWeight: 600 as const,
    color: t.textFaint, marginBottom: 5, letterSpacing: '0.5px', textTransform: 'uppercase' as const,
  };
  const cardStyle = {
    background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '18px', marginBottom: 16,
  };

  if (isLoading) return <div style={{ color: t.textMuted, fontSize: 14 }}>Loading templates…</div>;

  const currentStep = PIPELINE_STEPS.find(s => s.type === activeStep)!;

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
          <button key={step.type} onClick={() => { setActiveStep(step.type); setEditor(null); }} style={{
            padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 500, cursor: 'pointer',
            background: activeStep === step.type ? t.accentBg : t.bgCard,
            border: `1.5px solid ${activeStep === step.type ? t.accent : t.border}`,
            color: activeStep === step.type ? t.accent : t.textMuted,
          }}>
            {step.label}
          </button>
        ))}
      </div>

      {/* Editor */}
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

          {/* Placeholder chips */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: t.textFaint, marginBottom: 6 }}>Insert placeholder:</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {PLACEHOLDERS.map(p => (
                <button key={p.key} onClick={() => insertPlaceholder(p.key)} style={{
                  padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 500, cursor: 'pointer',
                  background: t.accentBg, border: `1px solid ${t.accent}40`, color: t.accent,
                }}>{p.label}</button>
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

          {/* Template library — default first, then custom */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

            {/* Default template — always shown, read-only */}
            {defaultTpl && (() => {
              const isActive = activeTpl === defaultTpl;
              const isExpanded = expandedId === 'default';
              return (
                <div style={{
                  ...cardStyle, marginBottom: 0,
                  border: `1px solid ${isActive ? '#10b98140' : t.border}`,
                  opacity: 1,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        {isActive && (
                          <span style={{ padding: '1px 7px', borderRadius: 20, fontSize: 10, fontWeight: 600, background: '#10b98120', color: '#10b981' }}>Active</span>
                        )}
                        <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Default</span>
                        <span style={{
                          padding: '1px 7px', borderRadius: 20, fontSize: 10, fontWeight: 600,
                          background: t.bgPage, border: `1px solid ${t.border}`, color: t.textFaint,
                        }}>Platform default · read-only</span>
                      </div>
                      <div style={{ fontSize: 12, color: t.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {defaultTpl.subject}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                      <button onClick={() => toggleExpand('default')} style={{
                        padding: '5px 12px', background: t.bgPage, border: `1px solid ${t.border}`,
                        borderRadius: 8, fontSize: 12, color: t.textMuted, cursor: 'pointer',
                      }}>{isExpanded ? 'Hide' : 'Preview'}</button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{ marginTop: 14, padding: '14px', background: t.bgPage, borderRadius: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Subject</div>
                      <div style={{ fontSize: 13, color: t.text, fontWeight: 500, marginBottom: 12 }}>{renderPreview(defaultTpl.subject)}</div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Body</div>
                      <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{renderPreview(defaultTpl.body)}</div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Custom templates */}
            {customTemplates.map(tpl => {
              const key = String(tpl.id);
              const isExpanded = expandedId === key;
              return (
                <div key={tpl.id} style={{
                  ...cardStyle, marginBottom: 0,
                  border: `1px solid ${tpl.is_active ? t.accent + '40' : t.border}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        {tpl.is_active && (
                          <span style={{ padding: '1px 7px', borderRadius: 20, fontSize: 10, fontWeight: 600, background: '#10b98120', color: '#10b981' }}>Active</span>
                        )}
                        <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{tpl.name || 'Untitled'}</span>
                        <span style={{ fontSize: 11, color: t.textFaint }}>v{tpl.version}</span>
                      </div>
                      <div style={{ fontSize: 12, color: t.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {tpl.subject}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                      <button onClick={() => toggleExpand(key)} style={{
                        padding: '5px 12px', background: t.bgPage, border: `1px solid ${t.border}`,
                        borderRadius: 8, fontSize: 12, color: t.textMuted, cursor: 'pointer',
                      }}>{isExpanded ? 'Hide' : 'Preview'}</button>
                      {!tpl.is_active && tpl.id && (
                        <button onClick={() => handleActivate(tpl.id!)} style={{
                          padding: '5px 12px', background: t.accentBg, border: `1px solid ${t.accent}40`,
                          borderRadius: 8, fontSize: 12, fontWeight: 500, color: t.accent, cursor: 'pointer',
                        }}>Use This</button>
                      )}
                      <button onClick={() => openEdit(tpl)} style={{
                        padding: '5px 10px', background: t.bgCard, border: `1px solid ${t.border}`,
                        borderRadius: 8, fontSize: 12, color: t.textMuted, cursor: 'pointer',
                      }}>Edit</button>
                      {tpl.id && (
                        <button onClick={() => handleDelete(tpl.id!)} style={{
                          padding: '5px 10px', background: t.redBg, border: `1px solid ${t.red}30`,
                          borderRadius: 8, fontSize: 12, color: t.red, cursor: 'pointer',
                        }}>Delete</button>
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{ marginTop: 14, padding: '14px', background: t.bgPage, borderRadius: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Subject</div>
                      <div style={{ fontSize: 13, color: t.text, fontWeight: 500, marginBottom: 12 }}>{renderPreview(tpl.subject)}</div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 4, textTransform: 'uppercase' }}>Body</div>
                      <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{renderPreview(tpl.body)}</div>
                    </div>
                  )}
                </div>
              );
            })}

            {customTemplates.length === 0 && (
              <div style={{ fontSize: 13, color: t.textFaint, padding: '10px 0' }}>
                No custom templates yet — the default will be used. Click "+ New Template" to create one.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
