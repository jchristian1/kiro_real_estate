import React, { useEffect, useState, useCallback } from 'react';
import axios, { AxiosError } from 'axios';
import { ConfirmDialog } from '@/platformAdminComponents/ConfirmDialog';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import { WatcherStatus } from '@/models/platform-admin';
import { POLL_INTERVAL_MS } from '@/shared/utils/config/const-app';
import { formatTs } from '@/shared/utils/helpers';
import styles from './index.module.css';


export const WatcherControls: React.FC = () => {
  const t = useT();
  const [watchers, setWatchers] = useState<WatcherStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [stopTarget, setStopTarget] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ agentId: string; msg: string; isError: boolean } | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`);
      setWatchers(res.data.watchers);
    } catch { /* silent */ } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const doAction = async (agentId: string, action: 'start' | 'stop' | 'sync') => {
    setActionLoading(`${agentId}-${action}`); setFeedback(null);
    try {
      await axios.post(`${API_BASE_URL}/watchers/${agentId}/${action}`);
      setFeedback({ agentId, msg: `${action.charAt(0).toUpperCase() + action.slice(1)} successful`, isError: false });
      await fetchStatus();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      setFeedback({ agentId, msg: e.response?.data?.detail || e.response?.data?.message || `Failed to ${action}`, isError: true });
    } finally { setActionLoading(null); }
  };

  const handleStopConfirm = async () => {
    if (!stopTarget) return;
    setStopTarget(null);
    await doAction(stopTarget, 'stop');
  };

  if (loading) return <div className={styles.loadingContainer} style={{ color: t.textMuted }} data-testid="watcher-controls-loading">Loading watchers…</div>;

  if (watchers.length === 0) return (
    <div className={styles.emptyContainer} style={t.card} data-testid="watcher-controls-empty">
      <p style={{ color: t.textMuted }}>No watchers configured. Create an agent to get started.</p>
    </div>
  );

  return (
    <div className={styles.container} data-testid="watcher-controls">
      <div className={styles.grid}>
        {watchers.map((w) => {
          const isRunning = w.status.toLowerCase() === 'running';
          const busy = actionLoading?.startsWith(w.agent_id) ?? false;
          const fb = feedback?.agentId === w.agent_id ? feedback : null;
          const statusColor = isRunning ? t.green : w.status.toLowerCase() === 'failed' ? t.red : t.textMuted;
          const statusBg = isRunning ? t.greenBg : w.status.toLowerCase() === 'failed' ? t.redBg : t.bgBadge;

          return (
            <div key={w.agent_id} style={t.card} data-testid={`watcher-card-${w.agent_id}`}>
              <div className={styles.cardHeader}>
                <h3 className={styles.agentTitle} style={{ color: t.text }} title={w.agent_id}>{w.agent_id}</h3>
                <span className={styles.statusBadge} style={{ background: statusBg, color: statusColor }} data-testid={`status-badge-${w.agent_id}`}>{w.status}</span>
              </div>

              <div className={styles.metaColumn}>
                {[['Last Heartbeat', w.last_heartbeat, `heartbeat-${w.agent_id}`], ['Last Sync', w.last_sync, `last-sync-${w.agent_id}`]].map(([label, val, testId]) => (
                  <div key={label as string} className={styles.metaRow}>
                    <span className={styles.metaLabel} style={{ color: t.textFaint }}>{label}</span>
                    <span className={styles.metaValue} style={{ color: t.textMuted }} data-testid={testId as string}>{formatTs(val as string | null)}</span>
                  </div>
                ))}
              </div>

              {w.error && <div className={styles.errorBox} style={{ background: t.redBg, border: `1px solid ${t.red}30`, color: t.red }} data-testid={`watcher-error-${w.agent_id}`}>{w.error}</div>}
              {fb && <div className={styles.feedbackBox} style={{ background: fb.isError ? t.redBg : t.greenBg, color: fb.isError ? t.red : t.green }} data-testid={`feedback-${w.agent_id}`}>{fb.msg}</div>}

              <div className={styles.controlsRow} data-testid={`controls-${w.agent_id}`}>
                {!isRunning && (
                  <button onClick={() => doAction(w.agent_id, 'start')} disabled={busy}
                    className={styles.actionBtn}
                    style={{ background: t.greenBg, color: t.green, border: `1px solid ${t.green}30`, opacity: busy ? 0.5 : 1 }}
                    data-testid={`start-btn-${w.agent_id}`}>
                    {actionLoading === `${w.agent_id}-start` ? 'Starting…' : 'Start'}
                  </button>
                )}
                {isRunning && (
                  <button onClick={() => setStopTarget(w.agent_id)} disabled={busy}
                    className={styles.actionBtn}
                    style={{ background: t.redBg, color: t.red, border: `1px solid ${t.red}30`, opacity: busy ? 0.5 : 1 }}
                    data-testid={`stop-btn-${w.agent_id}`}>
                    {actionLoading === `${w.agent_id}-stop` ? 'Stopping…' : 'Stop'}
                  </button>
                )}
                <button onClick={() => doAction(w.agent_id, 'sync')} disabled={busy}
                  className={styles.actionBtn}
                  style={{ ...t.btnPrimary, padding: '6px 10px', fontSize: 12, opacity: busy ? 0.5 : 1 }}
                  data-testid={`sync-btn-${w.agent_id}`}>
                  {actionLoading === `${w.agent_id}-sync` ? 'Syncing…' : 'Sync'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <ConfirmDialog isOpen={stopTarget !== null} title="Stop Watcher"
        message={`Are you sure you want to stop the watcher for agent "${stopTarget}"?`}
        confirmLabel="Stop" isDangerous onConfirm={handleStopConfirm} onCancel={() => setStopTarget(null)} />
    </div>
  );
};
