/**
 * Agent Leads Inbox — filter bar, search with debounce, lead cards, pagination.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { getTokens } from '../../utils/theme';
import { useAgentLeads } from '../hooks/useAgentQueries';
import type { Lead } from '../hooks/useAgentQueries';

const BUCKETS = ['', 'HOT', 'WARM', 'NURTURE'];
const STATUSES = ['', 'NEW', 'CONTACTED', 'APPOINTMENT_SET', 'LOST', 'CLOSED'];

function bucketColor(bucket: string | undefined, t: ReturnType<typeof getTokens>) {
  if (bucket === 'HOT') return { color: t.red, bg: t.redBg };
  if (bucket === 'WARM') return { color: t.orange, bg: t.orangeBg };
  return { color: t.textMuted, bg: t.bgBadge };
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const LeadCard: React.FC<{ lead: Lead; onClick: () => void }> = ({ lead, onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const bc = bucketColor(lead.score_bucket, t);

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '14px 18px', borderRadius: 14, cursor: 'pointer',
        background: t.bgCard, border: `1px solid ${lead.is_aging ? t.red + '40' : t.border}`,
        marginBottom: 8, transition: 'all 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = t.bgCardHover)}
      onMouseLeave={e => (e.currentTarget.style.background = t.bgCard)}
    >
      <div style={{
        width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 15, color: '#fff', fontWeight: 700,
      }}>
        {lead.name?.[0]?.toUpperCase() || '?'}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {lead.name}
          </span>
          {lead.is_aging && (
            <span style={{ fontSize: 10, color: t.red, fontWeight: 700, flexShrink: 0 }}>⚠ AGING</span>
          )}
        </div>
        <div style={{ fontSize: 12, color: t.textMuted }}>
          {lead.email}
          {lead.lead_source_name && <span> · {lead.lead_source_name}</span>}
          {lead.property_address && <span> · {lead.property_address}</span>}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
        {lead.score_bucket && (
          <span style={{
            fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 8,
            color: bc.color, background: bc.bg,
          }}>
            {lead.score_bucket}
          </span>
        )}
        {lead.current_state && (
          <span style={{ fontSize: 11, color: t.textFaint }}>{lead.current_state}</span>
        )}
        <span style={{ fontSize: 11, color: t.textFaint }}>{timeAgo(lead.created_at)}</span>
      </div>
    </div>
  );
};

export const AgentLeadsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [bucket, setBucket] = useState(searchParams.get('bucket') || '');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

  // 300ms debounce
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [debouncedSearch, bucket, status]);

  const params: Record<string, unknown> = { page };
  if (debouncedSearch) params.search = debouncedSearch;
  if (bucket) params.bucket = bucket;
  if (status) params.status = status;

  const { data, isLoading } = useAgentLeads(params);
  const leads = data?.leads || [];
  const totalPages = data?.pages || 1;

  const inputStyle = {
    padding: '9px 14px', background: t.bgInput, border: `1.5px solid ${t.border}`,
    borderRadius: 10, fontSize: 13, color: t.text, outline: 'none', transition: 'border-color 0.15s',
  };

  const filterBtn = (active: boolean) => ({
    padding: '7px 14px', borderRadius: 9, fontSize: 12, fontWeight: 500 as const, cursor: 'pointer' as const,
    background: active ? t.accentBg : 'transparent',
    border: `1px solid ${active ? t.accent : t.border}`,
    color: active ? t.accent : t.textMuted,
    transition: 'all 0.15s',
  });

  return (
    <div>
      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search leads…"
          style={{ ...inputStyle, minWidth: 200, flex: 1 }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)}
          onBlur={e => (e.target.style.borderColor = t.border)}
        />

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {BUCKETS.map(b => (
            <button key={b} onClick={() => setBucket(b)} style={filterBtn(bucket === b)}>
              {b || 'All Buckets'}
            </button>
          ))}
        </div>

        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          style={{ ...inputStyle, cursor: 'pointer' }}
        >
          {STATUSES.map(s => <option key={s} value={s}>{s || 'All Statuses'}</option>)}
        </select>
      </div>

      {/* Results count */}
      {data && (
        <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 14 }}>
          {data.total} lead{data.total !== 1 ? 's' : ''}
          {bucket && ` · ${bucket}`}
          {debouncedSearch && ` · "${debouncedSearch}"`}
        </div>
      )}

      {/* Lead cards */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: t.textMuted, fontSize: 14 }}>Loading leads…</div>
      ) : leads.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: t.textMuted, fontSize: 14, background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14 }}>
          No leads found
        </div>
      ) : (
        leads.map(lead => (
          <LeadCard key={lead.id} lead={lead} onClick={() => navigate(`/agent/leads/${lead.id}`)} />
        ))
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 20 }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '8px 16px', borderRadius: 9, fontSize: 13, cursor: page === 1 ? 'not-allowed' : 'pointer',
              background: t.bgCard, border: `1px solid ${t.border}`, color: page === 1 ? t.textFaint : t.text,
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
              background: t.bgCard, border: `1px solid ${t.border}`, color: page === totalPages ? t.textFaint : t.text,
            }}
          >Next →</button>
        </div>
      )}
    </div>
  );
};
