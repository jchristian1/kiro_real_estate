/**
 * Account Settings — personal preferences only (PR A1).
 *
 * Gmail connection, watcher toggle, and subscription management removed.
 * Inbox and watcher management is handled by company admins.
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';

export const AccountSettingsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  const [serviceArea, setServiceArea] = useState('');
  const [timezone, setTimezone] = useState('');
  const [quietStart, setQuietStart] = useState('');
  const [quietEnd, setQuietEnd] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok');

  const flash = (text: string, type: 'ok' | 'err') => {
    setMsg(text); setMsgType(type);
    setTimeout(() => setMsg(''), 4000);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await agentApi.put('/agent/account/preferences', {
        ...(serviceArea ? { service_area: serviceArea } : {}),
        ...(timezone ? { timezone } : {}),
        ...(quietStart ? { quiet_hours_start: quietStart } : {}),
        ...(quietEnd ? { quiet_hours_end: quietEnd } : {}),
      });
      flash('Preferences saved', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '11px 14px',
    background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 11, fontSize: 14, color: t.text,
    outline: 'none', boxSizing: 'border-box' as const, transition: 'border-color 0.15s',
  };
  const labelStyle = {
    display: 'block', fontSize: 11, fontWeight: 600 as const,
    color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' as const,
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '22px' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16 }}>Preferences</div>
        <form onSubmit={handleSave}>
          <div style={{ marginBottom: 14 }}>
            <label style={labelStyle}>Service Area</label>
            <input value={serviceArea} onChange={e => setServiceArea(e.target.value)}
              placeholder="e.g. Greater Boston Area" style={inputStyle}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)}
              onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={labelStyle}>Timezone</label>
            <input value={timezone} onChange={e => setTimezone(e.target.value)}
              placeholder="e.g. America/New_York" style={inputStyle}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)}
              onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Quiet Hours Start</label>
              <input type="time" value={quietStart} onChange={e => setQuietStart(e.target.value)}
                style={inputStyle}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Quiet Hours End</label>
              <input type="time" value={quietEnd} onChange={e => setQuietEnd(e.target.value)}
                style={inputStyle}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
          </div>

          {msg && (
            <div style={{
              marginBottom: 14, padding: '9px 14px', borderRadius: 9, fontSize: 13,
              background: msgType === 'ok' ? t.greenBg : t.redBg,
              color: msgType === 'ok' ? t.green : t.red,
              border: `1px solid ${msgType === 'ok' ? t.green : t.red}30`,
            }}>{msg}</div>
          )}

          <button type="submit" disabled={saving} style={{
            width: '100%', padding: '12px',
            background: saving ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
            cursor: saving ? 'not-allowed' : 'pointer',
            boxShadow: saving ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
          }}>
            {saving ? 'Saving…' : 'Save Preferences'}
          </button>
        </form>
      </div>
    </div>
  );
};
