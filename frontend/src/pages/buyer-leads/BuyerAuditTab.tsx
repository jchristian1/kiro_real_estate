import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';
import { useT } from '../../utils/useT';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface AuditEntry { id: number; lead_id: number | null; event_type: string; actor_type?: string; occurred_at: string; metadata_json?: string; }
interface AuditResponse { items: AuditEntry[]; total: number; page: number; page_size: number; }

const EVENT_TYPES = ['STATE_TRANSITION','FORM_INVITE_SENT','FORM_SUBMITTED','SCORE_COMPUTED','EMAIL_SENT','EMAIL_FAILED'];

export const BuyerAuditTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { error: toastError } = useToast();
  const t = useT();

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [leadIdFilter, setLeadIdFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [expandedEntry, setExpandedEntry] = useState<number | null>(null);

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { page: String(page), page_size: '25' };
      if (leadIdFilter) params.lead_id = leadIdFilter;
      if (eventTypeFilter) params.event_type = eventTypeFilter;
      if (startDate) params.date_from = startDate;
      if (endDate) params.date_to = endDate;
      const res = await axios.get<AuditResponse>(`${API}/buyer-leads/tenants/${tenantId}/audit`, { params });
      setEntries(res.data.items);
      setTotalPages(Math.max(1, Math.ceil(res.data.total / 25)));
      setTotal(res.data.total);
    } catch { toastError('Failed to load audit log'); } finally { setLoading(false); }
  }, [tenantId, page, leadIdFilter, eventTypeFilter, startDate, endDate]);

  useEffect(() => { fetchAudit(); }, [fetchAudit]);

  const actorBadge = (actor: string) => {
    const colors: Record<string, { bg: string; color: string }> = {
      SYSTEM: { bg: t.bgBadge, color: t.textMuted },
      AGENT: { bg: t.accentBg, color: t.accent },
      LEAD: { bg: t.greenBg, color: t.green },
    };
    const c = colors[actor] ?? { bg: t.bgBadge, color: t.textMuted };
    return <span style={{ padding: '2px 8px', fontSize: 10, fontWeight: 600, background: c.bg, color: c.color, borderRadius: 20 }}>{actor}</span>;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>Audit Log</h2>
        <span style={{ fontSize: 13, color: t.textMuted }}>{total} entries</span>
      </div>

      <div style={{ ...t.card, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <div>
          <label style={t.labelStyle}>Lead ID</label>
          <input type="number" value={leadIdFilter} onChange={(e) => { setLeadIdFilter(e.target.value); setPage(1); }} placeholder="Any" style={t.input} />
        </div>
        <div>
          <label style={t.labelStyle}>Event Type</label>
          <select value={eventTypeFilter} onChange={(e) => { setEventTypeFilter(e.target.value); setPage(1); }} style={t.input}>
            <option value="">All Events</option>
            {EVENT_TYPES.map(et => <option key={et} value={et}>{et}</option>)}
          </select>
        </div>
        <div>
          <label style={t.labelStyle}>Start Date</label>
          <input type="date" value={startDate} onChange={(e) => { setStartDate(e.target.value); setPage(1); }} style={t.input} />
        </div>
        <div>
          <label style={t.labelStyle}>End Date</label>
          <input type="date" value={endDate} onChange={(e) => { setEndDate(e.target.value); setPage(1); }} style={t.input} />
        </div>
      </div>

      <div style={t.card}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>
        ) : entries.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>No audit entries found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Time', 'Event', 'Actor', 'Lead ID', ''].map(h => <th key={h} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {entries.map((entry) => (
                <React.Fragment key={entry.id}>
                  <tr style={{ borderBottom: `1px solid ${t.border}` }}>
                    <td style={{ ...t.td, fontSize: 11, color: t.textMuted, whiteSpace: 'nowrap' }}>{new Date(entry.occurred_at).toLocaleString()}</td>
                    <td style={{ ...t.td, fontWeight: 500 }}>{entry.event_type}</td>
                    <td style={t.td}>{entry.actor_type ? actorBadge(entry.actor_type) : <span style={{ color: t.textFaint, fontSize: 12 }}>—</span>}</td>
                    <td style={{ ...t.td, color: t.textMuted }}>{entry.lead_id ?? '—'}</td>
                    <td style={{ ...t.td, textAlign: 'right' }}>
                      {entry.metadata_json && (
                        <button onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id)}
                          style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                          {expandedEntry === entry.id ? 'Hide' : 'Show'}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expandedEntry === entry.id && entry.metadata_json && (
                    <tr style={{ background: t.bgInput }}>
                      <td colSpan={5} style={{ padding: '12px 16px' }}>
                        <pre style={{ fontSize: 11, color: t.textSecondary, whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'monospace' }}>
                          {JSON.stringify(JSON.parse(entry.metadata_json), null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
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
