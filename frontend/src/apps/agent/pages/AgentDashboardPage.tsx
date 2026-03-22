/**
 * Agent Dashboard — compact premium operational cockpit.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import {
  useAgentDashboard, useAgentGmail, useToggleWatcher, useAgentMe,
} from '../hooks/useAgentQueries';
import { BackendPendingBadge } from '../components/BackendPendingBadge';

// ── Inject styles once ────────────────────────────────────────────────────────
if (typeof document !== 'undefined' && !document.getElementById('dash-css')) {
  const s = document.createElement('style');
  s.id = 'dash-css';
  s.textContent = `
    .dash-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; }
    @media(max-width:680px){ .dash-grid{ grid-template-columns:repeat(2,1fr); gap:5px; } }

    .dash-row {
      display:flex; align-items:center; gap:9px;
      padding:8px 12px; cursor:pointer;
      transition:background 0.1s;
      -webkit-tap-highlight-color:transparent;
    }
    .dash-row:last-child { border-bottom:none !important; }
    @media(max-width:480px){ .dash-row{ padding:8px 10px; gap:8px; } }

    .dash-sec-hdr {
      display:flex; align-items:center; justify-content:space-between;
      padding:8px 12px 7px;
      border-bottom:1px solid var(--dash-border);
    }
    .dash-sec-btn {
      background:none; border:none; cursor:pointer;
      font-size:11px; font-weight:600;
      padding:3px 0 3px 8px; min-height:28px;
      display:flex; align-items:center;
    }

    @keyframes dpulse {
      0%,100%{ opacity:1; transform:scale(1); }
      50%{ opacity:0.5; transform:scale(1.4); }
    }
    .dpulse { animation:dpulse 2s ease-in-out infinite; }
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

function stateHint(state?: string): string {
  if (!state) return 'New lead';
  const map: Record<string, string> = {
    NEW: 'Reach out now', INVITE_SENT: 'Follow up on invite',
    FORM_SUBMITTED: 'Review submission', SCORED: 'Contact scored lead',
    CONTACTED: 'Schedule appointment', APPOINTMENT_SET: 'Confirm appointment',
    LOST: 'Re-engage or archive', CLOSED: 'Closed',
  };
  return map[state] ?? state.replace(/_/g, ' ');
}

type QueueLead = {
  id: number; name: string; score?: number; score_bucket?: string;
  source?: string; lead_source_name?: string; created_at?: string;
  is_aging?: boolean; minutes_since_created?: number; current_state?: string;
};

function bucketColor(b?: string) {
  if (b === 'HOT')     return { c: '#f87171', bg: 'rgba(239,68,68,0.12)',  bd: 'rgba(239,68,68,0.3)'  };
  if (b === 'WARM')    return { c: '#fb923c', bg: 'rgba(251,146,60,0.12)', bd: 'rgba(251,146,60,0.3)' };
  if (b === 'NURTURE') return { c: '#94a3b8', bg: 'rgba(148,163,184,0.1)', bd: 'rgba(148,163,184,0.25)' };
  return null;
}

// ── LeadRow — compact queue row ───────────────────────────────────────────────
const LeadRow: React.FC<{
  lead: QueueLead;
  badge?: React.ReactNode;
  borderColor: string;
  onClick: () => void;
}> = ({ lead, badge, borderColor, onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hov, setHov] = useState(false);
  const bc = bucketColor(lead.score_bucket);
  const src = lead.lead_source_name || lead.source;
  const hint = stateHint(lead.current_state);
  const age = lead.created_at
    ? timeAgo(lead.created_at)
    : lead.minutes_since_created != null
      ? `${Math.round(lead.minutes_since_created)}m`
      : null;

  return (
    <div
      className="dash-row"
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? t.bgCardHover : 'transparent',
        borderBottom: `1px solid ${borderColor}`,
      }}
    >
      {/* Avatar */}
      <div style={{
        width: 28, height: 28, borderRadius: 7, flexShrink: 0,
        background: avatarGrad(lead.name || '?'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700, color: '#fff',
        boxShadow: bc ? `0 0 0 1.5px ${bc.c}40` : 'none',
      }}>
        {initials(lead.name || '?')}
      </div>

      {/* Name + hint */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 1 }}>
          <span style={{
            fontSize: 12, fontWeight: 700, color: t.text,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{lead.name}</span>
          {badge}
        </div>
        <div style={{ fontSize: 10, display: 'flex', gap: 4, alignItems: 'center', overflow: 'hidden' }}>
          <span style={{ color: t.accent, fontWeight: 600, whiteSpace: 'nowrap', flexShrink: 0 }}>{hint}</span>
          {src && (
            <span style={{ color: t.textFaint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              · {src}
            </span>
          )}
        </div>
      </div>

      {/* Trailing: bucket + score + age */}
      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {bc && (
            <span style={{
              fontSize: 8, fontWeight: 800, padding: '1px 5px', borderRadius: 3,
              background: bc.bg, color: bc.c, border: `1px solid ${bc.bd}`,
              letterSpacing: '0.04em', whiteSpace: 'nowrap',
            }}>{lead.score_bucket}</span>
          )}
          {lead.score != null && (
            <span style={{ fontSize: 9, fontWeight: 700, color: t.textMuted }}>{lead.score}pt</span>
          )}
        </div>
        {age && <span style={{ fontSize: 9, color: t.textFaint, whiteSpace: 'nowrap' }}>{age}</span>}
      </div>

      <span style={{ fontSize: 12, color: t.textFaint, flexShrink: 0, marginLeft: 2 }}>›</span>
    </div>
  );
};

// ── MetricCard ────────────────────────────────────────────────────────────────
const MetricCard: React.FC<{
  label: string; value: React.ReactNode; sub: string;
  accentColor?: string; accentBar?: string; onClick?: () => void;
  pending?: boolean;
}> = ({ label, value, sub, accentColor, accentBar, onClick, pending }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hov, setHov] = useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        borderRadius: 10, padding: '10px 12px 9px',
        background: accentColor ? `${accentColor}0d` : t.bgCard,
        border: `1px solid ${accentColor ? accentColor + '35' : t.border}`,
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative', overflow: 'hidden',
        transition: 'background 0.12s',
        ...(hov && onClick ? { background: accentColor ? `${accentColor}18` : t.bgCardHover } : {}),
      }}
    >
      {accentBar && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: accentBar,
        }} />
      )}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{
          fontSize: 9, fontWeight: 700, color: accentColor ?? t.textFaint,
          textTransform: 'uppercase', letterSpacing: '0.7px',
        }}>{label}</span>
        {pending && <BackendPendingBadge tooltip="Coming soon" />}
      </div>
      <div style={{
        fontSize: 26, fontWeight: 800, lineHeight: 1, letterSpacing: '-0.5px',
        color: accentColor ?? t.textMuted,
      }}>{value}</div>
      <div style={{ fontSize: 10, color: accentColor ? `${accentColor}99` : t.textFaint, marginTop: 3 }}>{sub}</div>
    </div>
  );
};

