/**
 * Step 6 — Go Live: precondition checklist, test simulation, go live button.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../contexts/ThemeContext';
import { getTokens } from '../../../utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';
import { useAgentAuth } from '../../contexts/AgentAuthContext';

interface Props { goBack: () => void; }

interface TestResult {
  lead_name: string; score: number; bucket: string;
  rendered_emails: { type: string; subject: string; body: string }[];
}

interface CompleteResult {
  success: boolean;
  missing?: string[];
}

export const Step6GoLive: React.FC<Props> = ({ goBack }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const { refreshAgent } = useAgentAuth();

  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testError, setTestError] = useState('');
  const [goLiveLoading, setGoLiveLoading] = useState(false);
  const [goLiveError, setGoLiveError] = useState('');
  const [missing, setMissing] = useState<string[]>([]);

  const runTest = async () => {
    setTestError(''); setTestResult(null); setTestLoading(true);
    try {
      const result = await agentApi.post<TestResult>('/agent/onboarding/test', {});
      setTestResult(result);
    } catch (err) {
      setTestError(getAgentErrorMessage(err));
    } finally {
      setTestLoading(false);
    }
  };

  const goLive = async () => {
    setGoLiveError(''); setMissing([]); setGoLiveLoading(true);
    try {
      const result = await agentApi.post<CompleteResult>('/agent/onboarding/complete', {});
      if (result.success) {
        await refreshAgent();
        navigate('/agent/dashboard');
      } else {
        setMissing(result.missing || []);
        setGoLiveError('Please complete all required steps before going live.');
      }
    } catch (err) {
      setGoLiveError(getAgentErrorMessage(err));
    } finally {
      setGoLiveLoading(false);
    }
  };

  const bucketColor = (bucket: string) => {
    if (bucket === 'HOT') return t.red;
    if (bucket === 'WARM') return t.orange;
    return t.textMuted;
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 22, padding: '36px 32px' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px', marginBottom: 6 }}>Go Live</div>
        <div style={{ fontSize: 13, color: t.textMuted }}>Run a test to verify your setup, then activate your agent account.</div>
      </div>

      {/* Test simulation */}
      <div style={{ marginBottom: 24, padding: '20px', background: t.bgPage, border: `1px solid ${t.border}`, borderRadius: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 8 }}>Test Simulation</div>
        <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 14 }}>
          Runs a simulated lead through your full pipeline — no real emails sent, no data saved.
        </div>
        <button type="button" onClick={runTest} disabled={testLoading} style={{
          padding: '10px 20px',
          background: testLoading ? t.accentBg : t.accentBg,
          border: `1px solid ${t.accent}`,
          borderRadius: 9, fontSize: 13, fontWeight: 600, color: t.accent,
          cursor: testLoading ? 'not-allowed' : 'pointer', transition: 'all 0.15s',
        }}>
          {testLoading ? 'Running test…' : 'Run Test'}
        </button>

        {testError && (
          <div style={{ marginTop: 12, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>
            {testError}
          </div>
        )}

        {testResult && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
              <div style={{ padding: '8px 14px', background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 9 }}>
                <div style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Lead</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginTop: 2 }}>{testResult.lead_name}</div>
              </div>
              <div style={{ padding: '8px 14px', background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 9 }}>
                <div style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Score</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginTop: 2 }}>{testResult.score}</div>
              </div>
              <div style={{ padding: '8px 14px', background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 9 }}>
                <div style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Bucket</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: bucketColor(testResult.bucket), marginTop: 2 }}>{testResult.bucket}</div>
              </div>
            </div>
            {testResult.rendered_emails?.map(email => (
              <div key={email.type} style={{ marginBottom: 10, padding: '12px 14px', background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 9 }}>
                <div style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>{email.type.replace(/_/g, ' ')}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: t.text, marginBottom: 4 }}>{email.subject}</div>
                <div style={{ fontSize: 12, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{email.body}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Missing items */}
      {missing.length > 0 && (
        <div style={{ marginBottom: 16, padding: '14px 16px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 11 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: t.red, marginBottom: 8 }}>Complete these steps first:</div>
          {missing.map(item => (
            <div key={item} style={{ fontSize: 12, color: t.red, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span>✗</span> {item}
            </div>
          ))}
        </div>
      )}

      {goLiveError && !missing.length && (
        <div style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>
          {goLiveError}
        </div>
      )}

      <div style={{ display: 'flex', gap: 10 }}>
        <button type="button" onClick={goBack} style={{
          flex: 1, padding: '12px', background: t.bgCard, border: `1px solid ${t.border}`,
          borderRadius: 11, fontSize: 14, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
        }}>Back</button>
        <button type="button" onClick={goLive} disabled={goLiveLoading} style={{
          flex: 2, padding: '12px',
          background: goLiveLoading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
          cursor: goLiveLoading ? 'not-allowed' : 'pointer',
          boxShadow: goLiveLoading ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
        }}>
          {goLiveLoading ? 'Activating…' : '🚀 Go Live'}
        </button>
      </div>
    </div>
  );
};
