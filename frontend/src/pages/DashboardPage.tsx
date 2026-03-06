/**
 * Dashboard Page — Apple-inspired dark theme
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export interface HealthData {
  status: string;
  timestamp: string;
  database: { connected: boolean; message: string };
  watchers: { active_count: number; heartbeats: Record<string, unknown> };
  errors: { count_24h: number; recent_errors: unknown[] };
}

export interface WatcherStatus {
  agent_id: string;
  status: string;
  last_heartbeat: string | null;
  last_sync: string | null;
  error: string | null;
}

const card: React.CSSProperties = {
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.07)',
  borderRadius: 16,
  padding: '20px 24px',
};

const label: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.35)',
  textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 6,
};

const statusDot = (ok: boolean) => ({
  display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
  background: ok ? '#34d399' : '#f87171',
  marginRight: 6, flexShrink: 0,
} as React.CSSProperties);

export const DashboardPage: React.FC = () => {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [watchers, setWatchers] = useState<WatcherStatus[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    try {
      const [h, w] = await Promise.all([
        axios.get<HealthData>(`${API_BASE_URL}/health`),
        axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`),
      ]);
      setHealth(h.data);
      setWatchers(w.data.watchers);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'rgba(255,255,255,0.3)', fontSize: 14 }}>
        Loading…
      </div>
    );
  }

  const isHealthy = health?.status === 'healthy';
  const dbOk = health?.database?.connected ?? false;
  const activeWatchers = health?.watchers?.active_count ?? 0;
  const errors24h = health?.errors?.count_24h ?? 0;

  return (
    <div style={{ maxWidth: 900 }}>
      {/* Status bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 28 }}>
        <span style={statusDot(isHealthy)} />
        <span style={{ fontSize: 13, color: isHealthy ? '#34d399' : '#f87171', fontWeight: 600 }}>
          {isHealthy ? 'All systems operational' : 'System degraded'}
        </span>
        {health?.timestamp && (
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', marginLeft: 8 }}>
            Updated {new Date(health.timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Database', value: dbOk ? 'Connected' : 'Disconnected', ok: dbOk },
          { label: 'Active Watchers', value: String(activeWatchers), ok: activeWatchers > 0 },
          { label: 'Errors (24h)', value: String(errors24h), ok: errors24h === 0 },
        ].map(s => (
          <div key={s.label} style={card}>
            <div style={label}>{s.label}</div>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={statusDot(s.ok)} />
              <span style={{ fontSize: 20, fontWeight: 700, color: '#f0f0f5', letterSpacing: '-0.5px' }}>{s.value}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Watchers table */}
      <div style={card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#f0f0f5' }}>Watchers</div>
          <button
            onClick={fetchAll}
            style={{
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, padding: '5px 12px', fontSize: 12, color: 'rgba(255,255,255,0.6)',
              cursor: 'pointer',
            }}
          >
            Refresh
          </button>
        </div>

        {watchers.length === 0 ? (
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.3)', padding: '12px 0' }}>No watchers configured.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Agent', 'Status', 'Last Sync', 'Error'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 0', color: 'rgba(255,255,255,0.3)', fontWeight: 500, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {watchers.map(w => (
                <tr key={w.agent_id}>
                  <td style={{ padding: '10px 0', color: '#f0f0f5', fontWeight: 500 }}>{w.agent_id}</td>
                  <td style={{ padding: '10px 0' }}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                      background: w.status === 'running' ? 'rgba(52,211,153,0.12)' : 'rgba(248,113,113,0.12)',
                      color: w.status === 'running' ? '#34d399' : '#f87171',
                    }}>
                      <span style={statusDot(w.status === 'running')} />
                      {w.status}
                    </span>
                  </td>
                  <td style={{ padding: '10px 0', color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>
                    {w.last_sync ? new Date(w.last_sync).toLocaleString() : '—'}
                  </td>
                  <td style={{ padding: '10px 0', color: '#f87171', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {w.error || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
