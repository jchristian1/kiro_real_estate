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
    /* Overview strip: 4-col desktop → 2×2 mobile */
    .dash-overview {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }
    @media (max-width: 767px) {
      .dash-overview { grid-template-columns: repeat(2, 1fr); gap: 7px; }
    }

    /* Queue section panels */
    .dash-queue-panel {
      border-radius: 14px;
      overflow: hidden;
      margin-bottom: 10px;
    }
    .dash-queue-header {
      padding: 12px 14px 11px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .dash-queue-action {
      background: none;
      border: none;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      padding: 6px 0 6px 12px; /* larger tap target */
      min-height: 36px;
      display: flex;
      align-items: center;
    }

    /* Queue items: comfortable touch targets */
    .dash-queue-item {
      display: flex;
      align-items: center;
      gap: 11px;
      padding: 12px 14px;
      cursor: pointer;
      transition: background 0.12s;
      -webkit-tap-highlight-color: transparent;
    }
    @media (max-width: 480px) {
      .dash-queue-item { padding: 11px 12px; gap: 10px; }
      .dash-queue-header { padding: 11px 12px 10px; }
    }

    /* Watcher card: stays horizontal but text wraps on tiny screens */
    .dash-watcher {
      display: flex;
      align-items: center;
      gap: 14px;
      border-radius: 14px;
      padding: 14px 16px;
      margin-bottom: 10px;
    }
    @media (max-width: 380px) {
      .dash-watcher { gap: 10px; padding: 12px 12px; }
    }

    /* Greeting */
    .dash-greeting-name { font-size: 22px; }
    @media (max-width: 480px) {
      .dash-greeting-name { font-size: 19px; }
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

// ── Queue item — richer work queue card ──────────────────────────────────────

type QueueLead = {
  id: number;
  name: string;
  score?: number;
  score_bucket?: string;
  source?: string;
  lead_source_name?: string;
  created_at?: string;
  is_aging?: boolean;
  minutes_since_created?: number;
  current_state?: string;
  address?: string;
  property_address?: string;
};

function bucketCfg(b?: string) {
  if (b === 'HOT')     return { label: 'HOT 🔥', color: '#f87171', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)'  };
  if (b === 'WARM')    return { label: 'WARM',   color: '#fb923c', bg: 'rgba(251,146,60,0.12)', border: 'rgba(251,146,60,0.3)' };
  if (b === 'NURTURE') return { label: 'NURTURE',color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', border: 'rgba(148,163,184,0.25)' };
  return null;
}

function stateHint(state?: string): string {
  if (!state) return 'New lead';
  const map: Record<string, string> = {
    NEW: 'Reach out now',
    INVITE_SENT: 'Follow up on form invite',
    FORM_SUBMITTED: 'Review form submission',
    SCORED: 'Contact scored lead',
    CONTACTED: 'Schedule appointment',
    APPOINTMENT_SET: 'Confirm appointment',
    LOST: 'Re-engage or archive',
    CLOSED: 'Closed',
  };
  return map[state] ?? state.replace(/_/g, ' ');
}

const QueueItem: React.FC<{
  lead: QueueLead;
  urgencyBadge?: React.ReactNode;
  onClick: () => void;
}> = ({ lead, urgencyBadge, onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hov, setHov] = useState(false);
  const bc = bucketCfg(lead.score_bucket);
  const src = lead.lead_source_name || lead.source;
  const hint = stateHint(lead.current_state);
  const age = lead.created_at ? timeAgo(lead.created_at) : lead.minutes_since_created != null ? `${Math.round(lead.minutes_since_created)}m` : null;

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className="dash-queue-item"
      style={{
        background: hov ? t.bgCardHover : 'transparent',
        borderBottom: `1px solid ${t.border}`,
      }}
    >
      {/* Avatar */}
      <div style={{
        width: 36, height: 36, borderRadius: 10, flexShrink: 0,
        background: avatarGrad(lead.name || '?'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, color: '#fff', fontWeight: 700,
        boxShadow: bc ? `0 0 0 2px ${bc.color}30` : 'none',
      }}>
        {initials(lead.name || '?')}
      </div>

      {/* Main info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Row 1: name + urgency */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
            {lead.name}
          </span>
          {urgencyBadge}
        </div>
        {/* Row 2: hint + source — truncated on mobile */}
        <div style={{ fontSize: 11, color: t.textMuted, display: 'flex', gap: 5, alignItems: 'center', overflow: 'hidden' }}>
          <span style={{ color: t.accent, fontWeight: 600, whiteSpace: 'nowrap', flexShrink: 0 }}>{hint}</span>
          {src && (
            <span style={{ color: t.textFaint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              · {src}
            </span>
          )}
        </div>
      </div>

      {/* Right: badges + age */}
      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          {bc && (
            <span style={{
              fontSize: 9, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
              background: bc.bg, color: bc.color, border: `1px solid ${bc.border}`,
              letterSpacing: '0.04em', whiteSpace: 'nowrap',
            }}>{bc.label}</span>
          )}
          {lead.score != null && (
            <span style={{ fontSize: 10, fontWeight: 700, color: t.textMuted }}>{lead.score}pt</span>
          )}
        </div>
        {age && <span style={{ fontSize: 10, color: t.textFaint, whiteSpace: 'nowrap' }}>{age}</span>}
      </div>

      {/* Open arrow */}
      <span style={{ fontSize: 14, color: t.textFaint, flexShrink: 0 }}>›</span>
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
    <div className="dash-watcher" style={{
      background: tierCfg.bg,
      border: `1px solid ${tierCfg.border}`,
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
      <div style={{ marginBottom: 18 }}>
        <div className="dash-greeting-name" style={{ fontWeight: 800, color: t.text, letterSpacing: '-0.3px', lineHeight: 1.2 }}>
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
      <WatcherCard />

      {/* ── Needs attention now — always first if any aging ── */}
      {hasAttention && (
        <div style={{
          marginBottom: 10, borderRadius: 14, overflow: 'hidden',
          border: '1px solid rgba(251,146,60,0.35)',
          background: 'rgba(251,146,60,0.04)',
        }}>
          <div className="dash-queue-header" style={{ borderBottom: '1px solid rgba(251,146,60,0.2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#fb923c', boxShadow: '0 0 6px #fb923c' }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>Needs Attention Now</span>
              <span style={{
                fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 5,
                background: 'rgba(251,146,60,0.15)', color: '#fb923c',
                border: '1px solid rgba(251,146,60,0.3)',
              }}>{attentionLeads.length}</span>
            </div>
            <button className="dash-queue-action" onClick={() => navigate('/agent/leads')} style={{ color: t.accent }}>
              View all →
            </button>
          </div>
          {attentionLeads.map(lead => (
            <QueueItem
              key={lead.id}
              lead={lead}
              onClick={() => navigate(`/agent/leads/${lead.id}`)}
              urgencyBadge={
                <span style={{
                  fontSize: 9, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
                  background: 'rgba(251,146,60,0.15)', color: '#fb923c',
                  border: '1px solid rgba(251,146,60,0.3)', letterSpacing: '0.04em',
                }}>
                  {lead.minutes_since_created != null ? `${Math.round(lead.minutes_since_created)}m` : '⏱ STALLED'}
                </span>
              }
            />
          ))}
        </div>
      )}

      {/* ── HOT leads queue ── */}
      <div style={{ marginBottom: 10, borderRadius: 14, overflow: 'hidden', border: `1px solid ${hotLeads.length > 0 ? 'rgba(239,68,68,0.25)' : t.border}`, background: t.bgCard }}>
        <div className="dash-queue-header" style={{ borderBottom: `1px solid ${t.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14 }}>🔥</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>HOT Leads</span>
            {hotCount > 0 && (
              <span style={{
                fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 5,
                background: 'rgba(239,68,68,0.12)', color: '#f87171',
                border: '1px solid rgba(239,68,68,0.28)',
              }}>{hotCount}</span>
            )}
          </div>
          <button className="dash-queue-action" onClick={() => navigate('/agent/leads?bucket=HOT')} style={{ color: t.accent }}>
            View all →
          </button>
        </div>
        {hotLeads.length === 0 ? (
          <div style={{ padding: '22px 14px', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
            <div style={{ fontSize: 20, marginBottom: 5 }}>🎯</div>
            No HOT leads right now — check back soon
          </div>
        ) : (
          <>
            {hotLeads.slice(0, 5).map(lead => (
              <QueueItem
                key={lead.id}
                lead={lead}
                onClick={() => navigate(`/agent/leads/${lead.id}`)}
                urgencyBadge={
                  lead.is_aging ? (
                    <span style={{ fontSize: 9, fontWeight: 800, padding: '2px 6px', borderRadius: 4, background: 'rgba(251,146,60,0.15)', color: '#fb923c', border: '1px solid rgba(251,146,60,0.3)' }}>⏱</span>
                  ) : undefined
                }
              />
            ))}
            {hotLeads.length > 5 && (
              <div style={{ padding: '9px 14px', borderTop: `1px solid ${t.border}` }}>
                <button className="dash-queue-action" onClick={() => navigate('/agent/leads?bucket=HOT')} style={{ color: t.accent, padding: 0, minHeight: 'auto' }}>
                  +{hotLeads.length - 5} more HOT leads →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Stalled / aging queue ── */}
      <div style={{ marginBottom: 10, borderRadius: 14, overflow: 'hidden', border: `1px solid ${agingLeads.length > 0 ? 'rgba(251,146,60,0.22)' : t.border}`, background: t.bgCard }}>
        <div className="dash-queue-header" style={{ borderBottom: `1px solid ${t.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14 }}>⏱</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>Stalled Leads</span>
            {agingCount > 0 && (
              <span style={{
                fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 5,
                background: 'rgba(251,146,60,0.12)', color: '#fb923c',
                border: '1px solid rgba(251,146,60,0.28)',
              }}>{agingCount}</span>
            )}
          </div>
          <button className="dash-queue-action" onClick={() => refetch()} style={{ color: t.textFaint }}>
            ↻ Refresh
          </button>
        </div>
        {agingLeads.length === 0 ? (
          <div style={{ padding: '22px 14px', textAlign: 'center' }}>
            <div style={{ fontSize: 20, marginBottom: 5 }}>✓</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: t.green }}>All caught up</div>
            <div style={{ fontSize: 12, color: t.textFaint, marginTop: 3 }}>No stalled leads — great response time</div>
          </div>
        ) : (
          agingLeads.slice(0, 5).map(lead => (
            <QueueItem
              key={lead.id}
              lead={lead}
              onClick={() => navigate(`/agent/leads/${lead.id}`)}
              urgencyBadge={
                <span style={{
                  fontSize: 9, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
                  background: 'rgba(251,146,60,0.15)', color: '#fb923c',
                  border: '1px solid rgba(251,146,60,0.3)', letterSpacing: '0.04em',
                }}>
                  {lead.minutes_since_created != null ? `${Math.round(lead.minutes_since_created)}m old` : 'stalled'}
                </span>
              }
            />
          ))
        )}
      </div>

      {/* ── Recent leads ── */}
      <div style={{ borderRadius: 14, overflow: 'hidden', border: `1px solid ${t.border}`, background: t.bgCard }}>
        <div className="dash-queue-header" style={{ borderBottom: `1px solid ${t.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14 }}>🕐</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>Recent Leads</span>
          </div>
          <button className="dash-queue-action" onClick={() => navigate('/agent/leads')} style={{ color: t.accent }}>
            All leads →
          </button>
        </div>
        {hotLeads.length === 0 && agingLeads.length === 0 ? (
          <div style={{ padding: '22px 14px', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
            <div style={{ fontSize: 20, marginBottom: 5 }}>◎</div>
            No leads yet — they'll appear here as they come in
          </div>
        ) : (
          <>
            {[...hotLeads, ...agingLeads]
              .filter((lead, idx, arr) => arr.findIndex(l => l.id === lead.id) === idx)
              .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
              .slice(0, 6)
              .map(lead => (
                <QueueItem
                  key={lead.id}
                  lead={lead}
                  onClick={() => navigate(`/agent/leads/${lead.id}`)}
                  urgencyBadge={
                    lead.is_aging ? (
                      <span style={{ fontSize: 9, color: '#fb923c', fontWeight: 800 }}>⏱</span>
                    ) : undefined
                  }
                />
              ))}
            <div style={{ padding: '9px 14px', borderTop: `1px solid ${t.border}` }}>
              <button className="dash-queue-action" onClick={() => navigate('/agent/leads')} style={{ color: t.accent, padding: 0, minHeight: 'auto' }}>
                View all leads →
              </button>
            </div>
          </>
        )}
      </div>

    </div>
  );
};
