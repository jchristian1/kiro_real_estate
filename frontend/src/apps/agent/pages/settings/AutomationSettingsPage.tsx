/**
 * Automation Settings — HOT/WARM thresholds, SLA, tour question toggle.
 */

import React, { useState, useEffect } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { useAgentAutomation, useUpdateAutomation } from '../../hooks/useAgentQueries';
import { getAgentErrorMessage } from '../../api/agentApi';

export const AutomationSettingsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data, isLoading } = useAgentAutomation();
  const updateAutomation = useUpdateAutomation();

  const [hotThreshold, setHotThreshold] = useState(80);
  const [slaMinutes, setSlaMinutes] = useState(15);
  const [tourQuestion, setTourQuestion] = useState(true);
  const [quietStart, setQuietStart] = useState('22:00');
  const [quietEnd, setQuietEnd] = useState('08:00');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok');

  useEffect(() => {
    if (data) {
      setHotThreshold(data.hot_threshold);
      setSlaMinutes(data.sla_minutes_hot);
      setTourQuestion(data.enable_tour_question);
      if (data.quiet_hours_start) setQuietStart(data.quiet_hours_start);
      if (data.quiet_hours_end) setQuietEnd(data.quiet_hours_end);
    }
  }, [data]);

  const flash = (text: string, type: 'ok' | 'err') => {
    setMsg(text); setMsgType(type);
    setTimeout(() => setMsg(''), 3000);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateAutomation.mutateAsync({
        hot_threshold: hotThreshold,
        warm_threshold: Math.max(hotThreshold - 30, 10),
        sla_minutes_hot: slaMinutes,
        enable_tour_question: tourQuestion,
        quiet_hours_start: quietStart,
        quiet_hours_end: quietEnd,
      });
      flash('Settings saved', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setSaving(false);
    }
  };

  const labelStyle = {
    display: 'block', fontSize: 11, fontWeight: 600 as const,
    color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' as const,
  };
  const inputStyle = {
    padding: '11px 14px', background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 11, fontSize: 14, color: t.text, outline: 'none', transition: 'border-color 0.15s',
  };

  if (isLoading) return <div style={{ color: t.textMuted, fontSize: 14 }}>Loading…</div>;

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '24px' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 24 }}>Buyer Automation</div>

        {/* HOT threshold */}
        <div style={{ marginBottom: 24 }}>
          <label style={labelStyle}>HOT Lead Threshold — {hotThreshold} points</label>
          <input type="range" min={60} max={95} value={hotThreshold}
            onChange={e => setHotThreshold(Number(e.target.value))}
            style={{ width: '100%', accentColor: '#6366f1' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: t.textFaint, marginTop: 4 }}>
            <span>60 (more HOT)</span><span>95 (fewer HOT)</span>
          </div>
          <div style={{ marginTop: 8, fontSize: 12, color: t.textMuted }}>
            WARM threshold auto-set to {Math.max(hotThreshold - 30, 10)} pts
          </div>
        </div>

        {/* SLA */}
        <div style={{ marginBottom: 24 }}>
          <label style={labelStyle}>Response SLA for HOT Leads</label>
          <select value={slaMinutes} onChange={e => setSlaMinutes(Number(e.target.value))}
            style={{ ...inputStyle, width: '100%', cursor: 'pointer', boxSizing: 'border-box' as const }}>
            {[5, 15, 30, 60].map(m => <option key={m} value={m}>{m} minutes</option>)}
          </select>
        </div>

        {/* Tour question toggle */}
        <div style={{ marginBottom: 24 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 16px', background: t.bgPage, border: `1px solid ${t.border}`, borderRadius: 12,
          }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>Tour Interest Question</div>
              <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
                Ask leads if they want to schedule a tour (contributes to score)
              </div>
            </div>
            <button
              onClick={() => setTourQuestion(v => !v)}
              style={{
                width: 44, height: 26, borderRadius: 13, border: 'none', cursor: 'pointer',
                background: tourQuestion ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.border,
                position: 'relative', transition: 'background 0.2s', flexShrink: 0,
              }}
            >
              <div style={{
                position: 'absolute', top: 3, left: tourQuestion ? 21 : 3,
                width: 20, height: 20, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s', boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
              }} />
            </button>
          </div>
        </div>

        {/* Quiet hours */}
        <div style={{ marginBottom: 24 }}>
          <label style={labelStyle}>Quiet Hours (no emails sent)</label>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input type="time" value={quietStart} onChange={e => setQuietStart(e.target.value)}
              style={{ ...inputStyle, flex: 1, boxSizing: 'border-box' as const }}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
            <span style={{ color: t.textMuted, fontSize: 13 }}>to</span>
            <input type="time" value={quietEnd} onChange={e => setQuietEnd(e.target.value)}
              style={{ ...inputStyle, flex: 1, boxSizing: 'border-box' as const }}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>
        </div>

        {msg && (
          <div style={{
            marginBottom: 16, padding: '9px 14px', borderRadius: 9, fontSize: 13,
            background: msgType === 'ok' ? t.greenBg : t.redBg,
            color: msgType === 'ok' ? t.green : t.red,
            border: `1px solid ${msgType === 'ok' ? t.green : t.red}30`,
          }}>{msg}</div>
        )}

        <button onClick={handleSave} disabled={saving} style={{
          width: '100%', padding: '12px',
          background: saving ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
          cursor: saving ? 'not-allowed' : 'pointer',
          boxShadow: saving ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
        }}>
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};
