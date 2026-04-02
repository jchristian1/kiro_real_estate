/**
 * Dashboard Page — theme-aware, Apple-inspired
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTheme } from '@/shared/contexts';
import { getTokens } from '@/shared/utils';
import { WatcherStatus, HealthData } from '@/models';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';



export const DashboardPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [watchers, setWatchers] = useState<WatcherStatus[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    try {
      const [h, w] = await Promise.all([
        axios.get<HealthData>(`${API_BASE_URL}/health`),
        axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`),
      ]);
      setHealth(h.data);
      setWatchers(w.data.watchers ?? []);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, []);

  const card: React.CSSProperties = {
    background: t.bgCard,
    border: `1px solid ${t.border}`,
    borderRadius: 16,
    padding: '20px 24px',
    transition: 'background 0.2s',
  };

  const dot = (ok: boolean): React.CSSProperties => ({
    display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
    background: ok ? t.green : t.red,
    marginRight: 7, flexShrink: 0,
    boxShadow: ok ? `0 0 6px ${t.green}80` : `0 0 6px ${t.red}80`,
  });

  if (loading) {
    return (
      <div className={styles.loadingContainer} style={{ color: t.textFaint }}>
        Loading…
      </div>
    );
  }

  const isHealthy = health?.status === 'healthy';
  const dbOk = health?.database === 'connected';
  const activeWatchers = health?.active_watchers ?? 0;
  const errors24h = health?.errors_last_24h ?? 0;

  return (
    <div style={{ maxWidth: 960 }}>
      {/* Status bar */}
      <div className={styles.statusBar}>
        <span className={styles.dot} style={{ background: isHealthy ? t.green : t.red, boxShadow: isHealthy ? `0 0 6px ${t.green}80` : `0 0 6px ${t.red}80` }} />
        <span className={styles.statusBarText} style={{ color: isHealthy ? t.green : t.red }}>
          {isHealthy ? 'All systems operational' : 'System degraded'}
        </span>
        {health && (
          <span className={styles.statusBarSubtext} style={{ color: t.textFaint }}>
            · {activeWatchers} watcher{activeWatchers !== 1 ? 's' : ''} running
          </span>
        )}
        <button
          onClick={fetchAll}
          className={styles.refreshButtonStyle}
          style={{
            background: t.bgCard, border: `1px solid ${t.border}`,
            color: t.textMuted,
          }}
        >
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div className={styles.metricsGrid}>
        {[
          { label: 'Database', value: dbOk ? 'Connected' : 'Disconnected', ok: dbOk },
          { label: 'Active Watchers', value: String(activeWatchers), ok: activeWatchers > 0 },
          { label: 'Errors (24h)', value: String(errors24h), ok: errors24h === 0 },
        ].map(s => (
          <div key={s.label} className={styles.metricCard} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
            <div className={styles.metricLabel} style={{ color: t.textFaint }}>
              {s.label}
            </div>
            <div className={styles.metricValue}>
              <span className={styles.dot} style={{ background: s.ok ? t.green : t.red, boxShadow: s.ok ? `0 0 6px ${t.green}80` : `0 0 6px ${t.red}80` }} />
              <span style={{ color: t.text }}>{s.value}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Watchers table */}
      <div className={styles.card} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
        <div className={styles.watchersTitle} style={{ color: t.text }}>Watchers</div>

        {watchers.length === 0 ? (
          <div className={styles.emptyState} style={{ color: t.textFaint }}>No watchers configured.</div>
        ) : (
          <table className={styles.watchersTable}>
            <thead>
              <tr>
                {['Agent', 'Status', 'Last Sync', 'Error'].map(h => (
                  <th key={h} className={styles.watchersTableHeader} style={{
                    color: t.textFaint,
                    borderBottom: `1px solid ${t.border}`,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {watchers.map((w, i) => (
                <tr key={w.agent_id} style={{ borderBottom: i < watchers.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                  <td className={styles.watchersTableCell} style={{ color: t.text, fontWeight: 500 }}>{w.agent_id}</td>
                  <td className={styles.watchersTableCell}>
                    <span className={styles.watcherStatusBadgeStyle}
                      style={{
                        background: w.status === 'running' ? t.greenBg : t.redBg,
                        color: w.status === 'running' ? t.green : t.red,
                      }}>
                      <span className={styles.dot} style={{ background: w.status === 'running' ? t.green : t.red, boxShadow: w.status === 'running' ? `0 0 6px ${t.green}80` : `0 0 6px ${t.red}80` }} />
                      {w.status}
                    </span>
                  </td>
                  <td className={styles.watchersTableCell} style={{ color: t.textMuted, fontSize: 12 }}>
                    {w.last_sync ? new Date(w.last_sync).toLocaleString() : '—'}
                  </td>
                  <td className={styles.watcherErrorCellStyle} style={{ color: t.red }}>
                    {w.error || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
