/**
 * Step 5 — Template Setup: 4 template cards, tone selector, inline editor, live preview.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../contexts/ThemeContext';
import { getTokens } from '../../../utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';

interface Props { goBack: () => void; }

const TEMPLATE_TYPES = [
  { type: 'initial_outreach', label: 'Initial Outreach', desc: 'First email sent when a new lead is detected' },
  { type: 'follow_up',        label: 'Follow Up',        desc: 'Sent if no response after initial outreach' },
  { type: 'post_form',        label: 'Post Form',        desc: 'Sent after lead submits the qualification form' },
  { type: 'appointment',      label: 'Appointment',      desc: 'Sent when scheduling a tour or meeting' },
];

const TONES = ['professional', 'friendly', 'concise'];

const SAMPLE_LEAD = { lead_name: 'Jane Smith', agent_name: 'You', agent_phone: '555-0100', agent_email: 'you@example.com', form_link: 'https://app.leadsync.io/form/abc123' };

const DEFAULT_TEMPLATES: Record<string, { subject: string; body: string }> = {
  initial_outreach: {
    subject: 'Hi {lead_name}, I saw your inquiry',
    body: 'Hi {lead_name},\n\nI noticed your interest and would love to help. I\'m {agent_name} and I specialize in this area.\n\nFeel free to reach me at {agent_phone} or reply to this email.\n\nBest,\n{agent_name}',
  },
  follow_up: {
    subject: 'Following up — {lead_name}',
    body: 'Hi {lead_name},\n\nJust checking in to see if you had any questions. I\'m here to help!\n\n{agent_name}\n{agent_phone}',
  },
  post_form: {
    subject: 'Thanks for completing the form, {lead_name}!',
    body: 'Hi {lead_name},\n\nThank you for filling out the qualification form. I\'ll review your answers and be in touch shortly.\n\n{agent_name}',
  },
  appointment: {
    subject: 'Let\'s schedule a tour, {lead_name}',
    body: 'Hi {lead_name},\n\nI\'d love to show you around. Please use this link to pick a time: {form_link}\n\nLooking forward to meeting you!\n{agent_name}',
  },
};

function renderPreview(text: string): string {
  return text
    .replace(/{lead_name}/g, SAMPLE_LEAD.lead_name)
    .replace(/{agent_name}/g, SAMPLE_LEAD.agent_name)
    .replace(/{agent_phone}/g, SAMPLE_LEAD.agent_phone)
    .replace(/{agent_email}/g, SAMPLE_LEAD.agent_email)
    .replace(/{form_link}/g, SAMPLE_LEAD.form_link);
}

export const Step5Templates: React.FC<Props> = ({ goBack }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const [activeType, setActiveType] = useState(TEMPLATE_TYPES[0].type);
  const [tone, setTone] = useState('professional');
  const [templates, setTemplates] = useState<Record<string, { subject: string; body: string }>>(DEFAULT_TEMPLATES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPreview, setShowPreview] = useState(false);

  const current = templates[activeType];
  const update = (field: 'subject' | 'body', val: string) =>
    setTemplates(prev => ({ ...prev, [activeType]: { ...prev[activeType], [field]: val } }));

  const handleSubmit = async () => {
    setError(''); setLoading(true);
    try {
      await agentApi.put('/agent/onboarding/templates', {
        templates: Object.entries(templates).map(([type, { subject, body }]) => ({ type, subject, body, tone })),
      });
      navigate('/agent/onboarding/go-live');
    } catch (err) {
      setError(getAgentErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '11px 14px',
    background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 11, fontSize: 13, color: t.text,
    outline: 'none', boxSizing: 'border-box' as const, transition: 'border-color 0.15s',
    fontFamily: 'inherit',
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 22, padding: '36px 32px' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px', marginBottom: 6 }}>Email Templates</div>
        <div style={{ fontSize: 13, color: t.textMuted }}>Customize the emails sent to your leads. Use {'{'}placeholders{'}'} for personalization.</div>
      </div>

      {/* Tone selector */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 8, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Tone</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {TONES.map(tn => (
            <button key={tn} type="button" onClick={() => setTone(tn)} style={{
              padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500, cursor: 'pointer',
              background: tone === tn ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgCard,
              border: `1px solid ${tone === tn ? 'transparent' : t.border}`,
              color: tone === tn ? '#fff' : t.textMuted,
              transition: 'all 0.15s',
            }}>{tn.charAt(0).toUpperCase() + tn.slice(1)}</button>
          ))}
        </div>
      </div>

      {/* Template tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {TEMPLATE_TYPES.map(tt => (
          <button key={tt.type} type="button" onClick={() => setActiveType(tt.type)} style={{
            padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500, cursor: 'pointer',
            background: activeType === tt.type ? t.accentBg : 'transparent',
            border: `1px solid ${activeType === tt.type ? t.accent : t.border}`,
            color: activeType === tt.type ? t.accent : t.textMuted,
            transition: 'all 0.15s',
          }}>{tt.label}</button>
        ))}
      </div>

      {/* Editor */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Subject</div>
        <input value={current.subject} onChange={e => update('subject', e.target.value)} style={inputStyle}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Body</div>
        <textarea value={current.body} onChange={e => update('body', e.target.value)} rows={6}
          style={{ ...inputStyle, resize: 'vertical' as const }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>

      {/* Preview toggle */}
      <button type="button" onClick={() => setShowPreview(v => !v)} style={{
        marginBottom: 16, padding: '8px 14px', background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 9, fontSize: 12, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
      }}>
        {showPreview ? 'Hide Preview' : 'Show Preview'}
      </button>

      {showPreview && (
        <div style={{ marginBottom: 20, padding: '16px', background: t.bgPage, border: `1px solid ${t.border}`, borderRadius: 11 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: t.textFaint, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Preview</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: t.text, marginBottom: 8 }}>{renderPreview(current.subject)}</div>
          <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{renderPreview(current.body)}</div>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 10 }}>
        <button type="button" onClick={goBack} style={{
          flex: 1, padding: '12px', background: t.bgCard, border: `1px solid ${t.border}`,
          borderRadius: 11, fontSize: 14, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
        }}>Back</button>
        <button type="button" onClick={handleSubmit} disabled={loading} style={{
          flex: 2, padding: '12px',
          background: loading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
          cursor: loading ? 'not-allowed' : 'pointer',
          boxShadow: loading ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
        }}>
          {loading ? 'Saving…' : 'Continue'}
        </button>
      </div>
    </div>
  );
};
