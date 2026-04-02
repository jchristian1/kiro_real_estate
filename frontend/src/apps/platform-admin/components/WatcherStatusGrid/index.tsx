import React from 'react';

import { useT } from '@/shared/hooks';
import { WatcherStatus } from '@/models';
import { formatTimestamp } from '@/shared/utils';
import styles from './index.module.css';

interface WatcherStatusGridProps {
  watchers: WatcherStatus[];
  onRefresh: () => void;
}

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
      <div className={styles.header}>
        <h2 className={styles.title} style={{ color: t.text }}>Watcher Status</h2>
        <button onClick={onRefresh} style={t.btnSecondary}>Refresh</button>
      </div>

      {watchers.length === 0 ? (
        <div className={styles.emptyState} style={{ color: t.textMuted }}>
          No watchers configured. Create an agent to get started.
        </div>
      ) : (
        <div className={styles.grid}>
          {watchers.map((watcher) => {
            const sc = statusStyle(watcher.status);
            return (
              <div key={watcher.agent_id} className={styles.card} style={{ background: t.bgInput, border: `1px solid ${t.border}` }}>
                <div className={styles.cardHeader}>
                  <h3 className={styles.agentTitle} style={{ color: t.text }} title={watcher.agent_id}>{watcher.agent_id}</h3>
                  <span className={styles.statusBadge} style={{ background: sc.bg, color: sc.color }}>{watcher.status}</span>
                </div>
                {[['Last Heartbeat', watcher.last_heartbeat], ['Last Sync', watcher.last_sync]].map(([label, val]) => (
                  <div key={label as string} className={styles.metaItem}>
                    <div className={styles.metaLabel} style={{ color: t.textFaint }}>{label}</div>
                    <div className={styles.metaValue} style={{ color: t.textSecondary }}>{formatTimestamp(val as string | null)}</div>
                  </div>
                ))}
                {watcher.error && (
                  <div className={styles.errorBox} style={{ background: t.redBg, border: `1px solid ${t.red}30` }}>
                    <div className={styles.errorTitle} style={{ color: t.red }}>Error</div>
                    <div className={styles.errorText} style={{ color: t.red }}>{watcher.error}</div>
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
