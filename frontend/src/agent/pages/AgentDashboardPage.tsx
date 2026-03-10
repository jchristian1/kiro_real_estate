/**
 * Agent Dashboard — HOT leads, aging alerts, response time stats, watcher status.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { getTokens } from '../../utils/theme';
import { useAgentDashboard, useToggleWatcher, useAgentGmail } from '../hooks/useAgentQueries';
import type { Lead } from '../hooks/useAgentQueries';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const StatCard: React.FC<{ label: string; value: string | number; sub?: string; color?: string }> = ({ label, value, sub, color }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '20px 22px', flex: 1, minWidth: 140 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || t.text, letterSpacing: '-0.5px' }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: t.textMuted, marginTop: 4 }}>{sub}</div>}
    </div>
  );
};

const LeadRow: React.FC<{ lead: Lead; onClick: () => void }> = ({ lead, onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isAging = lead.is_aging;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '12px 16px', borderRadius: 12, cursor: 'pointer',
        background: isAging ? t.redBg : t.bgCard,
        border: `1px solid ${isAging ? t.red + '40' : t.border}`,
        marginBottom: 8, transition: 'all 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = isAging ? t.redBg : t.bgCardHover)}
      onMouseLeave={e => (e.currentTarget.style.background = isAging ? t.redBg : t.bgCard)}
    >
      <div style={{
        width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14, color: '#fff', fontWeight: 700,
      }}>
        {lead.name?.[0]?.toUpperCase() || '?'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {lead.name}
          {isAging && <span style={{ marginLeft: 8, fontSize: 11, color: t.red, fontWeight: 700 }}>⚠ AGING</span>}
        </div>
        <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
          {lead.lead_source_name || 'Unknown source'} · {timeAgo(lead.created_at)}
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: t.red }}>HOT</div>
        {lead.score != null && <div style={{ fontSize: 11, color: t.textMuted }}>{lead.score} pts</div>}
      </div>
    </div>
  );
};

export const AgentDashboardPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const { data, isLoading, refetch } = useAgentDashboard();
  const { data: gmail } = useAgentGmail();
  const toggleWatcher = useToggleWatcher();

  const handleWatcherToggle = async () => {
    if (!gmail) return;
    if (gmail.watcher_admin_override) return;
    try {
      await toggleWatcher.mutateAsync(!gmail.watcher_enabled);
    } catch { /* handled */ }
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: t.textMuted, fontSize: 14 }}>
        Loading dashboard…
      </div>
    );
  }

  const hotLeads = data?.hot_leads || [];
  const agingLeads = data?.aging_leads || [];
  const watcherOn = gmail?.watcher_enabled ?? false;
  const adminLocked = gmail?.watcher_admin_override ?? false;

  return (
    <div>
      {/* Stats row */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 24, flexWrap: 'wrap' }}>
        <StatCard label="HOT Leads" value={hotLeads.length} color={t.red} />
        <StatCard label="Aging Alerts" value={agingLeads.length} color={agingLeads.length > 0 ? t.orange : t.green} />
        <StatCard
          label="Avg Response Today"
          value={data?.response_time_today_minutes != null ? `${data.response_time_today_minutes}m` : '—'}
          sub="target: < 15 min"
        />
        <StatCard
          label="Avg Response (7d)"
          value={data?.response_time_week_minutes != null ? `${data.response_time_week_minutes}m` : '—'}
        />
      </div>

      {/* Watcher status */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 18px', background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 14, marginBottom: 24,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: watcherOn ? t.green : t.textFaint,
            boxShadow: watcherOn ? `0 0 8px ${t.green}` : 'none',
          }} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>
              Gmail Watcher — {watcherOn ? 'Active' : 'Inactive'}
            </div>
            {adminLocked && <div style={{ fontSize: 11, color: t.orange, marginTop: 2 }}>Admin locked</div>}
            {gmail?.gmail_address && <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>{gmail.gmail_address}</div>}
          </div>
        </div>
        <button
          onClick={handleWatcherToggle}
          disabled={adminLocked || toggleWatcher.isPending}
          title={adminLocked ? 'Locked by admin' : undefined}
          style={{
            width: 44, height: 26, borderRadius: 13, border: 'none',
            cursor: adminLocked ? 'not-allowed' : 'pointer',
            background: watcherOn ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.border,
            position: 'relative', transition: 'background 0.2s', opacity: adminLocked ? 0.5 : 1,
          }}
        >
          <div style={{
            position: 'absolute', top: 3, left: watcherOn ? 21 : 3,
            width: 20, height: 20, borderRadius: '50%', background: '#fff',
            transition: 'left 0.2s', boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
          }} />
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* HOT Leads */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>HOT Leads</div>
            <button onClick={() => navigate('/agent/leads?bucket=HOT')} style={{
              background: 'none', border: 'none', fontSize: 12, color: t.accent, cursor: 'pointer', fontWeight: 500,
            }}>View all →</button>
          </div>
          {hotLeads.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: t.textMuted, fontSize: 13, background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 12 }}>
              No HOT leads right now
            </div>
          ) : (
            hotLeads.slice(0, 5).map(lead => (
              <LeadRow key={lead.id} lead={lead} onClick={() => navigate(`/agent/leads/${lead.id}`)} />
            ))
          )}
        </div>

        {/* Aging Alerts */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>
              Aging Alerts
              {agingLeads.length > 0 && (
                <span style={{ marginLeft: 8, fontSize: 11, background: t.redBg, color: t.red, padding: '2px 8px', borderRadius: 10, fontWeight: 600 }}>
                  {agingLeads.length}
                </span>
              )}
            </div>
            <button onClick={() => refetch()} style={{
              background: 'none', border: 'none', fontSize: 12, color: t.textMuted, cursor: 'pointer',
            }}>↻ Refresh</button>
          </div>
          {agingLeads.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: t.green, fontSize: 13, background: t.greenBg, border: `1px solid ${t.green}30`, borderRadius: 12 }}>
              ✓ No aging leads — great response time!
            </div>
          ) : (
            agingLeads.slice(0, 5).map(lead => (
              <LeadRow key={lead.id} lead={lead} onClick={() => navigate(`/agent/leads/${lead.id}`)} />
            ))
          )}
        </div>
      </div>
    </div>
  );
};
