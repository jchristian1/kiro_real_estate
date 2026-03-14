import React from 'react';
import { WatcherStatus } from '../pages/DashboardPage';
import { useT } from '../../../shared/hooks/useT';

interface WatcherStatusGridProps {
  watchers: WatcherStatus[];
  onRefresh: () => void;
}

const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  const diffMins = Math.floor((Date.now() - date.getTime()) / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleString();
};

export const WatcherStatusGrid: React.FC<WatcherStatusGridProps> = ({ watchers = [], onRefresh }) => {
  const t = useT();

  const statusStyle = (status: string): { bg: string; color: string } => {
    switch (status.toLowerCase()) {
      case 'running': return { bg: t.greenBg, color: t.green };
      case 'failed': return { bg: t.redBg, color: t.red };
      case 'stopped': return { bg: t.bgBadge, color: t.textMuted };
      default: return { bg: t.yellowBg, color: t.yellow };
    }
  };

  return (
    <div style={t.card}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>Watcher Status</h2>
        <button onClick={onRefresh} style={t.btnSecondary}>Refresh</button>
      </div>

      {watchers.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '32px 0', color: t.textMuted }}>
          No watchers configured. Create an agent to get started.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
          {watchers.map((watcher) => {
            const sc = statusStyle(watcher.status);
            return (
              <div key={watcher.agent_id} style={{ background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 12, padding: '14px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <h3 style={{ fontSize: 13, fontWeight: 600, color: t.text, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={watcher.agent_id}>{watcher.agent_id}</h3>
                  <span style={{ padding: '2px 8px', fontSize: 10, fontWeight: 600, background: sc.bg, color: sc.color, borderRadius: 20 }}>{watcher.status}</span>
                </div>
                {[['Last Heartbeat', watcher.last_heartbeat], ['Last Sync', watcher.last_sync]].map(([label, val]) => (
                  <div key={label as string} style={{ marginBottom: 6 }}>
                    <div style={{ fontSize: 10, color: t.textFaint }}>{label}</div>
                    <div style={{ fontSize: 12, color: t.textSecondary }}>{formatTimestamp(val as string | null)}</div>
                  </div>
                ))}
                {watcher.error && (
                  <div style={{ marginTop: 8, padding: '6px 10px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 8 }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: t.red, marginBottom: 2 }}>Error</div>
                    <div style={{ fontSize: 11, color: t.red }}>{watcher.error}</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
