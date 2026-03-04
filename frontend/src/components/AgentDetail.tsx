/**
 * Agent Detail Component
 *
 * Displays agent configuration and associated watcher status.
 * Provides watcher control buttons: Start, Stop, and Sync.
 *
 * - Shows agent_id, email, created_at, updated_at
 * - Shows watcher status (running/stopped/failed) with color badge
 * - Shows last heartbeat and last sync timestamps
 * - Start button (visible when watcher is stopped/not running)
 * - Stop button (visible when watcher is running)
 * - Sync button (always visible)
 *
 * Requirements: 1.6
 */

import React, { useEffect, useState, useCallback } from 'react';
import axios, { AxiosError } from 'axios';

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

export interface AgentDetailProps {
  /** The agent_id to display details for */
  agentId: string;
  /** Optional callback when the user navigates back */
  onBack?: () => void;
}

/**
 * Format a timestamp for human-readable display.
 * Appends 'Z' if no timezone info present (backend returns UTC without Z).
 */
const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return 'Never';
  // Ensure the timestamp is treated as UTC
  const utcTimestamp = timestamp.endsWith('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z';
  const date = new Date(utcTimestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  return date.toLocaleString();
};

/**
 * Return Tailwind classes for a watcher status badge.
 */
const getStatusColor = (status: string): string => {
  switch (status.toLowerCase()) {
    case 'running':
      return 'bg-green-100 text-green-800';
    case 'stopped':
      return 'bg-gray-100 text-gray-800';
    case 'failed':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-yellow-100 text-yellow-800';
  }
};

export const AgentDetail: React.FC<AgentDetailProps> = ({ agentId, onBack }) => {
  const [agent, setAgent] = useState<AgentDetailData | null>(null);
  const [watcherStatus, setWatcherStatus] = useState<WatcherStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null); // 'start' | 'stop' | 'sync'
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  /**
   * Fetch agent details and watcher status in parallel.
   */
  const fetchData = useCallback(async () => {
    try {
      const [agentRes, watchersRes] = await Promise.all([
        axios.get<AgentDetailData>(`${API_BASE_URL}/agents/${agentId}`),
        axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`),
      ]);

      setAgent(agentRes.data);

      const status = watchersRes.data.watchers.find((w) => w.agent_id === agentId) ?? null;
      setWatcherStatus(status);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch agent details:', err);
      setError('Failed to load agent details');
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchData();
    // Poll every 15 seconds to keep status fresh
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  /**
   * Execute a watcher control action (start / stop / sync).
   */
  const handleWatcherAction = async (action: 'start' | 'stop' | 'sync') => {
    setActionLoading(action);
    setActionError(null);
    setActionSuccess(null);

    try {
      await axios.post(`${API_BASE_URL}/watchers/${agentId}/${action}`);

      const successMessages: Record<string, string> = {
        start: 'Watcher started successfully',
        stop: 'Watcher stopped successfully',
        sync: 'Sync triggered successfully',
      };
      setActionSuccess(successMessages[action]);

      // Refresh watcher status after action
      const watchersRes = await axios.get<{ watchers: WatcherStatus[] }>(
        `${API_BASE_URL}/watchers/status`
      );
      const status = watchersRes.data.watchers.find((w) => w.agent_id === agentId) ?? null;
      setWatcherStatus(status);
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string; detail?: string }>;
      const msg =
        axiosError.response?.data?.message ||
        axiosError.response?.data?.detail ||
        `Failed to ${action} watcher`;
      setActionError(msg);
    } finally {
      setActionLoading(null);
    }
  };

  const isRunning = watcherStatus?.status?.toLowerCase() === 'running';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="agent-detail-loading">
        <div className="text-gray-600">Loading agent details...</div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="agent-detail-error">
        <div className="text-red-600">{error ?? 'Agent not found'}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="agent-detail">
      {/* Header */}
      <div className="flex items-center gap-4">
        {onBack && (
          <button
            onClick={onBack}
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
            data-testid="back-button"
          >
            ← Back
          </button>
        )}
        <h1 className="text-2xl font-bold text-gray-800">Agent: {agent.agent_id}</h1>
      </div>

      {/* Action feedback */}
      {actionSuccess && (
        <div
          className="p-3 bg-green-100 border border-green-400 text-green-700 rounded"
          role="status"
          data-testid="action-success"
        >
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div
          className="p-3 bg-red-100 border border-red-400 text-red-700 rounded"
          role="alert"
          data-testid="action-error"
        >
          {actionError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agent Configuration */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Configuration</h2>
          <dl className="space-y-3">
            <div>
              <dt className="text-xs text-gray-500 uppercase tracking-wide">Agent ID</dt>
              <dd className="mt-1 text-sm font-medium text-gray-900" data-testid="agent-id">
                {agent.agent_id}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500 uppercase tracking-wide">Email</dt>
              <dd className="mt-1 text-sm text-gray-900" data-testid="agent-email">
                {agent.email}
              </dd>
            </div>
            {agent.display_name && (
              <div>
                <dt className="text-xs text-gray-500 uppercase tracking-wide">Display Name</dt>
                <dd className="mt-1 text-sm text-gray-900" data-testid="agent-display-name">
                  {agent.display_name}
                </dd>
              </div>
            )}
            {agent.phone && (
              <div>
                <dt className="text-xs text-gray-500 uppercase tracking-wide">Phone</dt>
                <dd className="mt-1 text-sm text-gray-900" data-testid="agent-phone">
                  {agent.phone}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-gray-500 uppercase tracking-wide">Created</dt>
              <dd className="mt-1 text-sm text-gray-500" data-testid="agent-created-at">
                {new Date(agent.created_at).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500 uppercase tracking-wide">Last Updated</dt>
              <dd className="mt-1 text-sm text-gray-500" data-testid="agent-updated-at">
                {new Date(agent.updated_at).toLocaleString()}
              </dd>
            </div>
          </dl>
        </div>

        {/* Watcher Status */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Watcher Status</h2>

          {watcherStatus ? (
            <dl className="space-y-3">
              <div>
                <dt className="text-xs text-gray-500 uppercase tracking-wide">Status</dt>
                <dd className="mt-1">
                  <span
                    className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(
                      watcherStatus.status
                    )}`}
                    data-testid="watcher-status-badge"
                  >
                    {watcherStatus.status}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500 uppercase tracking-wide">Last Heartbeat</dt>
                <dd className="mt-1 text-sm text-gray-700" data-testid="watcher-last-heartbeat">
                  {formatTimestamp(watcherStatus.last_heartbeat)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500 uppercase tracking-wide">Last Sync</dt>
                <dd className="mt-1 text-sm text-gray-700" data-testid="watcher-last-sync">
                  {formatTimestamp(watcherStatus.last_sync)}
                </dd>
              </div>
              {watcherStatus.error && (
                <div>
                  <dt className="text-xs text-red-600 uppercase tracking-wide font-medium">
                    Error
                  </dt>
                  <dd
                    className="mt-1 text-sm text-red-700 bg-red-50 p-2 rounded"
                    data-testid="watcher-error"
                  >
                    {watcherStatus.error}
                  </dd>
                </div>
              )}
            </dl>
          ) : (
            <p className="text-sm text-gray-500" data-testid="watcher-not-started">
              Watcher has not been started for this agent.
            </p>
          )}

          {/* Watcher Control Buttons */}
          <div className="flex gap-3 mt-6" data-testid="watcher-controls">
            {/* Start — shown when not running */}
            {!isRunning && (
              <button
                onClick={() => handleWatcherAction('start')}
                disabled={actionLoading !== null}
                className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="start-button"
              >
                {actionLoading === 'start' ? 'Starting...' : 'Start'}
              </button>
            )}

            {/* Stop — shown when running */}
            {isRunning && (
              <button
                onClick={() => handleWatcherAction('stop')}
                disabled={actionLoading !== null}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="stop-button"
              >
                {actionLoading === 'stop' ? 'Stopping...' : 'Stop'}
              </button>
            )}

            {/* Sync — always shown */}
            <button
              onClick={() => handleWatcherAction('sync')}
              disabled={actionLoading !== null}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="sync-button"
            >
              {actionLoading === 'sync' ? 'Syncing...' : 'Sync'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
