/**
 * Health Metrics Component
 * Requirements: 8.5, 16.1
 */
import React from 'react';
import { useT } from '@/shared/hooks';
import { HealthData } from '@/models';
import styles from './index.module.css';

interface HealthMetricsProps {
  healthData: HealthData;
}

export const HealthMetrics: React.FC<HealthMetricsProps> = ({ healthData }) => {
  const t = useT();
  const isHealthy = healthData.status === 'healthy';
  const isDatabaseConnected = healthData.database === 'connected';
  const errorCount = healthData.errors_last_24h ?? 0;
  const activeWatchers = healthData.active_watchers ?? 0;
  const failedWatchers = Object.values(healthData.watchers ?? {}).filter(w => w.status === 'failed').length;

  const statCard = (label: string, content: React.ReactNode) => (
    <div className={styles.statCard} style={t.card}>
      <div style={t.labelStyle}>{label}</div>
      <div className={styles.statValue}>{content}</div>
    </div>
  );

  const statusDot = (ok: boolean) => (
    <span className={styles.statusDot} style={{
      background: ok ? t.green : t.red,
      boxShadow: ok ? `0 0 6px ${t.green}80` : `0 0 6px ${t.red}80`,
    }} />
  );

  return (
    <div className={styles.container} style={t.card}>
      <h2 className={styles.heading} style={{ color: t.text }}>System Health</h2>

      <div className={styles.statsRow}>
        {statCard('Status',
          <div className={styles.statusRow}>
            {statusDot(isHealthy)}
            <span className={styles.statusText} style={{ color: isHealthy ? t.green : t.red }}>
              {healthData.status}
            </span>
          </div>
        )}

        {statCard('Database',
          <div className={styles.statusRow}>
            {statusDot(isDatabaseConnected)}
            <span className={styles.statusText} style={{ color: isDatabaseConnected ? t.green : t.red }}>
              {isDatabaseConnected ? 'connected' : 'disconnected'}
            </span>
          </div>
        )}

        {statCard('Active Watchers',
          <span className={styles.bigNumber} style={{ color: t.accent }}>{activeWatchers}</span>
        )}

        {statCard('Failed Watchers',
          <span className={styles.bigNumber} style={{ color: failedWatchers > 0 ? t.red : t.textMuted }}>{failedWatchers}</span>
        )}

        {statCard('Errors (24h)',
          <span className={styles.bigNumber} style={{ color: errorCount > 0 ? t.orange : t.textMuted }}>
            {errorCount}
          </span>
        )}
      </div>
    </div>
  );
};
