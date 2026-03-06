/**
 * Leads Page Component
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useToast } from '../contexts/ToastContext';
import { useT } from '../utils/useT';

interface StateTransition {
  id: number;
  from_state: string | null;
  to_state: string;
  occurred_at: string | null;
  actor_type: string | null;
  metadata: Record<string, unknown> | null;
}

interface AnswerItem { question_key: string; answer: unknown; }
interface ScoreBreakdown { question_key: string; answer: unknown; points: number; reason: string; }
interface SubmissionScore {
  total: number;
  bucket: string;
  breakdown: ScoreBreakdown[];
  explanation: string;
}
interface Submission {
  id: number;
  submitted_at: string | null;
  form_version_id: number | null;
  answers: AnswerItem[];
  score: SubmissionScore | null;
}
interface Interaction {
  id: number;
  channel: string;
  direction: string;
  occurred_at: string | null;
  content_text: string | null;
  metadata: Record<string, unknown> | null;
}
interface LeadHistory {
  lead_id: number;
  state_transitions: StateTransition[];
  submissions: Submission[];
  interactions: Interaction[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface Lead {
  id: number;
  name: string | null;
  phone: string | null;
  source_email: string | null;
  gmail_uid: string | null;
  created_at: string;
  response_sent: boolean;
  response_status: string | null;
  agent_id: string | null;
  agent_name: string | null;
  company_id: number | null;
  company_name: string | null;
}

interface Company { id: number; name: string; }
interface Agent { agent_id: string; name: string; company_id: number | null; }

interface LeadFilters {
  company_id: string;
  agent_id: string;
  start_date: string;
  end_date: string;
  response_sent: string;
}

interface LeadsResponse {
  leads: Lead[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export const LeadsPage: React.FC = () => {
  const { success, error: toastError } = useToast();
  const t = useT();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<LeadFilters>({ company_id: '', agent_id: '', start_date: '', end_date: '', response_sent: '' });
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [exporting, setExporting] = useState(false);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [flatView, setFlatView] = useState(true);
  const [leadHistory, setLeadHistory] = useState<LeadHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    axios.get(`${API_BASE_URL}/companies`).then(r => setCompanies(Array.isArray(r.data) ? r.data : (r.data.companies || []))).catch(() => {});
    axios.get(`${API_BASE_URL}/agents`).then(r => setAgents(Array.isArray(r.data) ? r.data : (r.data.agents || []))).catch(() => {});
  }, []);

  const buildParams = useCallback(() => {
    const p: Record<string, string> = { page: String(page), per_page: '25', sort: 'created_at', order: 'desc' };
    if (filters.company_id) p.company_id = filters.company_id;
    if (filters.agent_id) p.agent_id = filters.agent_id;
    if (filters.start_date) p.start_date = filters.start_date;
    if (filters.end_date) p.end_date = filters.end_date;
    if (filters.response_sent !== '') p.response_sent = filters.response_sent;
    return p;
  }, [page, filters]);

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<LeadsResponse>(`${API_BASE_URL}/leads`, { params: buildParams() });
      setLeads(res.data.leads);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
      setFetchError(null);
    } catch {
      setFetchError('Failed to load leads');
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const handleFilterChange = (key: keyof LeadFilters, val: string) => {
    setFilters((f) => ({ ...f, [key]: val }));
    setPage(1);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = buildParams();
      delete params.page;
      delete params.per_page;
      const res = await axios.get(`${API_BASE_URL}/leads/export`, { params, responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `leads_export_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      success('CSV exported successfully');
    } catch {
      toastError('Failed to export leads');
    } finally {
      setExporting(false);
    }
  };

  const statusBadge = (sent: boolean, status: string | null) => {
    if (sent) return (
      <span style={{ padding: '2px 10px', fontSize: 11, fontWeight: 600, background: t.greenBg, color: t.green, borderRadius: 20 }}>Sent</span>
    );
    if (status === 'failed') return (
      <span style={{ padding: '2px 10px', fontSize: 11, fontWeight: 600, background: t.redBg, color: t.red, borderRadius: 20 }}>Failed</span>
    );
    return (
      <span style={{ padding: '2px 10px', fontSize: 11, fontWeight: 600, background: t.bgBadge, color: t.textMuted, borderRadius: 20 }}>Pending</span>
    );
  };

  const handleSelectLead = useCallback(async (lead: Lead) => {
    setSelectedLead(lead);
    setLeadHistory(null);
    setHistoryLoading(true);
    try {
      const res = await axios.get<LeadHistory>(`${API_BASE_URL}/buyer-leads/leads/${lead.id}/history`);
      setLeadHistory(res.data);
    } catch {
      // history is optional
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const handleBack = () => { setSelectedLead(null); setLeadHistory(null); };

  const grouped = leads.reduce<Record<string, { label: string; agents: Record<string, { label: string; leads: Lead[] }> }>>((acc, lead) => {
    const cKey = lead.company_id != null ? String(lead.company_id) : 'none';
    const cLabel = lead.company_name || (lead.company_id != null ? `Company ${lead.company_id}` : 'No Company');
    const aKey = lead.agent_id || 'unknown';
    const aLabel = lead.agent_name || lead.agent_id || 'Unknown Agent';
    if (!acc[cKey]) acc[cKey] = { label: cLabel, agents: {} };
    if (!acc[cKey].agents[aKey]) acc[cKey].agents[aKey] = { label: aLabel, leads: [] };
    acc[cKey].agents[aKey].leads.push(lead);
    return acc;
  }, {});

  // ── Lead Detail View ──────────────────────────────────────────────────────
  if (selectedLead) {
    const bucketColor = (b: string) => {
      if (b === 'HOT') return { bg: t.red, text: '#fff' };
      if (b === 'WARM') return { bg: t.orange, text: '#fff' };
      return { bg: t.textMuted, text: '#fff' };
    };
    const latestScore = leadHistory?.submissions.find(s => s.score)?.score ?? null;
    const bucket = latestScore?.bucket ?? null;
    const bc = bucket ? bucketColor(bucket) : null;

    return (
      <div style={{ minHeight: '100vh', background: t.bgPage, fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif' }} data-testid="lead-detail">
        {/* Sticky header */}
        <div style={{ position: 'sticky', top: 0, zIndex: 10, background: t.bgHeader, backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderBottom: `1px solid ${t.border}`, padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={handleBack} style={{ display: 'flex', alignItems: 'center', gap: 4, color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 15, fontWeight: 400, padding: 0 }}>
            <svg width="10" height="17" viewBox="0 0 10 17" fill="none"><path d="M9 1L1 8.5L9 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Leads
          </button>
          <span style={{ flex: 1, textAlign: 'center', fontSize: 17, fontWeight: 600, color: t.text, marginRight: 60 }}>{selectedLead.name || 'Lead'}</span>
          {bc && <span style={{ background: bc.bg, color: bc.text, fontSize: 12, fontWeight: 700, padding: '3px 10px', borderRadius: 20, letterSpacing: 0.5 }}>{bucket}</span>}
        </div>

        <div style={{ maxWidth: 680, margin: '0 auto', padding: '24px 16px 48px' }}>
          {/* Lead info card */}
          <div style={{ ...t.card, marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
              <div style={{ width: 52, height: 52, borderRadius: 26, background: t.accentGrad, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 20, fontWeight: 600, flexShrink: 0 }}>
                {(selectedLead.name || '?')[0].toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 600, color: t.text }}>{selectedLead.name || '—'}</div>
                <div style={{ fontSize: 13, color: t.textMuted, marginTop: 2 }}>{selectedLead.source_email || '—'}</div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px' }}>
              {[
                ['Phone', selectedLead.phone],
                ['Agent', selectedLead.agent_name || selectedLead.agent_id],
                ['Company', selectedLead.company_name],
                ['Created', new Date(selectedLead.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })],
              ].map(([label, val]) => (
                <div key={label as string}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
                  <div style={{ fontSize: 14, color: t.text, marginTop: 3 }}>{val || '—'}</div>
                </div>
              ))}
            </div>
          </div>

          {historyLoading && (
            <div style={{ textAlign: 'center', padding: 40, color: t.textMuted, fontSize: 14 }}>Loading history…</div>
          )}

          {leadHistory && !historyLoading && (
            <>
              {/* Score card */}
              {latestScore && (
                <div style={{ ...t.card, marginBottom: 16 }}>
                  <div style={t.sectionTitle}>Score</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
                    <div style={{ fontSize: 48, fontWeight: 700, color: t.text, lineHeight: 1 }}>{latestScore.total}</div>
                    {bc && <span style={{ background: bc.bg, color: bc.text, fontSize: 13, fontWeight: 700, padding: '4px 12px', borderRadius: 20 }}>{bucket}</span>}
                  </div>
                  {latestScore.explanation && <div style={{ fontSize: 13, color: t.textSecondary, marginBottom: 12, lineHeight: 1.5 }}>{latestScore.explanation}</div>}
                  {latestScore.breakdown.length > 0 && (
                    <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 10 }}>
                      {latestScore.breakdown.map((row, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: i < latestScore.breakdown.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                          <div>
                            <div style={{ fontSize: 13, color: t.text, fontWeight: 500 }}>{row.question_key}</div>
                            {row.reason && <div style={{ fontSize: 11, color: t.textMuted, marginTop: 2 }}>{row.reason}</div>}
                          </div>
                          <span style={{ fontSize: 14, fontWeight: 600, color: row.points > 0 ? t.green : row.points < 0 ? t.red : t.textMuted }}>
                            {row.points > 0 ? '+' : ''}{row.points}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* State timeline */}
              {leadHistory.state_transitions.length > 0 && (
                <div style={{ ...t.card, marginBottom: 16 }}>
                  <div style={t.sectionTitle}>Timeline</div>
                  <div style={{ position: 'relative' }}>
                    {leadHistory.state_transitions.map((tr, i) => (
                      <div key={tr.id} style={{ display: 'flex', gap: 14, paddingBottom: i < leadHistory.state_transitions.length - 1 ? 20 : 0, position: 'relative' }}>
                        {i < leadHistory.state_transitions.length - 1 && (
                          <div style={{ position: 'absolute', left: 7, top: 18, bottom: 0, width: 2, background: t.border }} />
                        )}
                        <div style={{ width: 16, height: 16, borderRadius: 8, background: i === leadHistory.state_transitions.length - 1 ? t.accent : t.border, flexShrink: 0, marginTop: 2, zIndex: 1 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, fontWeight: 500, color: t.text }}>{tr.to_state.replace(/_/g, ' ')}</div>
                          <div style={{ display: 'flex', gap: 8, marginTop: 3, flexWrap: 'wrap' }}>
                            {tr.occurred_at && <span style={{ fontSize: 11, color: t.textMuted }}>{new Date(tr.occurred_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>}
                            {tr.actor_type && <span style={{ fontSize: 10, fontWeight: 600, color: t.accent, background: t.accentBg, padding: '1px 7px', borderRadius: 10 }}>{tr.actor_type}</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Form answers */}
              {leadHistory.submissions.length > 0 && leadHistory.submissions[0].answers.length > 0 && (
                <div style={{ ...t.card, marginBottom: 16 }}>
                  <div style={t.sectionTitle}>Form Answers</div>
                  {leadHistory.submissions[0].answers.map((a, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: i < leadHistory.submissions[0].answers.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                      <span style={{ fontSize: 13, color: t.textMuted, fontWeight: 500 }}>{a.question_key.replace(/_/g, ' ')}</span>
                      <span style={{ fontSize: 13, color: t.text, fontWeight: 500, textAlign: 'right', maxWidth: '55%' }}>
                        {Array.isArray(a.answer) ? (a.answer as string[]).join(', ') : String(a.answer ?? '—')}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Interactions */}
              {leadHistory.interactions.length > 0 && (
                <div style={t.card}>
                  <div style={t.sectionTitle}>Interactions</div>
                  {leadHistory.interactions.map((ix, i) => (
                    <div key={ix.id} style={{ padding: '10px 0', borderBottom: i < leadHistory.interactions.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <span style={{ fontSize: 10, fontWeight: 600, color: ix.direction === 'outbound' ? t.accent : t.green, background: ix.direction === 'outbound' ? t.accentBg : t.greenBg, padding: '2px 8px', borderRadius: 10 }}>{ix.direction}</span>
                          <span style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, background: t.bgBadge, padding: '2px 8px', borderRadius: 10 }}>{ix.channel}</span>
                        </div>
                        {ix.occurred_at && <span style={{ fontSize: 11, color: t.textMuted }}>{new Date(ix.occurred_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>}
                      </div>
                      {ix.content_text && <div style={{ fontSize: 13, color: t.textSecondary, lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{ix.content_text}</div>}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  const filteredAgents = filters.company_id ? agents.filter(a => String(a.company_id) === filters.company_id) : agents;

  const selectStyle: React.CSSProperties = { ...t.input, width: '100%' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>
          Leads <span style={{ fontSize: 13, fontWeight: 400, color: t.textMuted }}>({total})</span>
        </h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setFlatView(v => !v)} style={t.btnSecondary}>
            {flatView ? 'Group by Company' : 'Flat List'}
          </button>
          <button onClick={handleExport} disabled={exporting} style={{ ...t.btnPrimary, background: `linear-gradient(135deg, ${t.green}, #059669)`, boxShadow: `0 4px 14px ${t.greenBg}` }} data-testid="export-btn">
            {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ ...t.card, display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }} data-testid="lead-filters">
        {[
          { label: 'Company', key: 'company_id' as const, type: 'select', options: companies.map(c => ({ value: String(c.id), label: c.name })), placeholder: 'All Companies', extra: () => handleFilterChange('agent_id', '') },
          { label: 'Agent', key: 'agent_id' as const, type: 'select', options: filteredAgents.map(a => ({ value: a.agent_id, label: a.name })), placeholder: 'All Agents' },
          { label: 'Start Date', key: 'start_date' as const, type: 'date' },
          { label: 'End Date', key: 'end_date' as const, type: 'date' },
          { label: 'Response', key: 'response_sent' as const, type: 'select', options: [{ value: 'true', label: 'Sent' }, { value: 'false', label: 'Not Sent' }], placeholder: 'All' },
        ].map(({ label, key, type, options, placeholder, extra }) => (
          <div key={key}>
            <label style={t.labelStyle}>{label}</label>
            {type === 'select' ? (
              <select value={filters[key]} onChange={(e) => { handleFilterChange(key, e.target.value); extra?.(); }} style={selectStyle}>
                <option value="">{placeholder}</option>
                {options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            ) : (
              <input type="date" value={filters[key]} onChange={(e) => handleFilterChange(key, e.target.value)} style={selectStyle} />
            )}
          </div>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120, color: t.textMuted }}>Loading leads…</div>
      ) : fetchError ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120, color: t.red }}>{fetchError}</div>
      ) : leads.length === 0 ? (
        <div style={{ ...t.card, textAlign: 'center', padding: '48px 24px', color: t.textMuted }} data-testid="leads-empty">No leads found</div>
      ) : (
        <>
          {flatView ? (
            <div style={t.card} data-testid="leads-table">
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Lead Name', 'Phone', 'Source', 'Agent', 'Company', 'Created', 'Status', ''].map(h => (
                      <th key={h} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {leads.map(lead => (
                    <tr key={lead.id} data-testid={`lead-row-${lead.id}`} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={{ ...t.td, fontWeight: 500 }}>{lead.name || '—'}</td>
                      <td style={{ ...t.td, color: t.textMuted }}>{lead.phone || '—'}</td>
                      <td style={{ ...t.td, color: t.textMuted, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{lead.source_email || '—'}</td>
                      <td style={t.td}>{lead.agent_name || lead.agent_id || '—'}</td>
                      <td style={t.td}>{lead.company_name || '—'}</td>
                      <td style={{ ...t.td, color: t.textMuted }}>{new Date(lead.created_at).toLocaleDateString()}</td>
                      <td style={t.td}>{statusBadge(lead.response_sent, lead.response_status)}</td>
                      <td style={{ ...t.td, textAlign: 'right' }}>
                        <button onClick={() => handleSelectLead(lead)} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }} data-testid={`view-lead-${lead.id}`}>View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="leads-table">
              {Object.entries(grouped).map(([cKey, company]) => (
                <div key={cKey} style={t.card}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.accent, marginBottom: 12 }}>{company.label}</div>
                  {Object.entries(company.agents).map(([aKey, agent]) => (
                    <div key={aKey} style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 500, color: t.textMuted, marginBottom: 8 }}>{agent.label} · {agent.leads.length} lead{agent.leads.length !== 1 ? 's' : ''}</div>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            {['Name', 'Phone', 'Source', 'Created', 'Status', ''].map(h => (
                              <th key={h} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left' }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {agent.leads.map(lead => (
                            <tr key={lead.id} style={{ borderBottom: `1px solid ${t.border}` }} data-testid={`lead-row-${lead.id}`}>
                              <td style={{ ...t.td, fontWeight: 500 }}>{lead.name || '—'}</td>
                              <td style={{ ...t.td, color: t.textMuted }}>{lead.phone || '—'}</td>
                              <td style={{ ...t.td, color: t.textMuted }}>{lead.source_email || '—'}</td>
                              <td style={{ ...t.td, color: t.textMuted }}>{new Date(lead.created_at).toLocaleDateString()}</td>
                              <td style={t.td}>{statusBadge(lead.response_sent, lead.response_status)}</td>
                              <td style={{ ...t.td, textAlign: 'right' }}>
                                <button onClick={() => handleSelectLead(lead)} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }} data-testid={`view-lead-${lead.id}`}>View</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }} data-testid="pagination">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>Previous</button>
              <span style={{ fontSize: 13, color: t.textMuted }}>Page {page} of {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={{ ...t.btnSecondary, opacity: page === totalPages ? 0.4 : 1 }}>Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