// ── QueueSection — reusable section wrapper ───────────────────────────────────
const QueueSection: React.FC<{
  icon: string; title: string; count?: number; countColor?: string; countBg?: string; countBd?: string;
  actionLabel: string; onAction: () => void; actionColor: string;
  borderColor: string; bg?: string; headerBorder?: string;
  emptyNode?: React.ReactNode;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ icon, title, count, countColor, countBg, countBd, actionLabel, onAction, actionColor,
        borderColor, bg, headerBorder, emptyNode, children, style }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{
      borderRadius: 10, overflow: 'hidden',
      border: `1px solid ${borderColor}`,
      background: bg ?? t.bgCard,
      marginBottom: 7,
      ...style,
    }}>
      <div className="dash-sec-hdr" style={{
        '--dash-border': headerBorder ?? t.border,
        borderBottom: `1px solid ${headerBorder ?? t.border}`,
      } as React.CSSProperties}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13 }}>{icon}</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: t.text }}>{title}</span>
          {count != null && count > 0 && (
            <span style={{
              fontSize: 9, fontWeight: 800, padding: '1px 6px', borderRadius: 4,
              background: countBg, color: countColor, border: `1px solid ${countBd}`,
            }}>{count}</span>
          )}
        </div>
        <button className="dash-sec-btn" onClick={onAction} style={{ color: actionColor }}>
          {actionLabel}
        </button>
      </div>
      {children ?? emptyNode}
    </div>
  );
};

