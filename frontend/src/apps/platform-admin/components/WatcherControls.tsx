import React, { useEffect, useState, useCallback } from 'react';
import axios, { AxiosError } from 'axios';
import { ConfirmDialog } from './ConfirmDialog';
import { useT } from '../../../shared/hooks/useT';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const POLL_INTERVAL_MS = 5000;

export interface WatcherStatus {
  agent_id: string;
  status: string;
  last_heartbeat: string | null;
  last_sync: string | null;
  error: string | null;
}

const formatTs = (ts: string | null): string => {
  if (!ts) return 'Never';
  const d = new Date(ts);
  const diffMins = Math.floor((Date.now() - d.getTime()) / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffH = Math.floor(diffMins / 60);
  if (diffH < 24) return `${diffH}h ago`;
  return d.toLocaleString();
};

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

  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120, color: t.textMuted }} data-testid="watcher-controls-loading">Loading watchers…</div>;

  if (watchers.length === 0) return (
    <div style={{ ...t.card, textAlign: 'center', padding: '48px 24px' }} data-testid="watcher-controls-empty">
      <p style={{ color: t.textMuted }}>No watchers configured. Create an agent to get started.</p>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="watcher-controls">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
        {watchers.map((w) => {
          const isRunning = w.status.toLowerCase() === 'running';
          const busy = actionLoading?.startsWith(w.agent_id) ?? false;
          const fb = feedback?.agentId === w.agent_id ? feedback : null;
          const statusColor = isRunning ? t.green : w.status.toLowerCase() === 'failed' ? t.red : t.textMuted;
          const statusBg = isRunning ? t.greenBg : w.status.toLowerCase() === 'failed' ? t.redBg : t.bgBadge;

          return (
            <div key={w.agent_id} style={t.card} data-testid={`watcher-card-${w.agent_id}`}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <h3 style={{ fontSize: 13, fontWeight: 600, color: t.text, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={w.agent_id}>{w.agent_id}</h3>
                <span style={{ padding: '2px 8px', fontSize: 10, fontWeight: 600, background: statusBg, color: statusColor, borderRadius: 20 }} data-testid={`status-badge-${w.agent_id}`}>{w.status}</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 }}>
                {[['Last Heartbeat', w.last_heartbeat, `heartbeat-${w.agent_id}`], ['Last Sync', w.last_sync, `last-sync-${w.agent_id}`]].map(([label, val, testId]) => (
                  <div key={label as string} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 11, color: t.textFaint }}>{label}</span>
                    <span style={{ fontSize: 11, color: t.textMuted }} data-testid={testId as string}>{formatTs(val as string | null)}</span>
                  </div>
                ))}
              </div>

              {w.error && <div style={{ marginBottom: 10, padding: '6px 10px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 8, fontSize: 11, color: t.red }} data-testid={`watcher-error-${w.agent_id}`}>{w.error}</div>}
              {fb && <div style={{ marginBottom: 10, padding: '6px 10px', background: fb.isError ? t.redBg : t.greenBg, borderRadius: 8, fontSize: 11, color: fb.isError ? t.red : t.green }} data-testid={`feedback-${w.agent_id}`}>{fb.msg}</div>}

              <div style={{ display: 'flex', gap: 8 }} data-testid={`controls-${w.agent_id}`}>
                {!isRunning && (
                  <button onClick={() => doAction(w.agent_id, 'start')} disabled={busy}
                    style={{ flex: 1, padding: '6px 10px', fontSize: 12, fontWeight: 600, background: t.greenBg, color: t.green, border: `1px solid ${t.green}30`, borderRadius: 8, cursor: 'pointer', opacity: busy ? 0.5 : 1 }}
                    data-testid={`start-btn-${w.agent_id}`}>
                    {actionLoading === `${w.agent_id}-start` ? 'Starting…' : 'Start'}
                  </button>
                )}
                {isRunning && (
                  <button onClick={() => setStopTarget(w.agent_id)} disabled={busy}
                    style={{ flex: 1, padding: '6px 10px', fontSize: 12, fontWeight: 600, background: t.redBg, color: t.red, border: `1px solid ${t.red}30`, borderRadius: 8, cursor: 'pointer', opacity: busy ? 0.5 : 1 }}
                    data-testid={`stop-btn-${w.agent_id}`}>
                    {actionLoading === `${w.agent_id}-stop` ? 'Stopping…' : 'Stop'}
                  </button>
                )}
                <button onClick={() => doAction(w.agent_id, 'sync')} disabled={busy}
                  style={{ flex: 1, ...t.btnPrimary, padding: '6px 10px', fontSize: 12, opacity: busy ? 0.5 : 1 }}
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
