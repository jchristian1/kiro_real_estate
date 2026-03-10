/**
 * Templates Settings — 4 template cards, inline editor, live preview, save/revert.
 */

import React, { useState, useEffect } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';
import { getTokens } from '../../../utils/theme';
import { useAgentTemplates, useSaveTemplate, useDeleteTemplate } from '../../hooks/useAgentQueries';

import { getAgentErrorMessage } from '../../api/agentApi';

const SAMPLE = { lead_name: 'Jane Smith', agent_name: 'You', agent_phone: '555-0100', agent_email: 'you@example.com', form_link: 'https://app.leadsync.io/form/abc' };
const TONES = ['professional', 'friendly', 'concise'];

function renderPreview(text: string): string {
  return text
    .replace(/{lead_name}/g, SAMPLE.lead_name)
    .replace(/{agent_name}/g, SAMPLE.agent_name)
    .replace(/{agent_phone}/g, SAMPLE.agent_phone)
    .replace(/{agent_email}/g, SAMPLE.agent_email)
    .replace(/{form_link}/g, SAMPLE.form_link);
}

const TYPE_LABELS: Record<string, string> = {
  initial_outreach: 'Initial Outreach',
  follow_up:        'Follow Up',
  post_form:        'Post Form',
  appointment:      'Appointment',
};

export const TemplatesSettingsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data, isLoading } = useAgentTemplates();
  const saveTemplate = useSaveTemplate();
  const deleteTemplate = useDeleteTemplate();

  const [active, setActive] = useState('initial_outreach');
  const [edits, setEdits] = useState<Record<string, { subject: string; body: string; tone: string }>>({});
  const [showPreview, setShowPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok');

  const templates = data?.templates || [];

  useEffect(() => {
    if (templates.length && !Object.keys(edits).length) {
      const init: typeof edits = {};
      templates.forEach(tpl => { init[tpl.type] = { subject: tpl.subject, body: tpl.body, tone: tpl.tone }; });
      setEdits(init);
    }
  }, [templates]);

  const current = edits[active] || { subject: '', body: '', tone: 'professional' };
  const tplMeta = templates.find(t => t.type === active);

  const update = (field: 'subject' | 'body' | 'tone', val: string) =>
    setEdits(prev => ({ ...prev, [active]: { ...prev[active], [field]: val } }));

  const flash = (text: string, type: 'ok' | 'err') => {
    setMsg(text); setMsgType(type);
    setTimeout(() => setMsg(''), 3000);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveTemplate.mutateAsync({ type: active, ...current });
      flash('Saved successfully', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setSaving(false);
    }
  };

  const handleRevert = async () => {
    setReverting(true);
    try {
      await deleteTemplate.mutateAsync(active);
      flash('Reverted to default', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setReverting(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '11px 14px',
    background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 11, fontSize: 13, color: t.text,
    outline: 'none', boxSizing: 'border-box' as const, transition: 'border-color 0.15s', fontFamily: 'inherit',
  };

  if (isLoading) return <div style={{ color: t.textMuted, fontSize: 14 }}>Loading templates…</div>;

  return (
    <div>
      {/* Template tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {Object.entries(TYPE_LABELS).map(([type, label]) => {
          const tpl = templates.find(t => t.type === type);
          return (
            <button key={type} onClick={() => setActive(type)} style={{
              padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 500, cursor: 'pointer',
              background: active === type ? t.accentBg : t.bgCard,
              border: `1.5px solid ${active === type ? t.accent : t.border}`,
              color: active === type ? t.accent : t.textMuted, transition: 'all 0.15s',
            }}>
              {label}
              {tpl && <span style={{ marginLeft: 6, fontSize: 10, color: t.textFaint }}>v{tpl.version}</span>}
            </button>
          );
        })}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: showPreview ? '1fr 1fr' : '1fr', gap: 20 }}>
        {/* Editor */}
        <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '22px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>{TYPE_LABELS[active]}</div>
            {tplMeta && (
              <span style={{ fontSize: 11, color: t.textFaint }}>
                Version {tplMeta.version} · {tplMeta.is_active ? 'Active' : 'Inactive'}
              </span>
            )}
          </div>

          {/* Tone */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 8, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Tone</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {TONES.map(tn => (
                <button key={tn} onClick={() => update('tone', tn)} style={{
                  padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  background: current.tone === tn ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgCard,
                  border: `1px solid ${current.tone === tn ? 'transparent' : t.border}`,
                  color: current.tone === tn ? '#fff' : t.textMuted, transition: 'all 0.15s',
                }}>{tn.charAt(0).toUpperCase() + tn.slice(1)}</button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Subject</div>
            <input value={current.subject} onChange={e => update('subject', e.target.value)} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Body</div>
            <textarea value={current.body} onChange={e => update('body', e.target.value)} rows={8}
              style={{ ...inputStyle, resize: 'vertical' as const }}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>

          {msg && (
            <div style={{ marginBottom: 14, padding: '9px 14px', borderRadius: 9, fontSize: 13,
              background: msgType === 'ok' ? t.greenBg : t.redBg,
              color: msgType === 'ok' ? t.green : t.red,
              border: `1px solid ${msgType === 'ok' ? t.green : t.red}30`,
            }}>{msg}</div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => setShowPreview(v => !v)} style={{
              padding: '9px 16px', background: t.bgCard, border: `1px solid ${t.border}`,
              borderRadius: 10, fontSize: 13, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
            }}>{showPreview ? 'Hide Preview' : 'Preview'}</button>
            <button onClick={handleRevert} disabled={reverting} style={{
              padding: '9px 16px', background: t.bgCard, border: `1px solid ${t.border}`,
              borderRadius: 10, fontSize: 13, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
              opacity: reverting ? 0.6 : 1,
            }}>{reverting ? '…' : 'Revert to Default'}</button>
            <button onClick={handleSave} disabled={saving} style={{
              flex: 1, padding: '9px 16px',
              background: saving ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 600, color: '#fff',
              cursor: saving ? 'not-allowed' : 'pointer',
              boxShadow: saving ? 'none' : '0 2px 8px rgba(99,102,241,0.3)',
            }}>{saving ? 'Saving…' : 'Save'}</button>
          </div>
        </div>

        {/* Preview */}
        {showPreview && (
          <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '22px' }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16 }}>Preview</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Subject</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 16, padding: '10px 14px', background: t.bgPage, borderRadius: 9 }}>
              {renderPreview(current.subject)}
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Body</div>
            <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7, padding: '12px 14px', background: t.bgPage, borderRadius: 9 }}>
              {renderPreview(current.body)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
