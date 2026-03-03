/**
 * Watcher Status Grid Component
 * 
 * Displays real-time status of all watchers in a grid layout.
 * Shows agent ID, status, last heartbeat, and last sync time.
 * 
 * Requirements: 16.2, 16.3, 16.4, 16.5
 */

import React from 'react';
import { WatcherStatus } from '../pages/DashboardPage';

interface WatcherStatusGridProps {
  watchers: WatcherStatus[];
  onRefresh: () => void;
}

export const WatcherStatusGrid: React.FC<WatcherStatusGridProps> = ({ watchers, onRefresh }) => {
  /**
   * Get status badge color based on watcher status
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

  /**
   * Format timestamp for display
   */
  const formatTimestamp = (timestamp: string | null): string => {
    if (!timestamp) return 'Never';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    
    return date.toLocaleString();
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-800">Watcher Status</h2>
        <button
          onClick={onRefresh}
          className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
        >
          Refresh
        </button>
      </div>

      {watchers.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No watchers configured. Create an agent to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {watchers.map((watcher) => (
            <div
              key={watcher.agent_id}
              className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              {/* Agent ID */}
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-800 truncate" title={watcher.agent_id}>
                  {watcher.agent_id}
                </h3>
                <span
                  className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(
                    watcher.status
                  )}`}
                >
                  {watcher.status}
                </span>
              </div>

              {/* Last Heartbeat */}
              <div className="mb-2">
                <div className="text-xs text-gray-500">Last Heartbeat</div>
                <div className="text-sm text-gray-700">
                  {formatTimestamp(watcher.last_heartbeat)}
                </div>
              </div>

              {/* Last Sync */}
              <div className="mb-2">
                <div className="text-xs text-gray-500">Last Sync</div>
                <div className="text-sm text-gray-700">
                  {formatTimestamp(watcher.last_sync)}
                </div>
              </div>

              {/* Error Message (if any) */}
              {watcher.error && (
                <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded">
                  <div className="text-xs text-red-600 font-medium mb-1">Error</div>
                  <div className="text-xs text-red-700">{watcher.error}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
