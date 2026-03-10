/**
 * Agent Reports — source distribution, bucket distribution, avg response time, period selector.
 */

import React, { useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { getTokens } from '../../utils/theme';
import { useAgentReports } from '../hooks/useAgentQueries';

const PERIODS = [
  { value: '7d',  label: '7 days'  },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
];

export const AgentReportsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [period, setPeriod] = useState('30d');
  const { data, isLoading } = useAgentReports(period);

  const cardStyle = {
    background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '22px',
  };

  const total = data
    ? (data.bucket_distribution.HOT + data.bucket_distribution.WARM + data.bucket_distribution.NURTURE)
    : 0;

  const bucketBar = (label: string, count: number, color: string) => {
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return (
      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color }}>{label}</span>
          <span style={{ fontSize: 13, color: t.textMuted }}>{count} ({pct}%)</span>
        </div>
        <div style={{ height: 8, background: t.border, borderRadius: 4, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
        </div>
      </div>
    );
  };

  return (
    <div>
      {/* Period selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {PERIODS.map(p => (
          <button key={p.value} onClick={() => setPeriod(p.value)} style={{
            padding: '8px 18px', borderRadius: 10, fontSize: 13, fontWeight: 500, cursor: 'pointer',
            background: period === p.value ? t.accentBg : t.bgCard,
            border: `1.5px solid ${period === p.value ? t.accent : t.border}`,
            color: period === p.value ? t.accent : t.textMuted, transition: 'all 0.15s',
          }}>{p.label}</button>
        ))}
        {data && (
          <span style={{ fontSize: 12, color: t.textFaint, alignSelf: 'center', marginLeft: 8 }}>
            {new Date(data.period_start).toLocaleDateString()} – {new Date(data.period_end).toLocaleDateString()}
          </span>
        )}
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: t.textMuted, fontSize: 14 }}>Loading reports…</div>
      ) : !data ? null : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
          {/* Summary stats */}
          <div style={{ ...cardStyle, gridColumn: '1 / -1', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {[
              { label: 'Total Leads', value: total, color: t.text },
              { label: 'Appointments Set', value: data.appointments_set, color: t.green },
              { label: 'Avg Response Time', value: data.avg_response_time_minutes != null ? `${data.avg_response_time_minutes}m` : '—', color: t.text },
              { label: 'HOT Leads', value: data.bucket_distribution.HOT, color: t.red },
            ].map(stat => (
              <div key={stat.label} style={{ flex: 1, minWidth: 120 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
                  {stat.label}
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: stat.color, letterSpacing: '-0.5px' }}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>

          {/* Bucket distribution */}
          <div style={cardStyle}>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 20 }}>Lead Buckets</div>
            {bucketBar('HOT', data.bucket_distribution.HOT, t.red)}
            {bucketBar('WARM', data.bucket_distribution.WARM, t.orange)}
            {bucketBar('NURTURE', data.bucket_distribution.NURTURE, t.textMuted)}
          </div>

          {/* Source distribution */}
          <div style={cardStyle}>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 20 }}>Leads by Source</div>
            {data.leads_by_source.length === 0 ? (
              <div style={{ fontSize: 13, color: t.textMuted }}>No data for this period.</div>
            ) : (
              data.leads_by_source.map(src => {
                const pct = total > 0 ? Math.round((src.count / total) * 100) : 0;
                return (
                  <div key={src.source} style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 13, color: t.text }}>{src.source}</span>
                      <span style={{ fontSize: 13, color: t.textMuted }}>{src.count} ({pct}%)</span>
                    </div>
                    <div style={{ height: 8, background: t.border, borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', width: `${pct}%`,
                        background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                        borderRadius: 4, transition: 'width 0.4s ease',
                      }} />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
