/**
 * FirstRunPage — shown once after first login when onboarding_completed=false.
 * Collects name, phone, timezone. On save → workspace.
 * No wizard, no step counter, no back button.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { agentApi, getAgentErrorMessage } from '../api/agentApi';
import { useAgentAuth } from '../contexts/AgentAuthContext';

const TIMEZONES = [
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Phoenix', 'America/Anchorage', 'Pacific/Honolulu',
];

export const FirstRunPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const { refreshAgent } = useAgentAuth();

  const browserTZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [timezone, setTimezone] = useState(browserTZ);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) { setError('Full name is required.'); return; }
    setError(''); setLoading(true);
    try {
      await agentApi.put('/agent/first-run/profile', { full_name: fullName, phone, timezone });
      await refreshAgent();
      navigate('/agent/dashboard', { replace: true });
    } catch (err) {
      setError(getAgentErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', background: t.bgPage,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif',
      padding: '0 16px',
    }}>
      <div style={{ width: '100%', maxWidth: 480 }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 17, color: '#fff', fontWeight: 800,
            boxShadow: '0 4px 12px rgba(99,102,241,0.4)',
          }}>L</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>LeadSync</div>
            <div style={{ fontSize: 10, color: t.textFaint, letterSpacing: '0.6px', textTransform: 'uppercase' }}>Welcome</div>
          </div>
        </div>

        {/* Card */}
        <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 22, padding: '36px 32px' }}>
          <div style={{ marginBottom: 28 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px', marginBottom: 6 }}>
              Set up your profile
            </div>
            <div style={{ fontSize: 13, color: t.textMuted }}>
              Just a few details so leads can reach you. You can update these any time in settings.
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Full Name *</label>
              <input
                value={fullName} onChange={e => setFullName(e.target.value)} required
                placeholder="Your name" style={inputStyle}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                onBlur={e => (e.target.style.borderColor = t.border)}
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Phone</label>
              <input
                type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                placeholder="Optional" style={inputStyle}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                onBlur={e => (e.target.style.borderColor = t.border)}
              />
            </div>
            <div style={{ marginBottom: 28 }}>
              <label style={labelStyle}>Timezone</label>
              <select
                value={timezone} onChange={e => setTimezone(e.target.value)}
                style={{ ...inputStyle, cursor: 'pointer' }}
              >
                {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
              </select>
            </div>

            {error && (
              <div style={{
                marginBottom: 16, padding: '10px 14px',
                background: t.redBg, border: `1px solid ${t.red}30`,
                borderRadius: 9, fontSize: 13, color: t.red,
              }}>{error}</div>
            )}

            <button type="submit" disabled={loading} style={{
              width: '100%', padding: '13px',
              background: loading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: loading ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
            }}>
              {loading ? 'Saving…' : 'Go to workspace →'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
