/**
 * Dashboard Page — theme-aware, Apple-inspired
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTheme } from '../contexts/ThemeContext';
import { getTokens } from '../utils/theme';

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

export const DashboardPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
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

  const card: React.CSSProperties = {
    background: t.bgCard,
    border: `1px solid ${t.border}`,
    borderRadius: 16,
    padding: '20px 24px',
    transition: 'background 0.2s',
  };

  const dot = (ok: boolean): React.CSSProperties => ({
    display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
    background: ok ? t.green : t.red,
    marginRight: 7, flexShrink: 0,
    boxShadow: ok ? `0 0 6px ${t.green}80` : `0 0 6px ${t.red}80`,
  });

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: t.textFaint, fontSize: 14 }}>
        Loading…
      </div>
    );
  }

  const isHealthy = health?.status === 'healthy';
  const dbOk = health?.database?.connected ?? false;
  const activeWatchers = health?.watchers?.active_count ?? 0;
  const errors24h = health?.errors?.count_24h ?? 0;

  return (
    <div style={{ maxWidth: 960 }}>
      {/* Status bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 28 }}>
        <span style={dot(isHealthy)} />
        <span style={{ fontSize: 13, color: isHealthy ? t.green : t.red, fontWeight: 600 }}>
          {isHealthy ? 'All systems operational' : 'System degraded'}
        </span>
        {health?.timestamp && (
          <span style={{ fontSize: 12, color: t.textFaint, marginLeft: 8 }}>
            · Updated {new Date(health.timestamp).toLocaleTimeString()}
          </span>
        )}
        <button
          onClick={fetchAll}
          style={{
            marginLeft: 'auto',
            background: t.bgCard, border: `1px solid ${t.border}`,
            borderRadius: 8, padding: '5px 14px', fontSize: 12,
            color: t.textMuted, cursor: 'pointer', transition: 'all 0.15s',
          }}
        >
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Database', value: dbOk ? 'Connected' : 'Disconnected', ok: dbOk },
          { label: 'Active Watchers', value: String(activeWatchers), ok: activeWatchers > 0 },
          { label: 'Errors (24h)', value: String(errors24h), ok: errors24h === 0 },
        ].map(s => (
          <div key={s.label} style={card}>
            <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 10 }}>
              {s.label}
            </div>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={dot(s.ok)} />
              <span style={{ fontSize: 22, fontWeight: 700, color: t.text, letterSpacing: '-0.5px' }}>{s.value}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Watchers table */}
      <div style={card}>
        <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 16 }}>Watchers</div>

        {watchers.length === 0 ? (
          <div style={{ fontSize: 13, color: t.textFaint, padding: '12px 0' }}>No watchers configured.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Agent', 'Status', 'Last Sync', 'Error'].map(h => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '0 0 10px',
                    color: t.textFaint, fontWeight: 500,
                    fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px',
                    borderBottom: `1px solid ${t.border}`,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {watchers.map((w, i) => (
                <tr key={w.agent_id} style={{ borderBottom: i < watchers.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                  <td style={{ padding: '11px 0', color: t.text, fontWeight: 500 }}>{w.agent_id}</td>
                  <td style={{ padding: '11px 0' }}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                      background: w.status === 'running' ? t.greenBg : t.redBg,
                      color: w.status === 'running' ? t.green : t.red,
                    }}>
                      <span style={dot(w.status === 'running')} />
                      {w.status}
                    </span>
                  </td>
                  <td style={{ padding: '11px 0', color: t.textMuted, fontSize: 12 }}>
                    {w.last_sync ? new Date(w.last_sync).toLocaleString() : '—'}
                  </td>
                  <td style={{ padding: '11px 0', color: t.red, fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
