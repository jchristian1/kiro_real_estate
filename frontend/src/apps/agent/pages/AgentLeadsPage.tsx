/**
 * Agent Leads Inbox — prioritized work inbox with rich lead cards.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { useAgentLeads } from '../hooks/useAgentQueries';
import type { Lead } from '../hooks/useAgentQueries';

const BUCKETS = ['', 'HOT', 'WARM', 'NURTURE'];
const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'score_desc', label: 'Highest score' },
  { value: 'aging', label: 'Aging first' },
];

function bucketConfig(bucket: string | undefined) {
  if (bucket === 'HOT') return { label: 'HOT', color: '#f87171', bg: 'rgba(239,68,68,0.12)', dot: '#ef4444' };
  if (bucket === 'WARM') return { label: 'WARM', color: '#fb923c', bg: 'rgba(251,146,60,0.12)', dot: '#f97316' };
  if (bucket === 'NURTURE') return { label: 'NURTURE', color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', dot: '#64748b' };
  return null;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function getInitials(name: string): string {
  const parts = name.trim().split(' ');
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function avatarGradient(name: string): string {
  const gradients = [
    'linear-gradient(135deg, #6366f1, #8b5cf6)',
    'linear-gradient(135deg, #0ea5e9, #6366f1)',
    'linear-gradient(135deg, #10b981, #0ea5e9)',
    'linear-gradient(135deg, #f59e0b, #ef4444)',
    'linear-gradient(135deg, #8b5cf6, #ec4899)',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return gradients[Math.abs(hash) % gradients.length];
}

function sortLeads(leads: Lead[], sort: string): Lead[] {
  const arr = [...leads];
  if (sort === 'oldest') return arr.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  if (sort === 'score_desc') return arr.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  if (sort === 'aging') return arr.sort((a, b) => (b.is_aging ? 1 : 0) - (a.is_aging ? 1 : 0));
  return arr.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

// ── Lead Card ────────────────────────────────────────────────────────────────

const LeadCard: React.FC<{ lead: Lead; onClick: () => void }> = ({ lead, onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const bc = bucketConfig(lead.score_bucket);
  const [hovered, setHovered] = useState(false);

  const stageName = lead.current_state?.replace(/_/g, ' ') || 'New';
  const phone = lead.phone;
  const source = lead.lead_source_name || lead.source;

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '14px 18px', borderRadius: 14, cursor: 'pointer',
        background: hovered ? t.bgCardHover : t.bgCard,
        border: `1px solid ${lead.is_aging ? 'rgba(239,68,68,0.35)' : t.border}`,
        marginBottom: 6, transition: 'all 0.15s',
        boxShadow: lead.is_aging ? '0 0 0 1px rgba(239,68,68,0.15)' : 'none',
      }}
    >
      {/* Aging indicator strip */}
      {lead.is_aging && (
        <div style={{
          position: 'absolute', left: 0, top: '20%', bottom: '20%',
          width: 3, borderRadius: '0 2px 2px 0', background: '#ef4444',
        }} />
      )}

      {/* Avatar */}
      <div style={{
        width: 42, height: 42, borderRadius: '50%', flexShrink: 0,
        background: avatarGradient(lead.name || '?'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14, color: '#fff', fontWeight: 700, letterSpacing: '-0.3px',
        boxShadow: bc ? `0 0 0 2px ${bc.dot}40` : 'none',
      }}>
        {getInitials(lead.name || '?')}
      </div>

      {/* Main info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 3 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {lead.name}
          </span>
          {lead.is_aging && (
            <span style={{ fontSize: 10, color: '#f87171', fontWeight: 700, flexShrink: 0, letterSpacing: '0.3px' }}>
              ⚠ AGING
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: t.textMuted, flexWrap: 'wrap' }}>
          {phone && <span style={{ fontFamily: 'monospace', letterSpacing: '0.3px' }}>{phone}</span>}
          {phone && source && <span style={{ color: t.textFaint }}>·</span>}
          {source && <span>{source}</span>}
        </div>
      </div>

      {/* Right side: badges + meta */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 5, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {bc && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 6,
              color: bc.color, background: bc.bg, letterSpacing: '0.4px',
            }}>
              {bc.label}
            </span>
          )}
          {lead.score != null && (
            <span style={{
              fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 6,
              color: t.textMuted, background: t.bgBadge,
            }}>
              {lead.score}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            fontSize: 10, padding: '2px 7px', borderRadius: 5,
            color: t.textFaint, background: t.bgBadge, whiteSpace: 'nowrap',
          }}>
            {stageName}
          </span>
        </div>
        <span style={{ fontSize: 11, color: t.textFaint }}>{timeAgo(lead.created_at)}</span>
      </div>

      {/* Quick actions */}
      <div
        style={{ display: 'flex', gap: 6, flexShrink: 0, marginLeft: 4 }}
        onClick={e => e.stopPropagation()}
      >
        {phone && (
          <a
            href={`tel:${phone}`}
            title="Call"
            style={{
              width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: t.bgBadge, border: `1px solid ${t.border}`, color: t.green,
              fontSize: 14, textDecoration: 'none', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLAnchorElement).style.background = t.greenBg; }}
            onMouseLeave={e => { (e.currentTarget as HTMLAnchorElement).style.background = t.bgBadge; }}
          >
            📞
          </a>
        )}
        {lead.email && (
          <a
            href={`mailto:${lead.email}`}
            title="Email"
            style={{
              width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: t.bgBadge, border: `1px solid ${t.border}`, color: t.accent,
              fontSize: 14, textDecoration: 'none', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLAnchorElement).style.background = t.accentBg; }}
            onMouseLeave={e => { (e.currentTarget as HTMLAnchorElement).style.background = t.bgBadge; }}
          >
            ✉
          </a>
        )}
        <div
          title="Text Message — Coming soon"
          style={{
            width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: t.bgBadge, border: `1px solid ${t.border}`, color: t.textFaint,
            fontSize: 14, cursor: 'not-allowed', opacity: 0.5,
          }}
        >
          💬
        </div>
      </div>
    </div>
  );
};

