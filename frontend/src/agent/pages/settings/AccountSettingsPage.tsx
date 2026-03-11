/**
 * Account / Gmail Settings — connection status, test, update credentials, disconnect, watcher toggle.
 */

import React, { useState } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';
import { getTokens } from '../../../utils/theme';
import { useAgentGmail, useToggleWatcher, useUpdateGmail, useDisconnectGmail, useCancelSubscription } from '../../hooks/useAgentQueries';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';

export const AccountSettingsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: gmail, isLoading } = useAgentGmail();
  const toggleWatcher = useToggleWatcher();
  const updateGmail = useUpdateGmail();
  const disconnectGmail = useDisconnectGmail();
  const cancelSubscription = useCancelSubscription();

  const [gmailAddress, setGmailAddress] = useState('');
  const [appPassword, setAppPassword] = useState('');
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok');

  const flash = (text: string, type: 'ok' | 'err') => {
    setMsg(text); setMsgType(type);
    setTimeout(() => setMsg(''), 4000);
  };

  const handleTest = async () => {
    if (!gmailAddress || !appPassword) { flash('Enter Gmail address and app password first', 'err'); return; }
    setTesting(true); setTestResult(null);
    try {
      await agentApi.post('/agent/account/gmail/test', { gmail_address: gmailAddress, app_password: appPassword });
      setTestResult({ ok: true, msg: 'Connection successful!' });
    } catch (err) {
      setTestResult({ ok: false, msg: getAgentErrorMessage(err) });
    } finally {
      setTesting(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateGmail.mutateAsync({ gmail_address: gmailAddress, app_password: appPassword });
      setGmailAddress(''); setAppPassword('');
      flash('Gmail credentials updated', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Disconnect Gmail? This will stop the watcher.')) return;
    setDisconnecting(true);
    try {
      await disconnectGmail.mutateAsync();
      flash('Gmail disconnected', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setDisconnecting(false);
    }
  };

  const handleWatcherToggle = async () => {
    if (gmail?.watcher_admin_override) return;
    try {
      await toggleWatcher.mutateAsync(!gmail?.watcher_enabled);
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    }
  };

  const handleCancelSubscription = async () => {
    setCancelling(true);
    try {
      await cancelSubscription.mutateAsync();
      setShowCancelConfirm(false);
      flash('Subscription cancelled. Watcher stopped.', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setCancelling(false);
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
  const cardStyle = {
    background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '22px', marginBottom: 16,
  };

  if (isLoading) return <div style={{ color: t.textMuted, fontSize: 14 }}>Loading…</div>;

  return (
    <div style={{ maxWidth: 560 }}>
      {/* Connection status */}
      <div style={cardStyle}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16 }}>Gmail Connection</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: gmail?.connected ? t.green : t.red,
            boxShadow: gmail?.connected ? `0 0 8px ${t.green}` : 'none',
          }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: t.text }}>
            {gmail?.connected ? 'Connected' : 'Not connected'}
          </span>
          {gmail?.gmail_address && (
            <span style={{ fontSize: 13, color: t.textMuted }}>— {gmail.gmail_address}</span>
          )}
        </div>
        {gmail?.last_sync && (
          <div style={{ fontSize: 12, color: t.textFaint, marginBottom: 16 }}>
            Last sync: {new Date(gmail.last_sync).toLocaleString()}
          </div>
        )}

        {/* Watcher toggle */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 14px', background: t.bgPage, border: `1px solid ${t.border}`, borderRadius: 11,
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Gmail Watcher</div>
            {gmail?.watcher_admin_override && (
              <div style={{ fontSize: 11, color: t.orange, marginTop: 2 }}>Locked by admin</div>
            )}
          </div>
          <button
            onClick={handleWatcherToggle}
            disabled={gmail?.watcher_admin_override || toggleWatcher.isPending}
            aria-label={gmail?.watcher_enabled ? 'Disable watcher' : 'Enable watcher'}
            style={{
              width: 44, height: 26, borderRadius: 13, border: 'none',
              cursor: gmail?.watcher_admin_override ? 'not-allowed' : 'pointer',
              background: gmail?.watcher_enabled ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.border,
              position: 'relative', transition: 'background 0.2s',
              opacity: gmail?.watcher_admin_override ? 0.5 : 1,
              padding: '9px 0', boxSizing: 'content-box' as const,
            }}
          >
            <div style={{
              position: 'absolute', top: 3, left: gmail?.watcher_enabled ? 21 : 3,
              width: 20, height: 20, borderRadius: '50%', background: '#fff',
              transition: 'left 0.2s', boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
            }} />
          </button>
        </div>

        {gmail?.connected && (
          <button onClick={handleDisconnect} disabled={disconnecting} style={{
            marginTop: 14, padding: '9px 16px', background: t.redBg,
            border: `1px solid ${t.red}30`, borderRadius: 10,
            fontSize: 13, fontWeight: 500, color: t.red, cursor: 'pointer',
            opacity: disconnecting ? 0.6 : 1,
          }}>
            {disconnecting ? 'Disconnecting…' : 'Disconnect Gmail'}
          </button>
        )}
      </div>

      {/* Update credentials */}
      <div style={cardStyle}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16 }}>
          {gmail?.connected ? 'Update Credentials' : 'Connect Gmail'}
        </div>
        <form onSubmit={handleUpdate}>
          <div style={{ marginBottom: 14 }}>
            <label style={labelStyle}>Gmail Address</label>
            <input type="email" value={gmailAddress} onChange={e => setGmailAddress(e.target.value)} required
              placeholder={gmail?.gmail_address || 'you@gmail.com'} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>App Password</label>
            <input type="password" value={appPassword} onChange={e => setAppPassword(e.target.value)} required
              placeholder="16-character app password" style={inputStyle}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>

          {testResult && (
            <div style={{
              marginBottom: 14, padding: '9px 14px', borderRadius: 9, fontSize: 13,
              background: testResult.ok ? t.greenBg : t.redBg,
              color: testResult.ok ? t.green : t.red,
              border: `1px solid ${testResult.ok ? t.green : t.red}30`,
            }}>{testResult.msg}</div>
          )}

          {msg && (
            <div style={{
              marginBottom: 14, padding: '9px 14px', borderRadius: 9, fontSize: 13,
              background: msgType === 'ok' ? t.greenBg : t.redBg,
              color: msgType === 'ok' ? t.green : t.red,
              border: `1px solid ${msgType === 'ok' ? t.green : t.red}30`,
            }}>{msg}</div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button type="button" onClick={handleTest} disabled={testing} style={{
              flex: 1, padding: '10px', background: t.bgPage, border: `1px solid ${t.border}`,
              borderRadius: 10, fontSize: 13, fontWeight: 500, color: t.textMuted,
              cursor: testing ? 'not-allowed' : 'pointer', opacity: testing ? 0.6 : 1,
            }}>
              {testing ? 'Testing…' : 'Test Connection'}
            </button>
            <button type="submit" disabled={saving} style={{
              flex: 2, padding: '10px',
              background: saving ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 600, color: '#fff',
              cursor: saving ? 'not-allowed' : 'pointer',
              boxShadow: saving ? 'none' : '0 2px 8px rgba(99,102,241,0.3)',
            }}>
              {saving ? 'Saving…' : gmail?.connected ? 'Update' : 'Connect'}
            </button>
          </div>
        </form>
      </div>

      {/* Danger zone — cancel subscription */}
      <div style={{
        ...cardStyle,
        border: `1px solid ${t.red}40`,
        background: t.redBg,
        marginTop: 8,
      }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.red, marginBottom: 8 }}>Cancel Subscription</div>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 16, lineHeight: 1.6 }}>
          This will stop your Gmail watcher and deactivate your account. Your leads and data will be preserved and you can re-activate at any time.
        </div>

        {!showCancelConfirm ? (
          <button
            onClick={() => setShowCancelConfirm(true)}
            style={{
              padding: '10px 20px', background: 'transparent',
              border: `1.5px solid ${t.red}`, borderRadius: 10,
              fontSize: 13, fontWeight: 600, color: t.red,
              cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            Cancel Subscription
          </button>
        ) : (
          <div style={{
            background: t.bgCard, border: `1px solid ${t.red}50`,
            borderRadius: 12, padding: '16px 18px',
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 6 }}>
              Are you sure?
            </div>
            <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 16 }}>
              Your watcher will stop immediately. All leads and settings are kept.
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setShowCancelConfirm(false)}
                disabled={cancelling}
                style={{
                  flex: 1, padding: '10px', background: t.bgPage,
                  border: `1px solid ${t.border}`, borderRadius: 10,
                  fontSize: 13, fontWeight: 500, color: t.textMuted,
                  cursor: 'pointer',
                }}
              >
                Keep Subscription
              </button>
              <button
                onClick={handleCancelSubscription}
                disabled={cancelling}
                style={{
                  flex: 1, padding: '10px',
                  background: t.red, border: 'none', borderRadius: 10,
                  fontSize: 13, fontWeight: 600, color: '#fff',
                  cursor: cancelling ? 'not-allowed' : 'pointer',
                  opacity: cancelling ? 0.7 : 1,
                }}
              >
                {cancelling ? 'Cancelling…' : 'Yes, Cancel'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
