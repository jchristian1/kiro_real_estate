/**
 * RegexVersionHistory Component
 * Requirements: 9.5, 9.6
 */
import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { ConfirmDialog } from './ConfirmDialog';
import { useT } from '../../../shared/hooks/useT';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface RegexProfileVersion {
  version: number;
  name_regex: string;
  phone_regex: string;
  identifier_snippet: string;
  created_at: string;
  created_by: number;
}

export interface RegexVersionHistoryProps {
  leadSourceId: number;
  leadSourceName: string;
  onClose: () => void;
  onRollbackSuccess: () => void;
}

export const RegexVersionHistory: React.FC<RegexVersionHistoryProps> = ({
  leadSourceId, leadSourceName, onClose, onRollbackSuccess,
}) => {
  const t = useT();
  const [versions, setVersions] = useState<RegexProfileVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<RegexProfileVersion | null>(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);

  useEffect(() => {
    const fetchVersions = async () => {
      try {
        setLoading(true);
        const res = await axios.get<{ versions: RegexProfileVersion[] }>(
          `${API_BASE_URL}/lead-sources/${leadSourceId}/versions`
        );
        setVersions(res.data.versions);
        setError(null);
      } catch {
        setError('Failed to load version history');
      } finally {
        setLoading(false);
      }
    };
    fetchVersions();
  }, [leadSourceId]);

  const handleRollbackConfirm = async () => {
    if (!rollbackTarget) return;
    setRollbackLoading(true);
    setRollbackError(null);
    try {
      await axios.post(`${API_BASE_URL}/lead-sources/${leadSourceId}/rollback`, { version: rollbackTarget.version });
      setRollbackTarget(null);
      onRollbackSuccess();
    } catch (err) {
      const e = err as AxiosError<{ message?: string; detail?: string }>;
      setRollbackError(e.response?.data?.message || e.response?.data?.detail || 'Failed to rollback');
      setRollbackTarget(null);
    } finally {
      setRollbackLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 40, display: 'flex', alignItems: 'center', justifyContent: 'center' }} data-testid="regex-version-history">
      {/* Backdrop */}
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)' }} onClick={onClose} data-testid="version-history-backdrop" />

      {/* Panel */}
      <div style={{
        position: 'relative', zIndex: 10,
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 18, width: '100%', maxWidth: 640,
        margin: '0 16px', display: 'flex', flexDirection: 'column',
        maxHeight: '80vh', boxShadow: '0 24px 64px rgba(0,0,0,0.4)',
        backdropFilter: 'blur(20px)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: `1px solid ${t.border}` }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: t.text }} data-testid="version-history-title">Version History</h2>
            <p style={{ margin: '3px 0 0', fontSize: 12, color: t.textMuted }}>{leadSourceName}</p>
          </div>
          <button onClick={onClose} aria-label="Close version history" data-testid="version-history-close"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textMuted, padding: 4, borderRadius: 8, display: 'flex', alignItems: 'center' }}>
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Body */}
        <div style={{ overflowY: 'auto', flex: 1, padding: '16px 24px' }}>
          {rollbackError && (
            <div role="alert" data-testid="rollback-error" style={{ marginBottom: 12, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 10, fontSize: 13, color: t.red }}>
              {rollbackError}
            </div>
          )}
          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120 }} data-testid="version-history-loading">
              <span style={{ color: t.textMuted, fontSize: 13 }}>Loading version history...</span>
            </div>
          )}
          {error && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120 }} data-testid="version-history-error">
              <span style={{ color: t.red, fontSize: 13 }}>{error}</span>
            </div>
          )}
          {!loading && !error && versions.length === 0 && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120 }} data-testid="version-history-empty">
              <span style={{ color: t.textMuted, fontSize: 13 }}>No version history available</span>
            </div>
          )}
          {!loading && !error && versions.length > 0 && (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }} data-testid="version-list">
              {versions.map((v, idx) => {
                const isLatest = idx === 0;
                const isExpanded = expandedVersion === v.version;
                return (
                  <li key={v.version} style={{ border: `1px solid ${t.border}`, borderRadius: 12, overflow: 'hidden' }} data-testid={`version-item-${v.version}`}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: t.bgInput }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Version {v.version}</span>
                        {isLatest && (
                          <span style={{ padding: '2px 8px', fontSize: 11, fontWeight: 600, background: t.accentBg, color: t.accent, borderRadius: 20 }}>Current</span>
                        )}
                        <span style={{ fontSize: 11, color: t.textMuted }}>{new Date(v.created_at).toLocaleString()}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button onClick={() => setExpandedVersion(isExpanded ? null : v.version)}
                          style={{ fontSize: 12, color: t.textMuted, background: 'none', border: 'none', cursor: 'pointer', padding: '3px 8px', borderRadius: 6 }}
                          data-testid={`toggle-version-${v.version}`}>
                          {isExpanded ? 'Hide' : 'Details'}
                        </button>
                        {!isLatest && (
                          <button onClick={() => setRollbackTarget(v)} disabled={rollbackLoading}
                            style={{ fontSize: 12, fontWeight: 600, color: t.accent, background: t.accentBg, border: 'none', cursor: 'pointer', padding: '3px 10px', borderRadius: 6, opacity: rollbackLoading ? 0.5 : 1 }}
                            data-testid={`rollback-button-${v.version}`}>
                            Rollback
                          </button>
                        )}
                      </div>
                    </div>
                    {isExpanded && (
                      <div style={{ padding: '12px 14px', borderTop: `1px solid ${t.border}`, display: 'flex', flexDirection: 'column', gap: 10 }} data-testid={`version-details-${v.version}`}>
                        <div>
                          <span style={t.labelStyle}>Identifier Snippet</span>
                          <code style={{ display: 'block', marginTop: 4, fontSize: 12, background: t.bgInput, color: t.textSecondary, padding: '6px 10px', borderRadius: 8, fontFamily: 'monospace', wordBreak: 'break-all', border: `1px solid ${t.border}` }}>
                            {v.identifier_snippet}
                          </code>
                        </div>
                        <div>
                          <span style={t.labelStyle}>Name Regex</span>
                          <code style={{ display: 'block', marginTop: 4, fontSize: 12, background: t.bgInput, color: t.textSecondary, padding: '6px 10px', borderRadius: 8, fontFamily: 'monospace', wordBreak: 'break-all', border: `1px solid ${t.border}` }}>
                            {v.name_regex}
                          </code>
                        </div>
                        <div>
                          <span style={t.labelStyle}>Phone Regex</span>
                          <code style={{ display: 'block', marginTop: 4, fontSize: 12, background: t.bgInput, color: t.textSecondary, padding: '6px 10px', borderRadius: 8, fontFamily: 'monospace', wordBreak: 'break-all', border: `1px solid ${t.border}` }}>
                            {v.phone_regex}
                          </code>
                        </div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 24px', borderTop: `1px solid ${t.border}`, display: 'flex', justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={t.btnSecondary}>Close</button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={rollbackTarget !== null}
        title="Rollback Regex Profile"
        message={`Roll back "${leadSourceName}" to version ${rollbackTarget?.version}? The current configuration will be replaced.`}
        confirmLabel="Rollback"
        onConfirm={handleRollbackConfirm}
        onCancel={() => setRollbackTarget(null)}
      />
    </div>
  );
};