// ── WatcherCard ───────────────────────────────────────────────────────────────
const WatcherCard: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: gmail } = useAgentGmail();
  const toggleWatcher = useToggleWatcher();

  const watcherOn   = gmail?.watcher_enabled ?? false;
  const adminLocked = gmail?.watcher_admin_override ?? false;
  const connected   = gmail?.connected ?? false;

  const handleToggle = async () => {
    if (adminLocked || !connected) return;
    try { await toggleWatcher.mutateAsync(!watcherOn); } catch { /* ignore */ }
  };

  const tier: 'active' | 'paused' | 'unconfigured' =
    !connected ? 'unconfigured' : watcherOn ? 'active' : 'paused';

  const cfg = {
    active:       { label: 'Active',          dot: t.green,    bg: `${t.green}0d`,           bd: `${t.green}28`,           lc: t.green    },
    paused:       { label: 'Paused',           dot: '#f87171',  bg: 'rgba(248,113,113,0.06)', bd: 'rgba(248,113,113,0.22)', lc: '#f87171'  },
    unconfigured: { label: 'Not configured',   dot: t.textFaint, bg: t.bgBadge,              bd: t.border,                 lc: t.textFaint },
  }[tier];

  const emailDisplay = gmail?.gmail_address
    ? gmail.gmail_address.replace(/^(.{2}).*@/, '$1…@')
    : null;
  const lastSync = gmail?.last_sync;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      borderRadius: 10, padding: '9px 12px',
      background: cfg.bg, border: `1px solid ${cfg.bd}`,
      marginBottom: 7,
    }}>
      {/* Icon + pulse dot */}
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 9,
          background: tier === 'active' ? `${t.green}15` : t.bgBadge,
          border: `1px solid ${tier === 'active' ? t.green + '30' : t.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
        }}>
          {tier === 'active' ? '📡' : tier === 'unconfigured' ? '🔌' : '⏸'}
        </div>
        <div
          className={tier === 'active' ? 'dpulse' : undefined}
          style={{
            position: 'absolute', bottom: -1, right: -1,
            width: 9, height: 9, borderRadius: '50%',
            background: cfg.dot, border: `1.5px solid ${t.bgCard}`,
            boxShadow: tier === 'active' ? `0 0 6px ${t.green}70` : 'none',
          }}
        />
      </div>

      {/* Text */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 1 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: t.text }}>Inbox Watcher</span>
          <span style={{
            fontSize: 8, fontWeight: 800, padding: '1px 5px', borderRadius: 3,
            background: tier === 'active' ? `${t.green}18` : 'rgba(148,163,184,0.12)',
            color: cfg.lc, border: `1px solid ${cfg.bd}`, letterSpacing: '0.05em',
          }}>{cfg.label}</span>
          {adminLocked && (
            <span style={{ fontSize: 8, color: t.orange, fontWeight: 700, letterSpacing: '0.05em' }}>LOCKED</span>
          )}
        </div>
        <div style={{ fontSize: 10, color: t.textFaint, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {emailDisplay
            ? <span style={{ fontFamily: 'monospace' }}>{emailDisplay}</span>
            : <span>{tier === 'unconfigured' ? 'Connect Gmail to monitor leads' : tier === 'paused' ? 'Watcher paused — leads may be missed' : 'Monitoring inbox'}</span>
          }
          {lastSync && tier === 'active' && (
            <span>· {timeAgo(lastSync)}</span>
          )}
        </div>
      </div>

      {/* Control */}
      {connected ? (
        <button
          onClick={handleToggle}
          disabled={adminLocked || toggleWatcher.isPending}
          aria-label={watcherOn ? 'Pause watcher' : 'Enable watcher'}
          style={{
            width: 38, height: 22, borderRadius: 11, border: 'none', flexShrink: 0,
            cursor: adminLocked ? 'not-allowed' : 'pointer',
            background: watcherOn ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : t.border,
            position: 'relative', transition: 'background 0.2s',
            opacity: adminLocked ? 0.5 : 1,
          }}
        >
          <div style={{
            position: 'absolute', top: 2, left: watcherOn ? 18 : 2,
            width: 18, height: 18, borderRadius: '50%', background: '#fff',
            transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          }} />
        </button>
      ) : (
        <button
          style={{
            padding: '5px 10px', borderRadius: 7, fontSize: 10, fontWeight: 600,
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', color: '#fff',
            border: 'none', cursor: 'pointer', flexShrink: 0,
            boxShadow: '0 2px 6px rgba(99,102,241,0.3)',
          }}
        >Set up</button>
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

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const hotLeads   = data?.hot_leads   || [];
  const agingLeads = data?.aging_leads || [];
  const hotCount   = data?.hot_lead_count   ?? hotLeads.length;
  const agingCount = data?.aging_lead_count ?? agingLeads.length;
  const responseTime = data?.response_time_today_minutes;

  const attentionLeads = agingLeads.slice(0, 5);
  const todayStr = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 160, color: t.textMuted, fontSize: 13 }}>
        Loading…
      </div>
    );
  }

  // Urgency badge helpers
  const stalledBadge = (lead: QueueLead) => (
    <span style={{
      fontSize: 8, fontWeight: 800, padding: '1px 5px', borderRadius: 3,
      background: 'rgba(251,146,60,0.15)', color: '#fb923c',
      border: '1px solid rgba(251,146,60,0.3)', letterSpacing: '0.04em',
    }}>
      {lead.minutes_since_created != null ? `${Math.round(lead.minutes_since_created)}m` : 'stalled'}
    </span>
  );

  const agingBadge = (
    <span style={{ fontSize: 9, color: '#fb923c', fontWeight: 800 }}>⏱</span>
  );

  // Deduped recent leads
  const recentLeads = [...hotLeads, ...agingLeads]
    .filter((l, i, arr) => arr.findIndex(x => x.id === l.id) === i)
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
    .slice(0, 6);

  return (
    <div style={{ maxWidth: 900, paddingBottom: 32 }}>

      {/* ── Greeting ── */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 800, color: t.text, letterSpacing: '-0.2px', lineHeight: 1.2 }}>
          {greeting(me?.full_name)}
        </div>
        <div style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>{todayStr}</div>
      </div>

      {/* ── Metric strip ── */}
      <div className="dash-grid" style={{ marginBottom: 7 }}>
        <MetricCard
          label="🔥 HOT Leads"
          value={hotCount}
          sub={hotCount === 0 ? 'none right now' : hotCount === 1 ? 'needs attention' : 'need attention'}
          accentColor={hotCount > 0 ? '#f87171' : undefined}
          accentBar={hotCount > 0 ? 'linear-gradient(90deg,#ef4444,#f87171)' : undefined}
          onClick={() => navigate('/agent/leads?bucket=HOT')}
        />
        <MetricCard
          label="⏱ Stalled"
          value={agingCount}
          sub={agingCount === 0 ? 'all caught up ✓' : agingCount === 1 ? 'lead stalled' : 'leads stalled'}
          accentColor={agingCount > 0 ? '#fb923c' : undefined}
          accentBar={agingCount > 0 ? 'linear-gradient(90deg,#f97316,#fb923c)' : undefined}
          onClick={() => navigate('/agent/leads')}
        />
        <MetricCard
          label="⚡ Avg Response"
          value={responseTime != null ? `${responseTime}m` : '—'}
          sub={responseTime == null ? 'no data today' : responseTime <= 15 ? 'on target ✓' : 'above 15m target'}
          accentColor={responseTime == null ? undefined : responseTime <= 15 ? t.green : '#fb923c'}
          accentBar={responseTime != null ? (responseTime <= 15 ? `linear-gradient(90deg,${t.green},${t.green}88)` : 'linear-gradient(90deg,#f97316,#fb923c)') : undefined}
        />
        <MetricCard
          label="📊 Conversions"
          value="—"
          sub="this month"
          pending
        />
      </div>

      {/* ── Watcher ── */}
      <WatcherCard />

      {/* ── Needs Attention ── */}
      {attentionLeads.length > 0 && (
        <QueueSection
          icon="●" title="Needs Attention"
          count={attentionLeads.length}
          countColor="#fb923c" countBg="rgba(251,146,60,0.15)" countBd="rgba(251,146,60,0.3)"
          actionLabel="View all →" onAction={() => navigate('/agent/leads')} actionColor={t.accent}
          borderColor="rgba(251,146,60,0.35)" bg="rgba(251,146,60,0.04)"
          headerBorder="rgba(251,146,60,0.2)"
        >
          {attentionLeads.map(lead => (
            <LeadRow key={lead.id} lead={lead} badge={stalledBadge(lead)}
              borderColor="rgba(251,146,60,0.12)"
              onClick={() => navigate(`/agent/leads/${lead.id}`)} />
          ))}
        </QueueSection>
      )}

      {/* ── HOT Leads ── */}
      <QueueSection
        icon="🔥" title="HOT Leads"
        count={hotCount} countColor="#f87171" countBg="rgba(239,68,68,0.12)" countBd="rgba(239,68,68,0.28)"
        actionLabel="View all →" onAction={() => navigate('/agent/leads?bucket=HOT')} actionColor={t.accent}
        borderColor={hotLeads.length > 0 ? 'rgba(239,68,68,0.22)' : t.border}
        emptyNode={
          <div style={{ padding: '9px 12px', fontSize: 11, color: t.textMuted }}>
            No HOT leads right now
          </div>
        }
      >
        {hotLeads.length > 0 ? (
          <>
            {hotLeads.slice(0, 5).map(lead => (
              <LeadRow key={lead.id} lead={lead}
                badge={lead.is_aging ? agingBadge : undefined}
                borderColor={t.border}
                onClick={() => navigate(`/agent/leads/${lead.id}`)} />
            ))}
            {hotLeads.length > 5 && (
              <div style={{ padding: '7px 12px', borderTop: `1px solid ${t.border}` }}>
                <button className="dash-sec-btn" onClick={() => navigate('/agent/leads?bucket=HOT')}
                  style={{ color: t.accent, padding: 0, minHeight: 'auto' }}>
                  +{hotLeads.length - 5} more →
                </button>
              </div>
            )}
          </>
        ) : undefined}
      </QueueSection>

      {/* ── Stalled Leads ── */}
      <QueueSection
        icon="⏱" title="Stalled Leads"
        count={agingCount} countColor="#fb923c" countBg="rgba(251,146,60,0.12)" countBd="rgba(251,146,60,0.28)"
        actionLabel="↻ Refresh" onAction={() => refetch()} actionColor={t.textFaint}
        borderColor={agingLeads.length > 0 ? 'rgba(251,146,60,0.2)' : t.border}
        emptyNode={
          <div style={{ padding: '9px 12px', fontSize: 11 }}>
            <span style={{ fontWeight: 600, color: t.green }}>✓ All caught up</span>
            <span style={{ color: t.textFaint, marginLeft: 5 }}>No stalled leads</span>
          </div>
        }
      >
        {agingLeads.length > 0 ? (
          agingLeads.slice(0, 5).map(lead => (
            <LeadRow key={lead.id} lead={lead} badge={stalledBadge(lead)}
              borderColor={t.border}
              onClick={() => navigate(`/agent/leads/${lead.id}`)} />
          ))
        ) : undefined}
      </QueueSection>

      {/* ── Recent Leads ── */}
      <QueueSection
        icon="🕐" title="Recent Leads"
        actionLabel="All leads →" onAction={() => navigate('/agent/leads')} actionColor={t.accent}
        borderColor={t.border}
        style={{ marginBottom: 0 }}
        emptyNode={
          <div style={{ padding: '9px 12px', fontSize: 11, color: t.textMuted }}>
            No leads yet — they'll appear here as they come in
          </div>
        }
      >
        {recentLeads.length > 0 ? (
          <>
            {recentLeads.map(lead => (
              <LeadRow key={lead.id} lead={lead}
                badge={lead.is_aging ? agingBadge : undefined}
                borderColor={t.border}
                onClick={() => navigate(`/agent/leads/${lead.id}`)} />
            ))}
            <div style={{ padding: '7px 12px', borderTop: `1px solid ${t.border}` }}>
              <button className="dash-sec-btn" onClick={() => navigate('/agent/leads')}
                style={{ color: t.accent, padding: 0, minHeight: 'auto' }}>
                View all leads →
              </button>
            </div>
          </>
        ) : undefined}
      </QueueSection>

    </div>
  );
};
