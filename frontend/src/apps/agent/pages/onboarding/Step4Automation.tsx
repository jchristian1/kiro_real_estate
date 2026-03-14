/**
 * Step 4 — Buyer Automation: HOT threshold, SLA, tour question toggle, working hours.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';

interface Props { goBack: () => void; }

export const Step4Automation: React.FC<Props> = ({ goBack }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const [hotThreshold, setHotThreshold] = useState(80);
  const [slaMinutes, setSlaMinutes] = useState(15);
  const [tourQuestion, setTourQuestion] = useState(true);
  const [quietStart, setQuietStart] = useState('22:00');
  const [quietEnd, setQuietEnd] = useState('08:00');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const inputStyle = {
    padding: '11px 14px', background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 11, fontSize: 14, color: t.text,
    outline: 'none', transition: 'border-color 0.15s',
  };
  const labelStyle = {
    display: 'block', fontSize: 11, fontWeight: 600 as const,
    color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' as const,
  };

  const handleSubmit = async () => {
    setError(''); setLoading(true);
    try {
      await agentApi.put('/agent/onboarding/automation', {
        hot_threshold: hotThreshold,
        warm_threshold: Math.max(hotThreshold - 30, 10),
        sla_minutes_hot: slaMinutes,
        enable_tour_question: tourQuestion,
        quiet_hours_start: quietStart,
        quiet_hours_end: quietEnd,
      });
      navigate('/agent/onboarding/templates');
    } catch (err) {
      setError(getAgentErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 22, padding: '36px 32px' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px', marginBottom: 6 }}>Buyer Automation</div>
        <div style={{ fontSize: 13, color: t.textMuted }}>Configure how leads are scored and when you get notified.</div>
      </div>

      {/* HOT threshold slider */}
      <div style={{ marginBottom: 24 }}>
        <label style={labelStyle}>HOT Lead Threshold — {hotThreshold} points</label>
        <input type="range" min={60} max={95} value={hotThreshold}
          onChange={e => setHotThreshold(Number(e.target.value))}
          style={{ width: '100%', accentColor: '#6366f1' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: t.textFaint, marginTop: 4 }}>
          <span>60 (more HOT leads)</span><span>95 (fewer HOT leads)</span>
        </div>
      </div>

      {/* SLA */}
      <div style={{ marginBottom: 24 }}>
        <label style={labelStyle}>Response SLA for HOT Leads</label>
        <select value={slaMinutes} onChange={e => setSlaMinutes(Number(e.target.value))}
          style={{ ...inputStyle, width: '100%', cursor: 'pointer', boxSizing: 'border-box' }}>
          {[5, 15, 30, 60].map(m => <option key={m} value={m}>{m} minutes</option>)}
        </select>
      </div>

      {/* Tour question toggle */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 12 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>Tour Interest Question</div>
            <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>Ask leads if they want to schedule a tour</div>
          </div>
          <button
            type="button"
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
