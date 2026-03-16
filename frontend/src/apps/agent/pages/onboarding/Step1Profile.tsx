/**
 * Step 1 — Agent Profile: full_name, phone, timezone, service_area, company join code.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';
import { useAgentAuth } from '../../contexts/AgentAuthContext';

const TIMEZONES = [
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Phoenix', 'America/Anchorage', 'Pacific/Honolulu',
];

interface Props { goBack: () => void; }

export const Step1Profile: React.FC<Props> = ({ goBack }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const { refreshAgent } = useAgentAuth();

  const browserTZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [fullName, setFullName] = useState(localStorage.getItem('ob_full_name') || '');
  const [phone, setPhone] = useState(localStorage.getItem('ob_phone') || '');
  const [timezone, setTimezone] = useState(localStorage.getItem('ob_timezone') || browserTZ);
  const [serviceArea, setServiceArea] = useState(localStorage.getItem('ob_service_area') || '');
  const [joinCode, setJoinCode] = useState('');
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
      await agentApi.put('/agent/onboarding/profile', {
        full_name: fullName, phone, timezone, service_area: serviceArea,
        ...(joinCode ? { company_join_code: joinCode } : {}),
      });
      localStorage.setItem('ob_full_name', fullName);
      localStorage.setItem('ob_phone', phone);
      localStorage.setItem('ob_timezone', timezone);
      localStorage.setItem('ob_service_area', serviceArea);
      await refreshAgent();
      navigate('/agent/onboarding/gmail');
    } catch (err) {
      setError(getAgentErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 22, padding: '36px 32px' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px', marginBottom: 6 }}>Your Profile</div>
        <div style={{ fontSize: 13, color: t.textMuted }}>Tell us a bit about yourself so leads can reach you.</div>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Full Name *</label>
          <input value={fullName} onChange={e => setFullName(e.target.value)} required style={inputStyle}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Phone</label>
          <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} style={inputStyle}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Timezone</label>
          <select value={timezone} onChange={e => setTimezone(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
            {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
          </select>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Service Area</label>
          <input value={serviceArea} onChange={e => setServiceArea(e.target.value)} placeholder="e.g. Greater Boston Area" style={inputStyle}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
        </div>
        <div style={{ marginBottom: 24 }}>
          <label style={labelStyle}>Company Join Code (optional)</label>
          <input value={joinCode} onChange={e => setJoinCode(e.target.value)} placeholder="Leave blank to skip" style={inputStyle}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
        </div>

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
          <button type="submit" disabled={loading} style={{
            flex: 2, padding: '12px',
            background: loading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
            cursor: loading ? 'not-allowed' : 'pointer',
            boxShadow: loading ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
          }}>
            {loading ? 'Saving…' : 'Continue'}
          </button>
        </div>
      </form>
    </div>
  );
};
