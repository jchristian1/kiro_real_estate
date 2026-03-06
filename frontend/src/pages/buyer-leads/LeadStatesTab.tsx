import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';
import { useT } from '../../utils/useT';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface LeadStateRow { lead_id: number; name: string | null; source_email: string | null; current_state: string | null; current_state_updated_at: string | null; }
interface LeadsStateResponse { items: LeadStateRow[]; total: number; page: number; page_size: number; }
interface FunnelEntry { state: string; count: number; }

const STATE_OPTIONS = ['NEW','FORM_INVITE_CREATED','FORM_INVITE_SENT','FORM_SUBMITTED','SCORED','POST_SUBMISSION_EMAIL_SENT','DISQUALIFIED','ARCHIVED'];
const BUCKET_OPTIONS = ['HOT', 'WARM', 'NURTURE'];

export const LeadStatesTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { error: toastError } = useToast();
  const t = useT();

  const [leads, setLeads] = useState<LeadStateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [stateFilter, setStateFilter] = useState('');
  const [bucketFilter, setBucketFilter] = useState('');
  const [funnel, setFunnel] = useState<FunnelEntry[]>([]);
  const [funnelLoading, setFunnelLoading] = useState(true);

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { page: String(page), page_size: '25' };
      if (stateFilter) params.state = stateFilter;
      if (bucketFilter) params.bucket = bucketFilter;
      const res = await axios.get<LeadsStateResponse>(`${API}/buyer-leads/tenants/${tenantId}/leads/states`, { params });
      setLeads(res.data.items);
      setTotalPages(Math.max(1, Math.ceil(res.data.total / 25)));
      setTotal(res.data.total);
    } catch { toastError('Failed to load lead states'); } finally { setLoading(false); }
  }, [tenantId, page, stateFilter, bucketFilter]);

  const fetchFunnel = useCallback(async () => {
    setFunnelLoading(true);
    try {
      const res = await axios.get<Record<string, number>>(`${API}/buyer-leads/tenants/${tenantId}/leads/funnel`);
      setFunnel(Object.entries(res.data).map(([state, count]) => ({ state, count })));
    } catch { /* non-critical */ } finally { setFunnelLoading(false); }
  }, [tenantId]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);
  useEffect(() => { fetchFunnel(); }, [fetchFunnel]);

  const maxCount = funnel.reduce((m, e) => Math.max(m, e.count), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>Lead States</h2>

      {/* Funnel chart */}
      {!funnelLoading && funnel.length > 0 && (
        <div style={t.card}>
          <div style={t.sectionTitle}>State Funnel</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {funnel.map((entry) => (
              <div key={entry.state} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 11, color: t.textMuted, width: 200, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.state}</span>
                <div style={{ flex: 1, background: t.bgBadge, borderRadius: 4, height: 14, overflow: 'hidden' }}>
                  <div style={{ background: t.accentGrad, height: 14, borderRadius: 4, width: `${(entry.count / maxCount) * 100}%`, transition: 'width 0.3s' }} />
                </div>
                <span style={{ fontSize: 11, fontWeight: 600, color: t.text, width: 28, textAlign: 'right' }}>{entry.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ ...t.card, display: 'flex', gap: 16, alignItems: 'flex-end' }}>
        <div>
          <label style={t.labelStyle}>State</label>
          <select value={stateFilter} onChange={(e) => { setStateFilter(e.target.value); setPage(1); }} style={t.input}>
            <option value="">All States</option>
            {STATE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label style={t.labelStyle}>Bucket</label>
          <select value={bucketFilter} onChange={(e) => { setBucketFilter(e.target.value); setPage(1); }} style={t.input}>
            <option value="">All Buckets</option>
            {BUCKET_OPTIONS.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <span style={{ fontSize: 13, color: t.textMuted, paddingBottom: 2 }}>{total} leads</span>
      </div>

      {/* Table */}
      <div style={t.card}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>
        ) : leads.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>No leads found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Lead', 'State', 'Email', 'Updated'].map(h => <th key={h} style={t.th}>{h}</th>)}
            </tr></thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.lead_id} style={{ borderBottom: `1px solid ${t.border}` }}>
                  <td style={{ ...t.td, fontWeight: 500 }}>{lead.name || `Lead #${lead.lead_id}`}</td>
                  <td style={{ ...t.td, color: t.textSecondary }}>{lead.current_state || '—'}</td>
                  <td style={{ ...t.td, color: t.textMuted }}>{lead.source_email || '—'}</td>
                  <td style={{ ...t.td, color: t.textMuted }}>{lead.current_state_updated_at ? new Date(lead.current_state_updated_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>Previous</button>
          <span style={{ fontSize: 13, color: t.textMuted }}>Page {page} of {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={{ ...t.btnSecondary, opacity: page === totalPages ? 0.4 : 1 }}>Next</button>
        </div>
      )}
    </div>
  );
};
