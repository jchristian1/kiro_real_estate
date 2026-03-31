/**
 * ActivityTab — paginated table of LeadStageHistory entries.
 * Requirements: 9.7
 */

import React, { useState } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';

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
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, overflow: 'hidden' }}>
      <div style={{ padding: '18px 24px', borderBottom: `1px solid ${t.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>Stage Activity</div>
          <div style={{ fontSize: 12, color: t.textMuted, marginTop: 4 }}>Recent lead stage transitions across this pipeline.</div>
        </div>
      </div>

      <ActivityFeed page={page} perPage={PER_PAGE} />

      <div style={{ padding: '12px 24px', borderTop: `1px solid ${t.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: page === 1 ? t.textFaint : t.textMuted, fontSize: 13, padding: '6px 14px', cursor: page === 1 ? 'default' : 'pointer' }}
        >
          Previous
        </button>
        <span style={{ fontSize: 13, color: t.textMuted }}>Page {page}</span>
        <button
          onClick={() => setPage(p => p + 1)}
          style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '6px 14px', cursor: 'pointer' }}
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
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          {COLS.map(h => (
            <th key={h} style={{
              textAlign: 'left', padding: '10px 24px',
              fontSize: 11, fontWeight: 600, color: t.textFaint,
              textTransform: 'uppercase', letterSpacing: '0.5px',
              borderBottom: `1px solid ${t.border}`,
            }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td colSpan={6} style={{ padding: '40px 24px', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
            Stage activity will appear here as leads move through the pipeline.
          </td>
        </tr>
      </tbody>
    </table>
  );
};
