/**
 * Leads Page Component
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useToast } from '../contexts/ToastContext';

// ─── Lead History Types ───────────────────────────────────────────────────────

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
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(new Set());
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [expandedLeads, setExpandedLeads] = useState<Set<number>>(new Set());
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
    if (sent) return <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">Sent</span>;
    if (status === 'failed') return <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800 rounded-full">Failed</span>;
    return <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">Pending</span>;
  };

  const handleSelectLead = useCallback(async (lead: Lead) => {
    setSelectedLead(lead);
    setLeadHistory(null);
    setHistoryLoading(true);
    try {
      const res = await axios.get<LeadHistory>(`${API_BASE_URL}/buyer-leads/leads/${lead.id}/history`);
      setLeadHistory(res.data);
    } catch {
      // history is optional — silently fail
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const handleBack = () => { setSelectedLead(null); setLeadHistory(null); };
  const toggleCompany = (k: string) => setExpandedCompanies(s => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const toggleAgent = (k: string) => setExpandedAgents(s => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const toggleLead = (id: number) => setExpandedLeads(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

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

  if (selectedLead) {
    const bucketColor = (b: string) => {
      if (b === 'HOT') return { bg: '#FF3B30', text: '#fff' };
      if (b === 'WARM') return { bg: '#FF9500', text: '#fff' };
      return { bg: '#8E8E93', text: '#fff' };
    };
    const latestScore = leadHistory?.submissions.find(s => s.score)?.score ?? null;
    const bucket = latestScore?.bucket ?? null;
    const bc = bucket ? bucketColor(bucket) : null;

    return (
      <div style={{ minHeight: '100vh', background: '#F2F2F7', fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif' }} data-testid="lead-detail">
        {/* Sticky header */}
        <div style={{ position: 'sticky', top: 0, zIndex: 10, background: 'rgba(242,242,247,0.85)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderBottom: '0.5px solid rgba(0,0,0,0.12)', padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={handleBack} style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#007AFF', background: 'none', border: 'none', cursor: 'pointer', fontSize: 17, fontWeight: 400, padding: 0 }}>
            <svg width="10" height="17" viewBox="0 0 10 17" fill="none"><path d="M9 1L1 8.5L9 16" stroke="#007AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Leads
          </button>
          <span style={{ flex: 1, textAlign: 'center', fontSize: 17, fontWeight: 600, color: '#1C1C1E', marginRight: 60 }}>{selectedLead.name || 'Lead'}</span>
          {bc && <span style={{ background: bc.bg, color: bc.text, fontSize: 12, fontWeight: 700, padding: '3px 10px', borderRadius: 20, letterSpacing: 0.5 }}>{bucket}</span>}
        </div>

        <div style={{ maxWidth: 680, margin: '0 auto', padding: '24px 16px 48px' }}>
          {/* Lead info card */}
          <div style={{ background: '#fff', borderRadius: 16, overflow: 'hidden', marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
            <div style={{ padding: '20px 20px 0', display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 56, height: 56, borderRadius: 28, background: 'linear-gradient(135deg, #007AFF, #5856D6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 22, fontWeight: 600, flexShrink: 0 }}>
                {(selectedLead.name || '?')[0].toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 600, color: '#1C1C1E' }}>{selectedLead.name || '—'}</div>
                <div style={{ fontSize: 14, color: '#8E8E93', marginTop: 2 }}>{selectedLead.source_email || '—'}</div>
              </div>
            </div>
            <div style={{ padding: '16px 20px 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px' }}>
              {[
                ['Phone', selectedLead.phone],
                ['Agent', selectedLead.agent_name || selectedLead.agent_id],
                ['Company', selectedLead.company_name],
                ['Created', new Date(selectedLead.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })],
              ].map(([label, val]) => (
                <div key={label as string}>
                  <div style={{ fontSize: 11, fontWeight: 500, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
                  <div style={{ fontSize: 15, color: '#1C1C1E', marginTop: 3 }}>{val || '—'}</div>
                </div>
              ))}
            </div>
          </div>

          {historyLoading && (
            <div style={{ textAlign: 'center', padding: 40, color: '#8E8E93', fontSize: 15 }}>Loading history…</div>
          )}

          {leadHistory && !historyLoading && (
            <>
              {/* Score card */}
              {latestScore && (
                <div style={{ background: '#fff', borderRadius: 16, padding: '20px', marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 16 }}>Score</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                    <div style={{ fontSize: 52, fontWeight: 700, color: '#1C1C1E', lineHeight: 1 }}>{latestScore.total}</div>
                    {bc && <span style={{ background: bc.bg, color: bc.text, fontSize: 14, fontWeight: 700, padding: '5px 14px', borderRadius: 20 }}>{bucket}</span>}
                  </div>
                  {latestScore.explanation && <div style={{ fontSize: 14, color: '#3C3C43', marginBottom: 16, lineHeight: 1.5 }}>{latestScore.explanation}</div>}
                  {latestScore.breakdown.length > 0 && (
                    <div style={{ borderTop: '0.5px solid #E5E5EA', paddingTop: 12 }}>
                      {latestScore.breakdown.map((row, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: i < latestScore.breakdown.length - 1 ? '0.5px solid #F2F2F7' : 'none' }}>
                          <div>
                            <div style={{ fontSize: 14, color: '#1C1C1E', fontWeight: 500 }}>{row.question_key}</div>
                            {row.reason && <div style={{ fontSize: 12, color: '#8E8E93', marginTop: 2 }}>{row.reason}</div>}
                          </div>
                          <span style={{ fontSize: 15, fontWeight: 600, color: row.points > 0 ? '#34C759' : row.points < 0 ? '#FF3B30' : '#8E8E93' }}>
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
                <div style={{ background: '#fff', borderRadius: 16, padding: '20px', marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 16 }}>Timeline</div>
                  <div style={{ position: 'relative' }}>
                    {leadHistory.state_transitions.map((t, i) => (
                      <div key={t.id} style={{ display: 'flex', gap: 14, paddingBottom: i < leadHistory.state_transitions.length - 1 ? 20 : 0, position: 'relative' }}>
                        {/* Line */}
                        {i < leadHistory.state_transitions.length - 1 && (
                          <div style={{ position: 'absolute', left: 7, top: 18, bottom: 0, width: 2, background: '#E5E5EA' }} />
                        )}
                        {/* Dot */}
                        <div style={{ width: 16, height: 16, borderRadius: 8, background: i === leadHistory.state_transitions.length - 1 ? '#007AFF' : '#C7C7CC', flexShrink: 0, marginTop: 2, zIndex: 1 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 15, fontWeight: 500, color: '#1C1C1E' }}>{t.to_state.replace(/_/g, ' ')}</div>
                          <div style={{ display: 'flex', gap: 8, marginTop: 3, flexWrap: 'wrap' }}>
                            {t.occurred_at && <span style={{ fontSize: 12, color: '#8E8E93' }}>{new Date(t.occurred_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>}
                            {t.actor_type && <span style={{ fontSize: 11, fontWeight: 600, color: '#007AFF', background: '#EAF4FF', padding: '1px 7px', borderRadius: 10 }}>{t.actor_type}</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Form answers */}
              {leadHistory.submissions.length > 0 && leadHistory.submissions[0].answers.length > 0 && (
                <div style={{ background: '#fff', borderRadius: 16, padding: '20px', marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 16 }}>Form Answers</div>
                  {leadHistory.submissions[0].answers.map((a, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: i < leadHistory.submissions[0].answers.length - 1 ? '0.5px solid #F2F2F7' : 'none' }}>
                      <span style={{ fontSize: 14, color: '#8E8E93', fontWeight: 500 }}>{a.question_key.replace(/_/g, ' ')}</span>
                      <span style={{ fontSize: 14, color: '#1C1C1E', fontWeight: 500, textAlign: 'right', maxWidth: '55%' }}>
                        {Array.isArray(a.answer) ? (a.answer as string[]).join(', ') : String(a.answer ?? '—')}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Interactions */}
              {leadHistory.interactions.length > 0 && (
                <div style={{ background: '#fff', borderRadius: 16, padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 16 }}>Interactions</div>
                  {leadHistory.interactions.map((ix, i) => (
                    <div key={ix.id} style={{ padding: '12px 0', borderBottom: i < leadHistory.interactions.length - 1 ? '0.5px solid #F2F2F7' : 'none' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <span style={{ fontSize: 11, fontWeight: 600, color: ix.direction === 'outbound' ? '#007AFF' : '#34C759', background: ix.direction === 'outbound' ? '#EAF4FF' : '#EAFAF1', padding: '2px 8px', borderRadius: 10 }}>{ix.direction}</span>
                          <span style={{ fontSize: 11, fontWeight: 600, color: '#8E8E93', background: '#F2F2F7', padding: '2px 8px', borderRadius: 10 }}>{ix.channel}</span>
                        </div>
                        {ix.occurred_at && <span style={{ fontSize: 12, color: '#8E8E93' }}>{new Date(ix.occurred_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>}
                      </div>
                      {ix.content_text && <div style={{ fontSize: 14, color: '#3C3C43', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{ix.content_text}</div>}
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Leads <span className="text-sm font-normal text-gray-500">({total})</span></h1>
        <button onClick={handleExport} disabled={exporting}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
          data-testid="export-btn">
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>

      <div className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="lead-filters">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Company</label>
          <select value={filters.company_id} onChange={(e) => { handleFilterChange('company_id', e.target.value); handleFilterChange('agent_id', ''); }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">All Companies</option>
            {companies.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Agent</label>
          <select value={filters.agent_id} onChange={(e) => handleFilterChange('agent_id', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-agent-id">
            <option value="">All Agents</option>
            {filteredAgents.map(a => <option key={a.agent_id} value={a.agent_id}>{a.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Start Date</label>
          <input type="date" value={filters.start_date} onChange={(e) => handleFilterChange('start_date', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-start-date" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">End Date</label>
          <input type="date" value={filters.end_date} onChange={(e) => handleFilterChange('end_date', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-end-date" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Response</label>
          <select value={filters.response_sent} onChange={(e) => handleFilterChange('response_sent', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-response">
            <option value="">All</option>
            <option value="true">Sent</option>
            <option value="false">Not Sent</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32"><span className="text-gray-500">Loading leads...</span></div>
      ) : fetchError ? (
        <div className="flex items-center justify-center h-32"><span className="text-red-600">{fetchError}</span></div>
      ) : leads.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500" data-testid="leads-empty">No leads found</div>
      ) : (
        <>
          <div className="space-y-3" data-testid="leads-table">
            {Object.entries(grouped).map(([cKey, company]) => (
              <div key={cKey} className="bg-white rounded-lg shadow overflow-hidden">
                <button onClick={() => toggleCompany(cKey)}
                  className="w-full flex items-center justify-between px-5 py-3 bg-blue-50 hover:bg-blue-100 text-left">
                  <span className="font-semibold text-blue-800 text-sm">{company.label}</span>
                  <span className="text-blue-500 text-xs">{expandedCompanies.has(cKey) ? '▲' : '▼'}</span>
                </button>
                {expandedCompanies.has(cKey) && (
                  <div className="divide-y divide-gray-100">
                    {Object.entries(company.agents).map(([aKey, agent]) => (
                      <div key={aKey}>
                        <button onClick={() => toggleAgent(`${cKey}:${aKey}`)}
                          className="w-full flex items-center justify-between px-8 py-2 bg-gray-50 hover:bg-gray-100 text-left">
                          <span className="font-medium text-gray-700 text-sm">{agent.label}</span>
                          <span className="text-gray-400 text-xs">{agent.leads.length} lead{agent.leads.length !== 1 ? 's' : ''} {expandedAgents.has(`${cKey}:${aKey}`) ? '▲' : '▼'}</span>
                        </button>
                        {expandedAgents.has(`${cKey}:${aKey}`) && (
                          <table className="min-w-full">
                            <thead className="bg-gray-50 border-t border-gray-200">
                              <tr>
                                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Agent</th>
                                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Lead Name</th>
                                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>
                                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                              {agent.leads.map(lead => (
                                <React.Fragment key={lead.id}>
                                  <tr className="hover:bg-gray-50" data-testid={`lead-row-${lead.id}`}>
                                    <td className="px-6 py-3 text-sm text-gray-700">{lead.agent_name || lead.agent_id || '—'}</td>
                                    <td className="px-6 py-3 text-sm font-medium text-gray-900">{lead.name || '—'}</td>
                                    <td className="px-6 py-3 text-sm text-gray-500">{lead.phone || '—'}</td>
                                    <td className="px-6 py-3 text-sm text-gray-500">{lead.source_email || '—'}</td>
                                    <td className="px-6 py-3 text-sm text-gray-500">{new Date(lead.created_at).toLocaleDateString()}</td>
                                    <td className="px-6 py-3">{statusBadge(lead.response_sent, lead.response_status)}</td>
                                    <td className="px-6 py-3 text-right">
                                      <button onClick={() => toggleLead(lead.id)} className="text-gray-500 hover:text-gray-700 text-xs mr-2">
                                        {expandedLeads.has(lead.id) ? 'Hide' : 'Details'}
                                      </button>
                                      <button onClick={() => handleSelectLead(lead)} className="text-blue-600 hover:text-blue-900 text-xs" data-testid={`view-lead-${lead.id}`}>View</button>
                                    </td>
                                  </tr>
                                  {expandedLeads.has(lead.id) && (
                                    <tr className="bg-blue-50">
                                      <td colSpan={7} className="px-8 py-3">
                                        <dl className="grid grid-cols-3 gap-3 text-xs">
                                          <div><dt className="text-gray-400 uppercase">Gmail UID</dt><dd className="text-gray-700 mt-0.5">{lead.gmail_uid || '—'}</dd></div>
                                          <div><dt className="text-gray-400 uppercase">Response Status</dt><dd className="text-gray-700 mt-0.5">{lead.response_status || '—'}</dd></div>
                                          <div><dt className="text-gray-400 uppercase">Company</dt><dd className="text-gray-700 mt-0.5">{lead.company_name || '—'}</dd></div>
                                        </dl>
                                      </td>
                                    </tr>
                                  )}
                                </React.Fragment>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between" data-testid="pagination">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">Previous</button>
              <span className="text-sm text-gray-600">Page {page} of {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
