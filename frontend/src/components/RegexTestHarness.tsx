/**
 * RegexTestHarness Component
 * Requirements: 2.3, 2.4, 14.5, 14.6, 14.7
 */
import React, { useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useT } from '../utils/useT';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface RegexTestResult {
  matched: boolean;
  match_text: string | null;
  groups: string[];
  named_groups: Record<string, string>;
}

interface RegexTestResponse {
  pattern: string;
  test_text: string;
  result: RegexTestResult;
}

export interface RegexTestHarnessProps {
  initialPattern?: string;
}

const HighlightedText: React.FC<{ text: string; matchText: string | null }> = ({ text, matchText }) => {
  if (!matchText) return <span>{text}</span>;
  const idx = text.indexOf(matchText);
  if (idx === -1) return <span>{text}</span>;
  return (
    <span>
      {text.slice(0, idx)}
      <mark style={{ background: 'rgba(251,191,36,0.35)', color: 'inherit', borderRadius: 3, padding: '0 2px' }} data-testid="match-highlight">
        {matchText}
      </mark>
      {text.slice(idx + matchText.length)}
    </span>
  );
};

export const RegexTestHarness: React.FC<RegexTestHarnessProps> = ({ initialPattern = '' }) => {
  const t = useT();
  const [pattern, setPattern] = useState(initialPattern);
  const [testText, setTestText] = useState('');
  const [result, setResult] = useState<RegexTestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTest = async () => {
    if (!pattern.trim() || !testText.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await axios.post<RegexTestResponse>(
        `${API_BASE_URL}/lead-sources/test-regex`,
        { pattern, test_text: testText }
      );
      setResult(response.data.result);
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      if (e.response?.status === 408) {
        setError('Regex timed out — pattern may be too complex or cause catastrophic backtracking.');
      } else {
        setError(e.response?.data?.detail || e.response?.data?.message || 'Failed to test regex. Please check your pattern.');
      }
    } finally {
      setLoading(false);
    }
  };

  const hasGroups = result && (result.groups.length > 0 || Object.keys(result.named_groups).length > 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} data-testid="regex-test-harness">
      <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: t.text }}>Regex Test Harness</h3>

      {/* Pattern */}
      <div>
        <label htmlFor="rth-pattern" style={t.labelStyle}>Pattern</label>
        <input id="rth-pattern" type="text" value={pattern} onChange={(e) => setPattern(e.target.value)}
          placeholder="e.g. (?i)new lead from (\w+)"
          style={{ ...t.input, fontFamily: 'monospace' }}
          data-testid="pattern-input" />
      </div>

      {/* Sample text */}
      <div>
        <label htmlFor="rth-text" style={t.labelStyle}>Sample Text</label>
        <textarea id="rth-text" value={testText} onChange={(e) => setTestText(e.target.value)}
          placeholder="Paste sample email subject or body here..."
          rows={4}
          style={{ ...t.input, resize: 'vertical', fontFamily: 'inherit' }}
          data-testid="test-text-input" />
      </div>

      {/* Test button */}
      <div>
        <button onClick={handleTest} disabled={loading || !pattern.trim() || !testText.trim()}
          style={{ ...t.btnPrimary, opacity: (loading || !pattern.trim() || !testText.trim()) ? 0.5 : 1, cursor: (loading || !pattern.trim() || !testText.trim()) ? 'not-allowed' : 'pointer' }}
          data-testid="test-button">
          {loading ? 'Testing...' : 'Test Pattern'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div role="alert" data-testid="test-error"
          style={{ padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 10, fontSize: 13, color: t.red }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="test-results">
          {/* Match status badge */}
          <div>
            <span data-testid="match-status" style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
              background: result.matched ? t.greenBg : t.redBg,
              color: result.matched ? t.green : t.red,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: result.matched ? t.green : t.red, display: 'inline-block' }} />
              {result.matched ? 'Match found' : 'No match'}
            </span>
          </div>

          {/* Highlighted text */}
          {result.matched && (
            <div data-testid="highlighted-text"
              style={{ padding: '10px 12px', background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 10, fontSize: 12, fontFamily: 'monospace', wordBreak: 'break-all', color: t.textSecondary }}>
              <HighlightedText text={testText} matchText={result.match_text} />
            </div>
          )}

          {/* Captured groups */}
          {hasGroups && (
            <div data-testid="captured-groups">
              <span style={t.labelStyle}>Captured Groups</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                {result.groups.map((g, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12 }}>
                    <span style={{ color: t.textMuted, fontFamily: 'monospace' }}>Group {i + 1}:</span>
                    <span data-testid={`group-${i + 1}`} style={{ fontFamily: 'monospace', color: t.accent, background: t.accentBg, padding: '1px 6px', borderRadius: 5 }}>{g}</span>
                  </div>
                ))}
                {Object.entries(result.named_groups).map(([name, val]) => (
                  <div key={name} style={{ display: 'flex', gap: 8, fontSize: 12 }}>
                    <span style={{ color: t.textMuted, fontFamily: 'monospace' }}>?&lt;{name}&gt;:</span>
                    <span data-testid={`named-group-${name}`} style={{ fontFamily: 'monospace', color: t.orange, background: t.orangeBg, padding: '1px 6px', borderRadius: 5 }}>{val}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
