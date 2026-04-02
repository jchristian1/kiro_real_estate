import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

interface AuditLog {
  id: number; timestamp: string; user_id: number; username: string;
  action: string; resource_type: string; resource_id: number | null; details: string | null;
}
interface AuditLogsResponse {
  logs: AuditLog[]; total: number; page: number; per_page: number; pages: number;
}
interface Filters { action: string; user_id: string; start_date: string; end_date: string; }

export const AuditLogsPage: React.FC = () => {
  const t = useT();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<Filters>({ action: '', user_id: '', start_date: '', end_date: '' });

  const buildParams = useCallback(() => {
    const p: Record<string, string> = { page: String(page), per_page: '100' };
    if (filters.action) p.action = filters.action;
    if (filters.user_id) p.user_id = filters.user_id;
    if (filters.start_date) p.start_date = filters.start_date;
    if (filters.end_date) p.end_date = filters.end_date;
    return p;
  }, [page, filters]);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<AuditLogsResponse>(`${API_BASE_URL}/audit-logs`, { params: buildParams() });
      setLogs(res.data.logs); setTotalPages(res.data.pages); setTotal(res.data.total); setFetchError(null);
    } catch { setFetchError('Failed to load audit logs'); }
    finally { setLoading(false); }
  }, [buildParams]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);
  const handleFilter = (key: keyof Filters, val: string) => { setFilters(f => ({ ...f, [key]: val })); setPage(1); };

  const actionColor = (action: string) => {
    if (action.includes('created')) return { color: t.green, bg: t.greenBg };
    if (action.includes('deleted')) return { color: t.red, bg: t.redBg };
    if (action.includes('updated') || action.includes('rollback')) return { color: t.yellow, bg: t.yellowBg };
    return { color: t.textMuted, bg: t.bgBadge };
  };

  const inputStyle = { ...t.input, width: '100%' };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div style={{ color: t.textMuted }}>
          <span className={styles.headerTitle} style={{ color: t.text }}>Audit Logs</span>
          <span className={styles.headerSubtitle}>{total} entries</span>
        </div>
      </div>

      {/* Filters */}
      <div style={t.card} className={styles.filtersContainer} data-testid="audit-filters">
        <div className={styles.filtersGrid}>
          {[
            { key: 'action' as const, label: 'Action', placeholder: 'e.g. agent_created', type: 'text' },
            { key: 'user_id' as const, label: 'User ID', placeholder: 'User ID', type: 'text' },
            { key: 'start_date' as const, label: 'Start Date', placeholder: '', type: 'date' },
            { key: 'end_date' as const, label: 'End Date', placeholder: '', type: 'date' },
          ].map(f => (
            <div key={f.key} className={styles.filterField}>
              <label style={t.labelStyle}>{f.label}</label>
              <input type={f.type} value={filters[f.key]} placeholder={f.placeholder}
                onChange={e => handleFilter(f.key, e.target.value)}
                style={inputStyle}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                onBlur={e => (e.target.style.borderColor = t.border)}
                data-testid={`filter-${f.key.replace('_', '-')}`} />
            </div>
          ))}
        </div>
      </div>

      {loading ? (
        <div className={styles.loadingContainer} style={{ color: t.textFaint }}>Loading…</div>
      ) : fetchError ? (
        <div className={styles.errorContainer} style={{ color: t.red }}>{fetchError}</div>
      ) : logs.length === 0 ? (
       <div className={styles.emptyState} style={{ ...t.card, color: t.textFaint }} data-testid="audit-empty">
          No audit logs found
        </div>
      ) : (
        <>
          <div style={t.card}>
            <table className={styles.table} data-testid="audit-table">
              <thead>
                <tr>
                  {['Timestamp', 'User', 'Action', 'Resource', 'Details'].map(h => (
                    <th key={h} style={t.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => {
                  const ac = actionColor(log.action);
                  return (
                    <tr key={log.id} data-testid={`audit-row-${log.id}`}
                      style={{ borderBottom: i < logs.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                      <td style={{ ...t.td, color: t.textMuted }} className={styles.timestampCell}>
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td style={{ ...t.td, fontWeight: 500 }}>{log.username}</td>
                      <td style={t.td}>
                        <span className={styles.actionBadge} style={{ color: ac.color, background: ac.bg }}>
                          {log.action}
                        </span>
                      </td>
                      <td style={{ ...t.td, color: t.textMuted }}>
                        {log.resource_type}{log.resource_id ? ` #${log.resource_id}` : ''}
                      </td>
                      <td style={{ ...t.td, color: t.textMuted }} className={styles.detailsCell}
                        title={log.details ?? ''}>
                        {log.details || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className={styles.paginationContainer} data-testid="pagination">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>Previous</button>
              <span className={styles.paginationText} style={{ color: t.textMuted }}>Page {page} of {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                style={{ ...t.btnSecondary, opacity: page === totalPages ? 0.4 : 1 }}>Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
