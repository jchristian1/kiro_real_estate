/**
 * TemplateVersionHistory Component
 * Requirements: 3.6, 3.7
 */
import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { ConfirmDialog } from '@/platformAdminComponents/ConfirmDialog';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import { TemplateVersion } from '@/models/app-model';
import styles from './index.module.css';

export interface TemplateVersionHistoryProps {
  templateId: number;
  templateName: string;
  onClose: () => void;
  onRollbackSuccess: () => void;
}

export const TemplateVersionHistory: React.FC<TemplateVersionHistoryProps> = ({
  templateId, templateName, onClose, onRollbackSuccess,
}) => {
  const t = useT();
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<TemplateVersion | null>(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    axios.get<{ versions: TemplateVersion[] }>(`${API_BASE_URL}/templates/${templateId}/versions`)
      .then((r) => setVersions(r.data.versions))
      .catch(() => setError('Failed to load version history'))
      .finally(() => setLoading(false));
  }, [templateId]);

  const handleRollback = async () => {
    if (!rollbackTarget) return;
    setRollbackLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/templates/${templateId}/rollback`, { version: rollbackTarget.version });
      setRollbackTarget(null);
      onRollbackSuccess();
    } catch (err) {
      const e = err as AxiosError<{ message?: string; detail?: string }>;
      setRollbackError(e.response?.data?.message || e.response?.data?.detail || 'Rollback failed');
      setRollbackTarget(null);
    } finally {
      setRollbackLoading(false);
    }
  };

  return (
    <div className={styles.overlay} data-testid="template-version-history">
      {/* Backdrop */}
      <div className={styles.backdrop} onClick={onClose} data-testid="version-history-backdrop" />

      {/* Panel */}
      <div className={styles.panel} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
        {/* Header */}
        <div className={styles.header} style={{ borderBottom: `1px solid ${t.border}` }}>
          <div>
            <h2 className={styles.headerTitle} style={{ color: t.text }} data-testid="version-history-title">Version History</h2>
            <p className={styles.headerSubtitle} style={{ color: t.textMuted }}>{templateName}</p>
          </div>
          <button onClick={onClose} aria-label="Close" data-testid="version-history-close"
            className={styles.closeBtn} style={{ color: t.textMuted }}>
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {rollbackError && (
            <div role="alert" data-testid="rollback-error" className={styles.alertBox} style={{ background: t.redBg, border: `1px solid ${t.red}30`, color: t.red }}>
              {rollbackError}
            </div>
          )}
          {loading && (
            <div className={styles.centeredState} data-testid="version-history-loading">
              <span className={styles.stateText} style={{ color: t.textMuted }}>Loading...</span>
            </div>
          )}
          {error && (
            <div className={styles.centeredState} data-testid="version-history-error">
              <span className={styles.stateText} style={{ color: t.red }}>{error}</span>
            </div>
          )}
          {!loading && !error && versions.length === 0 && (
            <div className={styles.centeredState} data-testid="version-history-empty">
              <span className={styles.stateText} style={{ color: t.textMuted }}>No version history</span>
            </div>
          )}
          {!loading && !error && versions.length > 0 && (
            <ul className={styles.versionList} data-testid="version-list">
              {versions.map((v, idx) => {
                const isLatest = idx === 0;
                const isExpanded = expanded === v.version;
                return (
                  <li key={v.version} className={styles.versionItem} style={{ border: `1px solid ${t.border}` }} data-testid={`version-item-${v.version}`}>
                    <div className={styles.versionHeader} style={{ background: t.bgInput }}>
                      <div className={styles.versionMeta}>
                        <span className={styles.versionNumber} style={{ color: t.text }}>Version {v.version}</span>
                        {isLatest && (
                          <span className={styles.currentBadge} style={{ background: t.accentBg, color: t.accent }}>Current</span>
                        )}
                        <span className={styles.versionDate} style={{ color: t.textMuted }}>{new Date(v.created_at).toLocaleString()}</span>
                      </div>
                      <div className={styles.versionActions}>
                        <button onClick={() => setExpanded(isExpanded ? null : v.version)}
                          className={styles.toggleBtn} style={{ color: t.textMuted }}
                          data-testid={`toggle-version-${v.version}`}>
                          {isExpanded ? 'Hide' : 'Details'}
                        </button>
                        {!isLatest && (
                          <button onClick={() => setRollbackTarget(v)} disabled={rollbackLoading}
                            className={styles.rollbackBtn} style={{ color: t.accent, background: t.accentBg, opacity: rollbackLoading ? 0.5 : 1 }}
                            data-testid={`rollback-button-${v.version}`}>
                            Rollback
                          </button>
                        )}
                      </div>
                    </div>
                    {isExpanded && (
                      <div className={styles.versionDetails} style={{ borderTop: `1px solid ${t.border}` }} data-testid={`version-details-${v.version}`}>
                        <div>
                          <span style={t.labelStyle}>Subject</span>
                          <p className={styles.detailSubject} style={{ color: t.textSecondary }}>{v.subject}</p>
                        </div>
                        <div>
                          <span style={t.labelStyle}>Body</span>
                          <pre className={styles.detailBody} style={{ background: t.bgInput, color: t.textSecondary, border: `1px solid ${t.border}` }}>{v.body}</pre>
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
        <div className={styles.footer} style={{ borderTop: `1px solid ${t.border}` }}>
          <button onClick={onClose} style={t.btnSecondary}>Close</button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={rollbackTarget !== null}
        title="Rollback Template"
        message={`Roll back "${templateName}" to version ${rollbackTarget?.version}? The current version will be replaced.`}
        confirmLabel="Rollback"
        onConfirm={handleRollback}
        onCancel={() => setRollbackTarget(null)}
      />
    </div>
  );
};
