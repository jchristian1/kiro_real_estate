/**
 * ActivityTab — paginated table of LeadStageHistory entries.
 * Requirements: 9.7
 */

import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts';
import { getTokens } from '@/shared/utils';
import styles from './index.module.css';

interface Props { pipelineId: number; }

// Activity tab shows recent stage history across all leads.
// We use a lead ID of 0 as a sentinel to indicate "all leads" — the backend
// should handle this, but for now we show a placeholder if no leadId is given.
export const ActivityTab: React.FC<Props> = ({ pipelineId: _pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [page, setPage] = useState(1);
  const PER_PAGE = 20;

  // Note: the current API returns history per-lead. A pipeline-wide activity
  // feed would require a dedicated endpoint. For now we show a helpful message
  // and the component is ready to wire up once that endpoint exists.

  return (
    <div className={styles.wrapper} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
      <div className={styles.headerRow} style={{ borderBottom: `1px solid ${t.border}` }}>
        <div>
          <div className={styles.headerTitle} style={{ color: t.text }}>Stage Activity</div>
          <div className={styles.headerSub} style={{ color: t.textMuted }}>Recent lead stage transitions across this pipeline.</div>
        </div>
      </div>

      <ActivityFeed page={page} perPage={PER_PAGE} />

      <div className={styles.paginationRow} style={{ borderTop: `1px solid ${t.border}` }}>
        <button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          className={styles.pageBtn}
          style={{ border: `1px solid ${t.border}`, color: page === 1 ? t.textFaint : t.textMuted, cursor: page === 1 ? 'default' : 'pointer' }}
        >
          Previous
        </button>
        <span className={styles.pageLabel} style={{ color: t.textMuted }}>Page {page}</span>
        <button
          onClick={() => setPage(p => p + 1)}
          className={styles.pageBtn}
          style={{ border: `1px solid ${t.border}`, color: t.textMuted, cursor: 'pointer' }}
        >
          Next
        </button>
      </div>
    </div>
  );
};

// ── Activity feed placeholder ─────────────────────────────────────────────
// Renders a table shell. Wire up to a real paginated endpoint when available.

const ActivityFeed: React.FC<{ page: number; perPage: number }> = ({ page: _page }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  const COLS = ['Lead', 'From Stage', 'To Stage', 'Source', 'Reason', 'When'];

  return (
    <table className={styles.feedTable}>
      <thead>
        <tr>
          {COLS.map(h => (
            <th key={h} className={styles.colHeader} style={{
              color: t.textFaint,
              borderBottom: `1px solid ${t.border}`,
            }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td colSpan={6} className={styles.emptyCell} style={{ color: t.textMuted }}>
            Stage activity will appear here as leads move through the pipeline.
          </td>
        </tr>
      </tbody>
    </table>
  );
};
