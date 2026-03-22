/**
 * Agent Dashboard — daily command cockpit.
 * Structure: greeting → overview strip → watcher health → attention queue → HOT leads → aging → recent
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import {
  useAgentDashboard, useAgentGmail, useToggleWatcher, useAgentMe,
} from '../hooks/useAgentQueries';
import { BackendPendingBadge } from '../components/BackendPendingBadge';

// ── CSS ───────────────────────────────────────────────────────────────────────

if (typeof document !== 'undefined' && !document.getElementById('dash-css')) {
  const s = document.createElement('style');
  s.id = 'dash-css';
  s.textContent = `
    .dash-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .dash-overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
    @media (max-width: 767px) {
      .dash-grid    { grid-template-columns: 1fr; }
      .dash-overview { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 400px) {
      .dash-overview { grid-template-columns: 1fr 1fr; }
    }
  `;
  document.head.appendChild(s);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function greeting(name?: string): string {
  const h = new Date().getHours();
  const g = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  return name ? `${g}, ${name.split(' ')[0]}` : g;
}

function initials(name: string): string {
  const p = name.trim().split(' ');
  return p.length >= 2 ? (p[0][0] + p[p.length - 1][0]).toUpperCase() : name.slice(0, 2).toUpperCase();
}

function avatarGrad(name: string): string {
  const g = [
    'linear-gradient(135deg,#6366f1,#8b5cf6)',
    'linear-gradient(135deg,#0ea5e9,#6366f1)',
    'linear-gradient(135deg,#10b981,#0ea5e9)',
    'linear-gradient(135deg,#f59e0b,#ef4444)',
    'linear-gradient(135deg,#8b5cf6,#ec4899)',
  ];
  let h = 0;
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return g[Math.abs(h) % g.length];
}

// ── Sub-components ────────────────────────────────────────────────────────────

const Card: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '14px 16px', ...style }}>
      {children}
    </div>
  );
};

const SectionHead: React.FC<{
  icon: string; title: string; count?: number;
  countColor?: string; action?: { label: string; onClick: () => void };
}> = ({ icon, title, count, countColor, action }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ fontSize: 15 }}>{icon}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>{title}</span>
        {count != null && (
          <span style={{
            fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 5,
            background: countColor ? `${countColor}18` : t.bgBadge,
            color: countColor ?? t.textFaint,
            border: `1px solid ${countColor ? countColor + '35' : t.border}`,
          }}>{count}</span>
        )}
      </div>
      {action && (
        <button onClick={action.onClick} style={{
          background: 'none', border: 'none', fontSize: 11, color: t.accent,
          cursor: 'pointer', fontWeight: 600, padding: 0,
        }}>{action.label} →</button>
      )}
    </div>
  );
};

// Compact lead row used in multiple sections
const LeadRow: React.FC<{
  lead: { id: number; name: string; score?: number; source?: string; lead_source_name?: string; created_at?: string; is_aging?: boolean; minutes_since_created?: number };
  badge?: React.ReactNode;
  onClick: () => void;
}> = ({ lead, badge, onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hov, setHov] = useState(false);
  const src = lead.lead_source_name || lead.source;

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '9px 10px', borderRadius: 10, cursor: 'pointer',
        background: hov ? t.bgCardHover : 'transparent',
        transition: 'background 0.12s',
        borderBottom: `1px solid ${t.border}`,
      }}
    >
      <div style={{
        width: 32, height: 32, borderRadius: 9, flexShrink: 0,
        background: avatarGrad(lead.name || '?'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, color: '#fff', fontWeight: 700,
      }}>
        {initials(lead.name || '?')}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {lead.name}
        </div>
        <div style={{ fontSize: 11, color: t.textFaint, marginTop: 1 }}>
          {src && <span>{src}</span>}
          {src && lead.created_at && <span style={{ margin: '0 4px' }}>·</span>}
          {lead.created_at && <span>{timeAgo(lead.created_at)}</span>}
          {lead.minutes_since_created != null && !lead.created_at && (
            <span>{Math.round(lead.minutes_since_created)}m old</span>
          )}
        </div>
      </div>
      <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
        {badge}
        {lead.score != null && (
          <span style={{ fontSize: 11, fontWeight: 700, color: t.textMuted }}>{lead.score}pt</span>
        )}
      </div>
    </div>
  );
};

// ── Watcher health card ───────────────────────────────────────────────────────

// Inject pulse animation once
if (typeof document !== 'undefined' && !document.getElementById('watcher-css')) {
  const s = document.createElement('style');
  s.id = 'watcher-css';
  s.textContent = `
    @keyframes watcher-pulse {
      0%,100% { opacity: 1; transform: scale(1); }
      50%      { opacity: 0.55; transform: scale(1.35); }
    }
    .watcher-live { animation: watcher-pulse 2s ease-in-out infinite; }
  `;
  document.head.appendChild(s);
}

const WatcherCard: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: gmail } = useAgentGmail();
  const toggleWatcher = useToggleWatcher();

  const watcherOn = gmail?.watcher_enabled ?? false;
  const adminLocked = gmail?.watcher_admin_override ?? false;
  const connected = gmail?.connected ?? false;

  const handleToggle = async () => {
    if (adminLocked || !connected) return;
    try { await toggleWatcher.mutateAsync(!watcherOn); } catch { /* ignore */ }
  };

  // Derive status tier
  const tier: 'active' | 'paused' | 'offline' | 'unconfigured' =
    !connected ? 'unconfigured' : watcherOn ? 'active' : 'paused';

  const tierCfg = {
    active:       { label: 'Active',        sub: 'Monitoring inbox for new leads', color: t.green,    bg: `${t.green}10`,    border: `${t.green}30`,    dot: t.green,    pulse: true  },
    paused:       { label: 'Paused',         sub: 'Watcher is off — leads may be missed', color: '#f87171', bg: 'rgba(248,113,113,0.07)', border: 'rgba(248,113,113,0.25)', dot: '#f87171', pulse: false },
    offline:      { label: 'Offline',        sub: 'Connection lost', color: '#f87171', bg: 'rgba(248,113,113,0.07)', border: 'rgba(248,113,113,0.25)', dot: '#f87171', pulse: false },
    unconfigured: { label: 'Not configured', sub: 'Connect Gmail to enable lead monitoring', color: t.textFaint, bg: t.bgBadge, border: t.border, dot: t.textFaint, pulse: false },
  }[tier];

  // Mask email for display — show domain only to reduce visual noise
  const emailDisplay = gmail?.gmail_address
    ? gmail.gmail_address.replace(/^(.{2}).*@/, '$1…@')
    : null;

  const lastSync = gmail?.last_sync;

  return (
    <div style={{
      background: tierCfg.bg,
      border: `1px solid ${tierCfg.border}`,
      borderRadius: 14, padding: '14px 16px',
      display: 'flex', alignItems: 'center', gap: 14,
    }}>
      {/* Status icon + live dot */}
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 13,
          background: tier === 'active' ? `${t.green}15` : t.bgBadge,
          border: `1.5px solid ${tier === 'active' ? t.green + '35' : t.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 20,
        }}>
          {tier === 'active' ? '📡' : tier === 'unconfigured' ? '🔌' : '⏸'}
        </div>
        {/* Live pulse dot */}
        <div
          className={tierCfg.pulse ? 'watcher-live' : undefined}
          style={{
            position: 'absolute', bottom: -1, right: -1,
            width: 11, height: 11, borderRadius: '50%',
            background: tierCfg.dot,
            border: `2px solid ${t.bgCard}`,
            boxShadow: tier === 'active' ? `0 0 8px ${t.green}80` : 'none',
          }}
        />
      </div>

      {/* Text block */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>Inbox Watcher</span>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5,
            background: tier === 'active' ? `${t.green}18` : tier === 'unconfigured' ? t.bgBadge : 'rgba(248,113,113,0.12)',
            color: tierCfg.color,
            border: `1px solid ${tier === 'active' ? t.green + '30' : tier === 'unconfigured' ? t.border : 'rgba(248,113,113,0.25)'}`,
            letterSpacing: '0.04em',
          }}>{tierCfg.label}</span>
          {adminLocked && (
            <span style={{ fontSize: 9, color: t.orange, fontWeight: 700, letterSpacing: '0.05em' }}>ADMIN LOCKED</span>
          )}
        </div>
        <div style={{ fontSize: 11, color: t.textMuted, lineHeight: 1.4 }}>{tierCfg.sub}</div>
        <div style={{ display: 'flex', gap: 10, marginTop: 4, flexWrap: 'wrap' }}>
          {emailDisplay && (
            <span style={{ fontSize: 10, color: t.textFaint, fontFamily: 'monospace' }}>{emailDisplay}</span>
          )}
          {lastSync && tier === 'active' && (
            <span style={{ fontSize: 10, color: t.textFaint }}>last sync {timeAgo(lastSync)}</span>
          )}
        </div>
      </div>

      {/* Toggle — only when connected */}
      {connected ? (
        <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
          <button
            onClick={handleToggle}
            disabled={adminLocked || toggleWatcher.isPending}
            aria-label={watcherOn ? 'Pause watcher' : 'Enable watcher'}
            style={{
              width: 46, height: 26, borderRadius: 13, border: 'none',
              cursor: adminLocked ? 'not-allowed' : 'pointer',
              background: watcherOn ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : t.border,
              position: 'relative', transition: 'background 0.2s',
              opacity: adminLocked ? 0.5 : 1, flexShrink: 0,
            }}
          >
            <div style={{
              position: 'absolute', top: 3, left: watcherOn ? 22 : 3,
              width: 20, height: 20, borderRadius: '50%', background: '#fff',
              transition: 'left 0.2s', boxShadow: '0 1px 4px rgba(0,0,0,0.25)',
            }} />
          </button>
          <span style={{ fontSize: 9, color: t.textFaint, fontWeight: 600 }}>
            {watcherOn ? 'ON' : 'OFF'}
          </span>
        </div>
      ) : (
        <button
          onClick={() => {/* navigate to settings */}}
          style={{
            padding: '7px 13px', borderRadius: 9, fontSize: 11, fontWeight: 600,
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', color: '#fff',
            border: 'none', cursor: 'pointer', flexShrink: 0,
            boxShadow: '0 2px 8px rgba(99,102,241,0.3)',
          }}
        >
          Set up
        </button>
      )}
    </div>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────

export const AgentDashboardPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const { data, isLoading, refetch } = useAgentDashboard();
  const { data: me } = useAgentMe();
  const [now, setNow] = useState(new Date());

  // Tick clock for greeting freshness
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const hotLeads = data?.hot_leads || [];
  const agingLeads = data?.aging_leads || [];
  const hotCount = data?.hot_lead_count ?? hotLeads.length;
  const agingCount = data?.aging_lead_count ?? agingLeads.length;
  const responseTime = data?.response_time_today_minutes;

  // Attention queue = aging leads that need immediate action
  const attentionLeads = agingLeads.slice(0, 5);
  const hasAttention = attentionLeads.length > 0;

  const todayStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: t.textMuted, fontSize: 14 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>⟳</div>
          Loading dashboard…
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, paddingBottom: 40 }}>

      {/* ── Greeting header ── */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 22, fontWeight: 800, color: t.text, letterSpacing: '-0.3px', lineHeight: 1.2 }}>
          {greeting(me?.full_name)}
        </div>
        <div style={{ fontSize: 12, color: t.textFaint, marginTop: 3 }}>{todayStr}</div>
      </div>

      {/* ── Overview strip ── */}
      <div className="dash-overview" style={{ marginBottom: 12 }}>

        {/* HOT leads */}
        <div
          onClick={() => navigate('/agent/leads?bucket=HOT')}
          style={{
            borderRadius: 14, padding: '16px 16px 14px', cursor: 'pointer',
            background: hotCount > 0 ? 'rgba(239,68,68,0.08)' : t.bgCard,
            border: `1px solid ${hotCount > 0 ? 'rgba(239,68,68,0.28)' : t.border}`,
            transition: 'all 0.15s', position: 'relative', overflow: 'hidden',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = hotCount > 0 ? 'rgba(239,68,68,0.13)' : t.bgCardHover)}
          onMouseLeave={e => (e.currentTarget.style.background = hotCount > 0 ? 'rgba(239,68,68,0.08)' : t.bgCard)}
        >
          {hotCount > 0 && (
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 3,
              background: 'linear-gradient(90deg,#ef4444,#f87171)',
            }} />
          )}
          <div style={{ fontSize: 10, fontWeight: 700, color: hotCount > 0 ? '#f87171' : t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
            🔥 HOT Leads
          </div>
          <div style={{ fontSize: 34, fontWeight: 800, color: hotCount > 0 ? '#f87171' : t.textMuted, lineHeight: 1, letterSpacing: '-1px' }}>
            {hotCount}
          </div>
          <div style={{ fontSize: 11, color: hotCount > 0 ? 'rgba(248,113,113,0.7)' : t.textFaint, marginTop: 5 }}>
            {hotCount === 0 ? 'none right now' : hotCount === 1 ? 'needs your attention' : 'need your attention'}
          </div>
        </div>

        {/* Aging */}
        <div
          onClick={() => navigate('/agent/leads')}
          style={{
            borderRadius: 14, padding: '16px 16px 14px', cursor: 'pointer',
            background: agingCount > 0 ? 'rgba(251,146,60,0.08)' : t.bgCard,
            border: `1px solid ${agingCount > 0 ? 'rgba(251,146,60,0.28)' : t.border}`,
            transition: 'all 0.15s', position: 'relative', overflow: 'hidden',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = agingCount > 0 ? 'rgba(251,146,60,0.13)' : t.bgCardHover)}
          onMouseLeave={e => (e.currentTarget.style.background = agingCount > 0 ? 'rgba(251,146,60,0.08)' : t.bgCard)}
        >
          {agingCount > 0 && (
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 3,
              background: 'linear-gradient(90deg,#f97316,#fb923c)',
            }} />
          )}
          <div style={{ fontSize: 10, fontWeight: 700, color: agingCount > 0 ? '#fb923c' : t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
            ⏱ Stalled
          </div>
          <div style={{ fontSize: 34, fontWeight: 800, color: agingCount > 0 ? '#fb923c' : t.textMuted, lineHeight: 1, letterSpacing: '-1px' }}>
            {agingCount}
          </div>
          <div style={{ fontSize: 11, color: agingCount > 0 ? 'rgba(251,146,60,0.7)' : t.textFaint, marginTop: 5 }}>
            {agingCount === 0 ? 'all caught up ✓' : agingCount === 1 ? 'lead stalled' : 'leads stalled'}
          </div>
        </div>

        {/* Response time */}
        <div style={{
          borderRadius: 14, padding: '16px 16px 14px', position: 'relative', overflow: 'hidden',
          background: t.bgCard, border: `1px solid ${t.border}`,
        }}>
          {responseTime != null && (
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 3,
              background: responseTime <= 15
                ? `linear-gradient(90deg,${t.green},${t.green}88)`
                : 'linear-gradient(90deg,#f97316,#fb923c)',
            }} />
          )}
          <div style={{ fontSize: 10, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
            ⚡ Avg Response
          </div>
          <div style={{
            fontSize: 34, fontWeight: 800, lineHeight: 1, letterSpacing: '-1px',
            color: responseTime == null ? t.textMuted : responseTime <= 15 ? t.green : '#fb923c',
          }}>
            {responseTime != null ? `${responseTime}m` : '—'}
          </div>
          <div style={{ fontSize: 11, marginTop: 5, color: t.textFaint }}>
            {responseTime == null ? 'no data today' : responseTime <= 15 ? 'on target ✓' : 'above 15m target'}
          </div>
        </div>

        {/* Conversions — backend pending */}
        <div style={{
          borderRadius: 14, padding: '16px 16px 14px',
          background: t.bgCard, border: `1px dashed ${t.border}`,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px' }}>
              📊 Conversions
            </div>
            <BackendPendingBadge tooltip="Conversion rate tracking — coming soon" />
          </div>
          <div style={{ fontSize: 34, fontWeight: 800, color: t.textFaint, lineHeight: 1, letterSpacing: '-1px' }}>—</div>
          <div style={{ fontSize: 11, color: t.textFaint, marginTop: 5 }}>this month</div>
        </div>
      </div>

      {/* ── Watcher + system health ── */}
      <div style={{ marginBottom: 12 }}>
        <WatcherCard />
      </div>

      {/* ── Needs attention now ── */}
      {hasAttention && (
        <Card style={{ marginBottom: 12, borderColor: 'rgba(251,146,60,0.35)', background: 'rgba(251,146,60,0.04)', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px 0' }}>
            <SectionHead
              icon="⚠"
              title="Needs Attention Now"
              count={attentionLeads.length}
              countColor="#fb923c"
              action={{ label: 'View all aging', onClick: () => navigate('/agent/leads') }}
            />
          </div>
          <div>
            {attentionLeads.map((lead, i) => (
              <div key={lead.id} style={{ borderTop: i === 0 ? `1px solid rgba(251,146,60,0.2)` : `1px solid ${t.border}` }}>
                <LeadRow
                  lead={lead}
                  onClick={() => navigate(`/agent/leads/${lead.id}`)}
                  badge={
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5,
                      background: 'rgba(251,146,60,0.15)', color: '#fb923c',
                      border: '1px solid rgba(251,146,60,0.3)',
                    }}>⏱ AGING</span>
                  }
                />
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── HOT leads + Aging grid ── */}
      <div className="dash-grid" style={{ marginBottom: 12 }}>

        {/* HOT leads */}
        <Card style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px 0' }}>
            <SectionHead
              icon="🔥"
              title="HOT Leads"
              count={hotCount}
              countColor="#f87171"
              action={{ label: 'View all', onClick: () => navigate('/agent/leads?bucket=HOT') }}
            />
          </div>
          {hotLeads.length === 0 ? (
            <div style={{ padding: '20px 16px', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
              <div style={{ fontSize: 22, marginBottom: 6 }}>🎯</div>
              No HOT leads right now
            </div>
          ) : (
            <div>
              {hotLeads.slice(0, 6).map((lead, i) => (
                <div key={lead.id} style={{ borderTop: i === 0 ? `1px solid ${t.border}` : `1px solid ${t.border}` }}>
                  <LeadRow
                    lead={lead}
                    onClick={() => navigate(`/agent/leads/${lead.id}`)}
                    badge={
                      <span style={{
                        fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 5,
                        background: 'rgba(239,68,68,0.12)', color: '#f87171',
                        border: '1px solid rgba(239,68,68,0.3)',
                      }}>HOT 🔥</span>
                    }
                  />
                </div>
              ))}
              {hotLeads.length > 6 && (
                <div style={{ padding: '8px 16px', borderTop: `1px solid ${t.border}` }}>
                  <button onClick={() => navigate('/agent/leads?bucket=HOT')} style={{
                    background: 'none', border: 'none', fontSize: 12, color: t.accent,
                    cursor: 'pointer', fontWeight: 600, padding: 0,
                  }}>+{hotLeads.length - 6} more HOT leads →</button>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Aging / stalled */}
        <Card style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px 0' }}>
            <SectionHead
              icon="⏱"
              title="Stalled Leads"
              count={agingCount}
              countColor={agingCount > 0 ? '#fb923c' : t.green}
              action={{ label: 'Refresh', onClick: () => refetch() }}
            />
          </div>
          {agingLeads.length === 0 ? (
            <div style={{ padding: '20px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: 22, marginBottom: 6 }}>✓</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: t.green }}>All caught up</div>
              <div style={{ fontSize: 12, color: t.textFaint, marginTop: 3 }}>No stalled leads — great response time</div>
            </div>
          ) : (
            <div>
              {agingLeads.slice(0, 6).map((lead, i) => (
                <div key={lead.id} style={{ borderTop: i === 0 ? `1px solid ${t.border}` : `1px solid ${t.border}` }}>
                  <LeadRow
                    lead={lead}
                    onClick={() => navigate(`/agent/leads/${lead.id}`)}
                    badge={
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5,
                        background: 'rgba(251,146,60,0.12)', color: '#fb923c',
                        border: '1px solid rgba(251,146,60,0.3)',
                      }}>
                        {lead.minutes_since_created != null ? `${Math.round(lead.minutes_since_created)}m` : 'stalled'}
                      </span>
                    }
                  />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Recent leads ── */}
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px 0' }}>
          <SectionHead
            icon="🕐"
            title="Recent Leads"
            action={{ label: 'All leads', onClick: () => navigate('/agent/leads') }}
          />
        </div>
        {hotLeads.length === 0 && agingLeads.length === 0 ? (
          <div style={{ padding: '20px 16px', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
            <div style={{ fontSize: 22, marginBottom: 6 }}>◎</div>
            No leads yet — they'll appear here as they come in
          </div>
        ) : (
          <div>
            {[...hotLeads, ...agingLeads]
              .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
              .slice(0, 5)
              .map((lead, i) => (
                <div key={lead.id} style={{ borderTop: i === 0 ? `1px solid ${t.border}` : `1px solid ${t.border}` }}>
                  <LeadRow
                    lead={lead}
                    onClick={() => navigate(`/agent/leads/${lead.id}`)}
                    badge={
                      lead.is_aging ? (
                        <span style={{ fontSize: 10, color: '#fb923c', fontWeight: 700 }}>⏱</span>
                      ) : undefined
                    }
                  />
                </div>
              ))}
            <div style={{ padding: '10px 16px', borderTop: `1px solid ${t.border}` }}>
              <button onClick={() => navigate('/agent/leads')} style={{
                background: 'none', border: 'none', fontSize: 12, color: t.accent,
                cursor: 'pointer', fontWeight: 600, padding: 0,
              }}>View all leads →</button>
            </div>
          </div>
        )}
      </Card>

    </div>
  );
};
