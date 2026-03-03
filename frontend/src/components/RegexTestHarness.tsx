/**
 * RegexTestHarness Component
 *
 * Interactive UI for testing regex patterns against sample text.
 * Calls the backend test-regex endpoint and displays match results
 * with highlighting and captured groups.
 *
 * Requirements: 2.3, 2.4, 14.5, 14.6, 14.7
 */

import React, { useState } from 'react';
import axios, { AxiosError } from 'axios';

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
  /** Pre-fill the pattern field (e.g. from a lead source form) */
  initialPattern?: string;
}

/**
 * Highlight matched portion of text.
 */
const HighlightedText: React.FC<{ text: string; matchText: string | null }> = ({
  text,
  matchText,
}) => {
  if (!matchText) return <span>{text}</span>;

  const idx = text.indexOf(matchText);
  if (idx === -1) return <span>{text}</span>;

  return (
    <span>
      {text.slice(0, idx)}
      <mark className="bg-yellow-200 text-yellow-900 rounded px-0.5" data-testid="match-highlight">
        {matchText}
      </mark>
      {text.slice(idx + matchText.length)}
    </span>
  );
};

export const RegexTestHarness: React.FC<RegexTestHarnessProps> = ({ initialPattern = '' }) => {
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
      const axiosError = err as AxiosError<{ detail?: string; message?: string }>;
      if (axiosError.response?.status === 408) {
        setError('Regex timed out — pattern may be too complex or cause catastrophic backtracking.');
      } else {
        const msg =
          axiosError.response?.data?.detail ||
          axiosError.response?.data?.message ||
          'Failed to test regex. Please check your pattern.';
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const hasGroups =
    result && (result.groups.length > 0 || Object.keys(result.named_groups).length > 0);

  return (
    <div className="space-y-4" data-testid="regex-test-harness">
      <h3 className="text-sm font-semibold text-gray-700">Regex Test Harness</h3>

      {/* Pattern input */}
      <div>
        <label htmlFor="rth-pattern" className="block text-sm font-medium text-gray-700 mb-1">
          Pattern
        </label>
        <input
          id="rth-pattern"
          type="text"
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          placeholder="e.g. (?i)new lead from (\w+)"
          className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          data-testid="pattern-input"
        />
      </div>

      {/* Sample text input */}
      <div>
        <label htmlFor="rth-text" className="block text-sm font-medium text-gray-700 mb-1">
          Sample Text
        </label>
        <textarea
          id="rth-text"
          value={testText}
          onChange={(e) => setTestText(e.target.value)}
          placeholder="Paste sample email subject or body here..."
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          data-testid="test-text-input"
        />
      </div>

      {/* Test button */}
      <button
        onClick={handleTest}
        disabled={loading || !pattern.trim() || !testText.trim()}
        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="test-button"
      >
        {loading ? 'Testing...' : 'Test Pattern'}
      </button>

      {/* Error */}
      {error && (
        <div
          className="p-3 bg-red-50 border border-red-300 text-red-700 rounded text-sm"
          role="alert"
          data-testid="test-error"
        >
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-3" data-testid="test-results">
          {/* Match status */}
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-1 text-xs font-semibold rounded-full ${
                result.matched
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
              data-testid="match-status"
            >
              {result.matched ? 'Match found' : 'No match'}
            </span>
          </div>

          {/* Highlighted text */}
          {result.matched && (
            <div className="p-3 bg-gray-50 border border-gray-200 rounded text-sm font-mono break-all" data-testid="highlighted-text">
              <HighlightedText text={testText} matchText={result.match_text} />
            </div>
          )}

          {/* Captured groups */}
          {hasGroups && (
            <div data-testid="captured-groups">
              <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
                Captured Groups
              </h4>

              {result.groups.length > 0 && (
                <div className="space-y-1">
                  {result.groups.map((g, i) => (
                    <div key={i} className="flex gap-2 text-sm">
                      <span className="text-gray-500 font-mono">Group {i + 1}:</span>
                      <span className="font-mono text-blue-700 bg-blue-50 px-1 rounded" data-testid={`group-${i + 1}`}>
                        {g}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {Object.keys(result.named_groups).length > 0 && (
                <div className="space-y-1 mt-2">
                  {Object.entries(result.named_groups).map(([name, val]) => (
                    <div key={name} className="flex gap-2 text-sm">
                      <span className="text-gray-500 font-mono">?&lt;{name}&gt;:</span>
                      <span className="font-mono text-purple-700 bg-purple-50 px-1 rounded" data-testid={`named-group-${name}`}>
                        {val}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
