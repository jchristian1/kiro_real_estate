/**
 * Health Metrics Component
 * Requirements: 8.5, 16.1
 */
import React from 'react';
import { HealthData } from '../pages/DashboardPage';
import { useT } from '../../../shared/hooks/useT';

interface HealthMetricsProps {
  healthData: HealthData;
}

export const HealthMetrics: React.FC<HealthMetricsProps> = ({ healthData }) => {
  const t = useT();
  const isHealthy = healthData.status === 'healthy';
  const isDatabaseConnected = healthData.database?.connected === true;
  const errorCount = healthData.errors?.count_24h ?? 0;
  const activeWatchers = healthData.watchers?.active_count ?? 0;

  const statCard = (label: string, content: React.ReactNode) => (
    <div style={{ ...t.card, padding: '14px 18px', flex: 1, minWidth: 120 }}>
      <div style={t.labelStyle}>{label}</div>
      <div style={{ marginTop: 6 }}>{content}</div>
    </div>
  );

  const statusDot = (ok: boolean) => (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: ok ? t.green : t.red, marginRight: 7, flexShrink: 0,
      boxShadow: ok ? `0 0 6px ${t.green}80` : `0 0 6px ${t.red}80`,
    }} />
  );

  return (
    <div style={{ ...t.card, padding: '20px 24px' }}>
      <h2 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: t.text }}>System Health</h2>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {/* Overall Status */}
        {statCard('Status',
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {statusDot(isHealthy)}
            <span style={{ fontSize: 14, fontWeight: 600, color: isHealthy ? t.green : t.red }}>
              {healthData.status}
            </span>
          </div>
        )}

        {/* Database */}
        {statCard('Database',
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {statusDot(isDatabaseConnected)}
            <span style={{ fontSize: 14, fontWeight: 600, color: isDatabaseConnected ? t.green : t.red }}>
              {isDatabaseConnected ? 'connected' : 'disconnected'}
            </span>
          </div>
        )}

        {/* Active Watchers */}
        {statCard('Active Watchers',
          <span style={{ fontSize: 22, fontWeight: 700, color: t.accent }}>{activeWatchers}</span>
        )}

        {/* Failed Watchers */}
        {statCard('Failed Watchers',
          <span style={{ fontSize: 22, fontWeight: 700, color: t.textMuted }}>0</span>
        )}

        {/* Errors 24h */}
        {statCard('Errors (24h)',
          <span style={{ fontSize: 22, fontWeight: 700, color: errorCount > 0 ? t.orange : t.textMuted }}>
            {errorCount}
          </span>
        )}
      </div>

      <div style={{ marginTop: 14, fontSize: 11, color: t.textFaint }}>
        Last updated: {new Date(healthData.timestamp).toLocaleString()}
      </div>
    </div>
  );
};
