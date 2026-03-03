/**
 * WatcherControls Component
 *
 * Displays watcher status with start/stop/sync controls per agent.
 * Polls status every 5 seconds. Shows confirmation before stopping.
 *
 * Requirements: 4.1, 4.6, 4.7, 15.4, 15.5, 15.6, 16.2, 16.3, 16.4, 16.5
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios, { AxiosError } from 'axios';
import { ConfirmDialog } from './ConfirmDialog';

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

const statusColor = (s: string) => {
  switch (s.toLowerCase()) {
    case 'running': return 'bg-green-100 text-green-800';
    case 'stopped': return 'bg-gray-100 text-gray-800';
    case 'failed': return 'bg-red-100 text-red-800';
    default: return 'bg-yellow-100 text-yellow-800';
  }
};

export const WatcherControls: React.FC = () => {
  const [watchers, setWatchers] = useState<WatcherStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null); // `${agentId}-${action}`
  const [stopTarget, setStopTarget] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ agentId: string; msg: string; isError: boolean } | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`);
      setWatchers(res.data.watchers);
    } catch {
      // silently ignore poll errors
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const doAction = async (agentId: string, action: 'start' | 'stop' | 'sync') => {
    setActionLoading(`${agentId}-${action}`);
    setFeedback(null);
    try {
      await axios.post(`${API_BASE_URL}/watchers/${agentId}/${action}`);
      setFeedback({ agentId, msg: `${action.charAt(0).toUpperCase() + action.slice(1)} successful`, isError: false });
      await fetchStatus();
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      setFeedback({ agentId, msg: e.response?.data?.detail || e.response?.data?.message || `Failed to ${action}`, isError: true });
    } finally {
      setActionLoading(null);
    }
  };

  const handleStopConfirm = async () => {
    if (!stopTarget) return;
    setStopTarget(null);
    await doAction(stopTarget, 'stop');
  };

  if (loading) return <div className="flex items-center justify-center h-32" data-testid="watcher-controls-loading"><span className="text-gray-500">Loading watchers...</span></div>;

  if (watchers.length === 0) return (
    <div className="bg-white rounded-lg shadow p-8 text-center" data-testid="watcher-controls-empty">
      <p className="text-gray-500">No watchers configured. Create an agent to get started.</p>
    </div>
  );

  return (
    <div className="space-y-4" data-testid="watcher-controls">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {watchers.map((w) => {
          const isRunning = w.status.toLowerCase() === 'running';
          const busy = actionLoading?.startsWith(w.agent_id) ?? false;
          const fb = feedback?.agentId === w.agent_id ? feedback : null;

          return (
            <div key={w.agent_id} className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm" data-testid={`watcher-card-${w.agent_id}`}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-800 truncate" title={w.agent_id}>{w.agent_id}</h3>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColor(w.status)}`} data-testid={`status-badge-${w.agent_id}`}>{w.status}</span>
              </div>

              <div className="space-y-1 mb-3 text-sm">
                <div className="flex justify-between"><span className="text-gray-500 text-xs">Last Heartbeat</span><span className="text-gray-700 text-xs" data-testid={`heartbeat-${w.agent_id}`}>{formatTs(w.last_heartbeat)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500 text-xs">Last Sync</span><span className="text-gray-700 text-xs" data-testid={`last-sync-${w.agent_id}`}>{formatTs(w.last_sync)}</span></div>
              </div>

              {w.error && <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700" data-testid={`watcher-error-${w.agent_id}`}>{w.error}</div>}

              {fb && (
                <div className={`mb-3 p-2 rounded text-xs ${fb.isError ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`} data-testid={`feedback-${w.agent_id}`}>{fb.msg}</div>
              )}

              <div className="flex gap-2" data-testid={`controls-${w.agent_id}`}>
                {!isRunning && (
                  <button onClick={() => doAction(w.agent_id, 'start')} disabled={busy}
                    className="flex-1 px-2 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
                    data-testid={`start-btn-${w.agent_id}`}>
                    {actionLoading === `${w.agent_id}-start` ? 'Starting…' : 'Start'}
                  </button>
                )}
                {isRunning && (
                  <button onClick={() => setStopTarget(w.agent_id)} disabled={busy}
                    className="flex-1 px-2 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
                    data-testid={`stop-btn-${w.agent_id}`}>
                    {actionLoading === `${w.agent_id}-stop` ? 'Stopping…' : 'Stop'}
                  </button>
                )}
                <button onClick={() => doAction(w.agent_id, 'sync')} disabled={busy}
                  className="flex-1 px-2 py-1 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
                  data-testid={`sync-btn-${w.agent_id}`}>
                  {actionLoading === `${w.agent_id}-sync` ? 'Syncing…' : 'Sync'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <ConfirmDialog
        isOpen={stopTarget !== null}
        title="Stop Watcher"
        message={`Are you sure you want to stop the watcher for agent "${stopTarget}"?`}
        confirmLabel="Stop"
        isDangerous
        onConfirm={handleStopConfirm}
        onCancel={() => setStopTarget(null)}
      />
    </div>
  );
};
