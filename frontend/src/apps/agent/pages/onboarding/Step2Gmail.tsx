/**
 * Step 2 — Gmail Connection: address + app password, IMAP test, watcher toggle.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';

interface Props { goBack: () => void; }

const ERROR_MESSAGES: Record<string, string> = {
  IMAP_DISABLED: 'IMAP is disabled in your Gmail settings. Enable it under Settings → See all settings → Forwarding and POP/IMAP.',
  TWO_FACTOR_REQUIRED: '2-Step Verification is required. Enable it in your Google Account security settings first.',
  INVALID_PASSWORD: 'Invalid App Password. Make sure you copied it correctly (no spaces).',
  RATE_LIMITED: 'Too many attempts. Please wait 15 minutes and try again.',
  CONNECTION_FAILED: 'Could not connect to Gmail. Check your internet connection and try again.',
};

export const Step2Gmail: React.FC<Props> = ({ goBack }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const [gmailAddress, setGmailAddress] = useState('');
  const [appPassword, setAppPassword] = useState('');
  const [showInstructions, setShowInstructions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

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
    setError(''); setSuccess(false); setLoading(true);
    try {
      await agentApi.post('/agent/onboarding/gmail', { gmail_address: gmailAddress, app_password: appPassword });
      setSuccess(true);
      setTimeout(() => navigate('/agent/onboarding/sources'), 800);
    } catch (err: unknown) {
      const raw = getAgentErrorMessage(err);
      setError(ERROR_MESSAGES[raw] || raw);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 22, padding: '36px 32px' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px', marginBottom: 6 }}>Connect Gmail</div>
        <div style={{ fontSize: 13, color: t.textMuted }}>Connect your Gmail account so LeadSync can monitor your inbox for new leads.</div>
      </div>

      {/* Collapsible instructions */}
      <div style={{ marginBottom: 20, background: t.accentBg, border: `1px solid ${t.borderFocus}`, borderRadius: 11, overflow: 'hidden' }}>
        <button
          type="button"
          onClick={() => setShowInstructions(v => !v)}
          style={{
            width: '100%', padding: '12px 16px', background: 'none', border: 'none',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            cursor: 'pointer', fontSize: 13, fontWeight: 600, color: t.accent,
          }}
        >
          <span>How to create an App Password</span>
          <span style={{ fontSize: 11, transition: 'transform 0.2s', transform: showInstructions ? 'rotate(180deg)' : 'none' }}>▼</span>
        </button>
        {showInstructions && (
          <div style={{ padding: '0 16px 14px', fontSize: 12, color: t.textSecondary, lineHeight: 1.7 }}>
            <ol style={{ margin: 0, paddingLeft: 18 }}>
              <li>Go to <strong style={{ color: t.text }}>myaccount.google.com</strong></li>
              <li>Click <strong style={{ color: t.text }}>Security</strong> → enable 2-Step Verification</li>
              <li>Search for <strong style={{ color: t.text }}>App passwords</strong></li>
              <li>Select app: <strong style={{ color: t.text }}>Mail</strong>, device: <strong style={{ color: t.text }}>Other</strong></li>
              <li>Copy the 16-character password and paste it below</li>
            </ol>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Gmail Address</label>
          <input type="email" value={gmailAddress} onChange={e => setGmailAddress(e.target.value)} required
            placeholder="you@gmail.com" style={inputStyle}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
        </div>
        <div style={{ marginBottom: 24 }}>
          <label style={labelStyle}>App Password</label>
          <input type="password" value={appPassword} onChange={e => setAppPassword(e.target.value)} required
            placeholder="16-character app password" style={inputStyle}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
        </div>

        {error && (
          <div style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>
            {error}
          </div>
        )}
        {success && (
          <div style={{ marginBottom: 16, padding: '10px 14px', background: t.greenBg, border: `1px solid ${t.green}30`, borderRadius: 9, fontSize: 13, color: t.green }}>
            ✓ Gmail connected successfully!
          </div>
        )}

        <div style={{ display: 'flex', gap: 10 }}>
          <button type="button" onClick={goBack} style={{
            flex: 1, padding: '12px', background: t.bgCard, border: `1px solid ${t.border}`,
            borderRadius: 11, fontSize: 14, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
          }}>Back</button>
          <button type="submit" disabled={loading || success} style={{
            flex: 2, padding: '12px',
            background: loading || success ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
            cursor: loading || success ? 'not-allowed' : 'pointer',
            boxShadow: loading || success ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
          }}>
            {loading ? 'Testing connection…' : success ? 'Connected ✓' : 'Connect Gmail'}
          </button>
        </div>
      </form>
    </div>
  );
};
