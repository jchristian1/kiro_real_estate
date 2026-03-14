/**
 * Agent Detail Component
 * Requirements: 1.6
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios, { AxiosError } from 'axios';
import { useT } from '../../../shared/hooks/useT';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface AgentDetailData {
  id: number;
  agent_id: string;
  email: string;
  display_name: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface WatcherStatus {
  agent_id: string;
  status: string;
  last_heartbeat: string | null;
  last_sync: string | null;
  error: string | null;
}

interface AgentTemplate {
  id?: number;
  type: string; label: string; name: string; subject: string; body: string;
  is_custom: boolean; is_active: boolean; version: number;
}

export interface AgentDetailProps {
  agentId: string;
  onBack?: () => void;
}

const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return 'Never';
  const utcTimestamp = timestamp.endsWith('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z';
  const date = new Date(utcTimestamp);
  const diffMs = Date.now() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleString();
};

export const AgentDetail: React.FC<AgentDetailProps> = ({ agentId, onBack }) => {
  const t = useT();
  const [agent, setAgent] = useState<AgentDetailData | null>(null);
  const [watcherStatus, setWatcherStatus] = useState<WatcherStatus | null>(null);
  const [agentTemplates, setAgentTemplates] = useState<AgentTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [agentRes, watchersRes, templatesRes] = await Promise.all([
        axios.get<AgentDetailData>(`${API_BASE_URL}/agents/${agentId}`),
        axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`),
        axios.get<{ templates: AgentTemplate[] }>(`${API_BASE_URL}/agents/${agentId}/templates`).catch(() => ({ data: { templates: [] } })),
      ]);
      setAgent(agentRes.data);
      setWatcherStatus(watchersRes.data.watchers.find((w) => w.agent_id === agentId) ?? null);
      setAgentTemplates(templatesRes.data.templates);
      setError(null);
    } catch {
      setError('Failed to load agent details');
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleWatcherAction = async (action: 'start' | 'stop' | 'sync') => {
    setActionLoading(action);
    setActionError(null);
    setActionSuccess(null);
    try {
      await axios.post(`${API_BASE_URL}/watchers/${agentId}/${action}`);
      setActionSuccess({ start: 'Watcher started', stop: 'Watcher stopped', sync: 'Sync triggered' }[action]);
      const watchersRes = await axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`);
      setWatcherStatus(watchersRes.data.watchers.find((w) => w.agent_id === agentId) ?? null);
    } catch (err) {
      const e = err as AxiosError<{ message?: string; detail?: string }>;
      setActionError(e.response?.data?.message || e.response?.data?.detail || `Failed to ${action} watcher`);
    } finally {
      setActionLoading(null);
    }
  };

  const isRunning = watcherStatus?.status?.toLowerCase() === 'running';

  const statusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running': return { color: t.green, bg: t.greenBg };
      case 'stopped': return { color: t.textMuted, bg: t.bgInput };
      case 'failed': return { color: t.red, bg: t.redBg };
      default: return { color: t.yellow, bg: t.yellowBg };
    }
  };

  const fieldRow = (label: string, value: React.ReactNode, testId?: string) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={t.labelStyle}>{label}</span>
      <span style={{ fontSize: 13, color: t.text }} data-testid={testId}>{value}</span>
    </div>
  );

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }} data-testid="agent-detail-loading">
        <span style={{ color: t.textMuted, fontSize: 14 }}>Loading agent details...</span>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }} data-testid="agent-detail-error">
        <span style={{ color: t.red, fontSize: 14 }}>{error ?? 'Agent not found'}</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }} data-testid="agent-detail">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {onBack && (
          <button onClick={onBack} data-testid="back-button"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.accent, fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}>
            ← Back
          </button>
        )}
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: t.text }}>Agent: {agent.agent_id}</h1>
      </div>

      {/* Feedback banners */}
      {actionSuccess && (
        <div role="status" data-testid="action-success"
          style={{ padding: '10px 14px', background: t.greenBg, border: `1px solid ${t.green}30`, borderRadius: 10, fontSize: 13, color: t.green }}>
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div role="alert" data-testid="action-error"
          style={{ padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 10, fontSize: 13, color: t.red }}>
          {actionError}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        {/* Configuration card */}
        <div style={t.card}>
          <h2 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600, color: t.text }}>Configuration</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {fieldRow('Agent ID', agent.agent_id, 'agent-id')}
            {fieldRow('Email', agent.email, 'agent-email')}
            {agent.display_name && fieldRow('Display Name', agent.display_name, 'agent-display-name')}
            {agent.phone && fieldRow('Phone', agent.phone, 'agent-phone')}
            {fieldRow('Created', new Date(agent.created_at).toLocaleString(), 'agent-created-at')}
            {fieldRow('Last Updated', new Date(agent.updated_at).toLocaleString(), 'agent-updated-at')}
          </div>
        </div>

        {/* Watcher status card */}
        <div style={t.card}>
          <h2 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600, color: t.text }}>Watcher Status</h2>

          {watcherStatus ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <span style={t.labelStyle}>Status</span>
                <div style={{ marginTop: 4 }}>
                  {(() => {
                    const sc = statusColor(watcherStatus.status);
                    return (
                      <span data-testid="watcher-status-badge" style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                        background: sc.bg, color: sc.color,
                      }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: sc.color, display: 'inline-block' }} />
                        {watcherStatus.status}
                      </span>
                    );
                  })()}
                </div>
              </div>
              {fieldRow('Last Heartbeat', formatTimestamp(watcherStatus.last_heartbeat), 'watcher-last-heartbeat')}
              {fieldRow('Last Sync', formatTimestamp(watcherStatus.last_sync), 'watcher-last-sync')}
              {watcherStatus.error && (
                <div>
                  <span style={{ ...t.labelStyle, color: t.red }}>Error</span>
                  <div data-testid="watcher-error" style={{ marginTop: 4, fontSize: 13, color: t.red, background: t.redBg, padding: '8px 10px', borderRadius: 8 }}>
                    {watcherStatus.error}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p style={{ fontSize: 13, color: t.textMuted, margin: 0 }} data-testid="watcher-not-started">
              Watcher has not been started for this agent.
            </p>
          )}

          {/* Control buttons */}
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }} data-testid="watcher-controls">
            {!isRunning && (
              <button onClick={() => handleWatcherAction('start')} disabled={actionLoading !== null}
                data-testid="start-button"
                style={{ ...t.btnPrimary, background: t.greenBg, color: t.green, boxShadow: 'none', border: `1px solid ${t.green}30`, opacity: actionLoading ? 0.5 : 1 }}>
                {actionLoading === 'start' ? 'Starting...' : 'Start'}
              </button>
            )}
            {isRunning && (
              <button onClick={() => handleWatcherAction('stop')} disabled={actionLoading !== null}
                data-testid="stop-button"
                style={{ ...t.btnDanger, opacity: actionLoading ? 0.5 : 1 }}>
                {actionLoading === 'stop' ? 'Stopping...' : 'Stop'}
              </button>
            )}
            <button onClick={() => handleWatcherAction('sync')} disabled={actionLoading !== null}
              data-testid="sync-button"
              style={{ ...t.btnPrimary, opacity: actionLoading ? 0.5 : 1 }}>
              {actionLoading === 'sync' ? 'Syncing...' : 'Sync'}
            </button>
          </div>
        </div>
      </div>

      {/* Templates card */}
      {agentTemplates.length > 0 && (() => {
        const STEP_ORDER = ['INITIAL_INVITE', 'POST_HOT', 'POST_WARM', 'POST_NURTURE'];
        const byType: Record<string, AgentTemplate[]> = {};
        for (const tpl of agentTemplates) {
          if (!byType[tpl.type]) byType[tpl.type] = [];
          byType[tpl.type].push(tpl);
        }
        return (
          <div style={t.card}>
            <h2 style={{ margin: '0 0 14px', fontSize: 14, fontWeight: 600, color: t.text }}>Templates</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {STEP_ORDER.filter(type => byType[type]).map(type => {
                const stepTemplates = byType[type];
                const label = stepTemplates[0]?.label ?? type;
                return (
                  <div key={type}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                      {label}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {stepTemplates.map((tpl, idx) => (
                        <div key={tpl.id ?? `default-${idx}`} style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '10px 12px', background: t.bgInput, borderRadius: 9,
                          border: `1px solid ${tpl.is_active ? t.green + '40' : t.border}`,
                        }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                              {tpl.is_active && (
                                <span style={{ padding: '1px 7px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: t.greenBg, color: t.green }}>
                                  ✓ Active
                                </span>
                              )}
                              <span style={{ fontSize: 13, color: t.text, fontWeight: 500 }}>{tpl.name}</span>
                              {tpl.version > 0 && (
                                <span style={{ fontSize: 11, color: t.textFaint }}>v{tpl.version}</span>
                              )}
                              {!tpl.is_custom && (
                                <span style={{ padding: '1px 7px', borderRadius: 20, fontSize: 10, fontWeight: 600, background: t.bgPage, border: `1px solid ${t.border}`, color: t.textFaint }}>
                                  read-only
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: 11, color: t.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 380 }}>
                              {tpl.subject}
                            </div>
                          </div>
                          {tpl.is_custom && tpl.id != null && (
                            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                              {!tpl.is_active && (
                                <button
                                  onClick={async () => {
                                    setActionLoading(`activate-${tpl.id}`);
                                    try {
                                      await axios.post(`${API_BASE_URL}/agents/${agentId}/templates/${tpl.id}/activate`);
                                      await fetchData();
                                      setActionSuccess('Template activated');
                                    } catch {
                                      setActionError('Failed to activate template');
                                    } finally { setActionLoading(null); }
                                  }}
                                  disabled={actionLoading !== null}
                                  style={{ padding: '4px 10px', background: t.accentBg, border: `1px solid ${t.accent}40`, borderRadius: 7, fontSize: 11, fontWeight: 600, color: t.accent, cursor: 'pointer', opacity: actionLoading ? 0.5 : 1 }}>
                                  {actionLoading === `activate-${tpl.id}` ? '…' : 'Set Active'}
                                </button>
                              )}
                              <button
                                onClick={async () => {
                                  setActionLoading(`delete-${tpl.id}`);
                                  try {
                                    await axios.delete(`${API_BASE_URL}/agents/${agentId}/templates/${tpl.id}`);
                                    await fetchData();
                                    setActionSuccess('Template deleted');
                                  } catch {
                                    setActionError('Failed to delete template');
                                  } finally { setActionLoading(null); }
                                }}
                                disabled={actionLoading !== null}
                                style={{ padding: '4px 10px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 7, fontSize: 11, color: t.red, cursor: 'pointer', opacity: actionLoading ? 0.5 : 1 }}>
                                {actionLoading === `delete-${tpl.id}` ? '…' : 'Delete'}
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}
    </div>
  );
};