// ── Page ─────────────────────────────────────────────────────────────────────

export const AgentLeadsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [bucket, setBucket] = useState(searchParams.get('bucket') || '');
  const [sort, setSort] = useState('newest');
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => { setPage(1); }, [debouncedSearch, bucket]);

  const params: Record<string, unknown> = { page };
  if (debouncedSearch) params.search = debouncedSearch;
  if (bucket) params.bucket = bucket;

  const { data, isLoading } = useAgentLeads(params);
  const rawLeads = data?.leads || [];
  const leads = sortLeads(rawLeads, sort);
  const totalPages = data?.pages || 1;

  const hotCount = rawLeads.filter(l => l.score_bucket === 'HOT').length;
  const agingCount = rawLeads.filter(l => l.is_aging).length;

  const inputStyle: React.CSSProperties = {
    padding: '9px 14px', background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 10, fontSize: 13, color: t.text, outline: 'none',
    transition: 'border-color 0.15s', width: '100%',
  };

  const bucketBtn = (b: string) => {
    const active = bucket === b;
    const bc = bucketConfig(b);
    return {
      padding: '7px 14px', borderRadius: 9, fontSize: 12, fontWeight: 500 as const,
      cursor: 'pointer' as const, transition: 'all 0.15s',
      background: active ? (bc?.bg || t.accentBg) : 'transparent',
      border: `1px solid ${active ? (bc?.dot || t.accent) : t.border}`,
      color: active ? (bc?.color || t.accent) : t.textMuted,
    };
  };

  return (
    <div style={{ maxWidth: 900 }}>
      {/* Summary strip */}
      {data && (data.total > 0) && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
          {[
            { label: 'Total', value: data.total, color: t.text, bg: t.bgCard },
            { label: 'HOT', value: hotCount, color: '#f87171', bg: 'rgba(239,68,68,0.08)' },
            { label: 'Aging', value: agingCount, color: '#fbbf24', bg: 'rgba(251,191,36,0.08)' },
          ].map(stat => (
            <div key={stat.label} style={{
              padding: '10px 18px', borderRadius: 12, background: stat.bg,
              border: `1px solid ${t.border}`, display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{ fontSize: 20, fontWeight: 700, color: stat.color }}>{stat.value}</span>
              <span style={{ fontSize: 12, color: t.textMuted }}>{stat.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: t.textFaint, fontSize: 14, pointerEvents: 'none' }}>
            🔍
          </span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, phone, email…"
            style={{ ...inputStyle, paddingLeft: 36 }}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)}
            onBlur={e => (e.target.style.borderColor = t.border)}
          />
        </div>

        <select
          value={sort}
          onChange={e => setSort(e.target.value)}
          style={{ ...inputStyle, width: 'auto', cursor: 'pointer', paddingRight: 28 }}
        >
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* Bucket filters */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 18, flexWrap: 'wrap' }}>
        {BUCKETS.map(b => (
          <button key={b} onClick={() => setBucket(b)} style={bucketBtn(b)}>
            {b || 'All Leads'}
          </button>
        ))}
      </div>

      {/* Results count */}
      {data && (
        <div style={{ fontSize: 12, color: t.textFaint, marginBottom: 12, letterSpacing: '0.2px' }}>
          {data.total} lead{data.total !== 1 ? 's' : ''}
          {bucket && ` · ${bucket}`}
          {debouncedSearch && ` · "${debouncedSearch}"`}
        </div>
      )}

      {/* Lead cards */}
      <div style={{ position: 'relative' }}>
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: t.textMuted, fontSize: 14 }}>
            <div style={{ fontSize: 24, marginBottom: 10 }}>⟳</div>
            Loading leads…
          </div>
        ) : leads.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '60px 0', color: t.textMuted, fontSize: 14,
            background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14,
          }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>◎</div>
            <div style={{ fontWeight: 600, color: t.text, marginBottom: 6 }}>No leads found</div>
            <div style={{ fontSize: 12 }}>Try adjusting your filters or search query</div>
          </div>
        ) : (
          leads.map(lead => (
            <LeadCard key={lead.id} lead={lead} onClick={() => navigate(`/agent/leads/${lead.id}`)} />
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 24 }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '8px 16px', borderRadius: 9, fontSize: 13, cursor: page === 1 ? 'not-allowed' : 'pointer',
              background: t.bgCard, border: `1px solid ${t.border}`,
              color: page === 1 ? t.textFaint : t.text, transition: 'all 0.15s',
            }}
          >← Prev</button>
          <span style={{ padding: '8px 14px', fontSize: 13, color: t.textMuted }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{
              padding: '8px 16px', borderRadius: 9, fontSize: 13, cursor: page === totalPages ? 'not-allowed' : 'pointer',
              background: t.bgCard, border: `1px solid ${t.border}`,
              color: page === totalPages ? t.textFaint : t.text, transition: 'all 0.15s',
            }}
          >Next →</button>
        </div>
      )}
    </div>
  );
};
