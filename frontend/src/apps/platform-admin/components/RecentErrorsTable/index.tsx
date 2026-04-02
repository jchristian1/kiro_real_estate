/**
 * Recent Errors Table Component
 *
 * Displays errors from the last 24 hours.
 * Requirements: 8.6, 16.3
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useT } from '@/shared/hooks/useT';
import styles from './index.module.css';

interface RecentErrorsTableProps {
  errorCount: number;
}

export const RecentErrorsTable: React.FC<RecentErrorsTableProps> = ({ errorCount }) => {
  const navigate = useNavigate();
  const t = useT();

  return (
    <div style={{ ...t.card }}>
      <div className={styles.header}>
        <h2 className={styles.title} style={{ color: t.text }}>Recent Errors (24h)</h2>
        <button
          onClick={() => navigate('/audit-logs')}
          className={styles.viewButton}
          style={{
            background: t.accentBg,
            border: `1px solid ${t.accent}30`,
            color: t.accent,
          }}
        >
          View Audit Logs
        </button>
      </div>

      <div className={styles.centerContent}>
        {errorCount === 0 ? (
          <div className={styles.statusContent}>
            <div className={styles.iconCircle} style={{ background: t.greenBg }}>
              <svg width="24" height="24" fill="none" stroke={t.green} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div className={styles.statusTitle} style={{ color: t.text }}>No errors in the last 24 hours</div>
            <div className={styles.statusSubtitle} style={{ color: t.textMuted }}>System is running smoothly</div>
          </div>
        ) : (
          <div className={styles.statusContent}>
            <div className={styles.iconCircle} style={{ background: t.orangeBg }}>
              <svg width="24" height="24" fill="none" stroke={t.orange} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className={styles.statusTitle} style={{ color: t.text }}>
              {errorCount} {errorCount === 1 ? 'error' : 'errors'} detected
            </div>
            <div className={styles.statusSubtitle} style={{ color: t.textMuted }}>
              Click "View Audit Logs" to see details
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
