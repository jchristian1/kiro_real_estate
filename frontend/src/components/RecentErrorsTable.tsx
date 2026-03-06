/**
 * Recent Errors Table Component
 *
 * Displays errors from the last 24 hours.
 * Requirements: 8.6, 16.3
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useT } from '../utils/useT';

interface RecentErrorsTableProps {
  errorCount: number;
}

export const RecentErrorsTable: React.FC<RecentErrorsTableProps> = ({ errorCount }) => {
  const navigate = useNavigate();
  const t = useT();

  return (
    <div style={{ ...t.card }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>Recent Errors (24h)</h2>
        <button
          onClick={() => navigate('/audit-logs')}
          style={{
            padding: '7px 14px',
            background: t.accentBg,
            border: `1px solid ${t.accent}30`,
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 500,
            color: t.accent,
            cursor: 'pointer',
          }}
        >
          View Audit Logs
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 0' }}>
        {errorCount === 0 ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 56, height: 56, background: t.greenBg, borderRadius: '50%', marginBottom: 12,
            }}>
              <svg width="24" height="24" fill="none" stroke={t.green} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>No errors in the last 24 hours</div>
            <div style={{ fontSize: 12, color: t.textMuted, marginTop: 4 }}>System is running smoothly</div>
          </div>
        ) : (
          <div style={{ textAlign: 'center' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 56, height: 56, background: t.orangeBg, borderRadius: '50%', marginBottom: 12,
            }}>
              <svg width="24" height="24" fill="none" stroke={t.orange} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>
              {errorCount} {errorCount === 1 ? 'error' : 'errors'} detected
            </div>
            <div style={{ fontSize: 12, color: t.textMuted, marginTop: 4 }}>
              Click "View Audit Logs" to see details
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
