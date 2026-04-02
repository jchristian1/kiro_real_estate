import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { AgentForm, AgentFormValues, AgentEditFormValues, AgentDetail } from '@/platformAdminComponents/Agents';

import { useT } from '@/shared/hooks';
import { ConfirmDialog } from '@/platformAdminComponents/ConfirmDialog';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';



interface Agent {
  id: number; agent_id: string; email: string; display_name: string | null;
  phone: string | null; company_id: number | null; company_name: string | null;
  created_at: string; updated_at: string; watcher_status: string | null;
}
type View = 'list' | 'create' | 'edit' | 'detail';

const PAGE_SIZE = 20;

export const AgentsPage: React.FC = () => {
  const t = useT();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>('list');
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Agent | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const [agentsRes, watchersRes] = await Promise.all([
        axios.get<{ agents: Agent[] }>(`${API_BASE_URL}/agents`),
        axios.get<{ watchers: { agent_id: string; status: string }[] }>(`${API_BASE_URL}/watchers/status`).catch(() => ({ data: { watchers: [] } })),
      ]);
      const statusMap: Record<string, string> = {};
      for (const w of watchersRes.data.watchers) statusMap[w.agent_id] = w.status;
      setAgents(agentsRes.data.agents.map(a => {
        // Never let the live watcher registry override a "cancelled" DB status
        if (a.watcher_status === 'cancelled') return a;
        return { ...a, watcher_status: statusMap[a.agent_id] ?? a.watcher_status };
      }));
      setError(null);
    } catch { setError('Failed to load agents'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAgents(); const id = setInterval(fetchAgents, 15000); return () => clearInterval(id); }, []);

  const handleCreate = async (data: AgentFormValues | AgentEditFormValues) => {
    setSubmitting(true); setServerError(null);
    try { await axios.post(`${API_BASE_URL}/agents`, data); await fetchAgents(); setView('list'); }
    catch (err) { const e = err as AxiosError<{ message?: string }>; setServerError(e.response?.data?.message || 'Failed to create agent'); }
    finally { setSubmitting(false); }
  };

  const handleEdit = async (data: AgentFormValues | AgentEditFormValues) => {
    if (!selectedAgent) return;
    setSubmitting(true); setServerError(null);
    try { await axios.put(`${API_BASE_URL}/agents/${selectedAgent.agent_id}`, data); await fetchAgents(); setView('list'); setSelectedAgent(null); }
    catch (err) { const e = err as AxiosError<{ message?: string }>; setServerError(e.response?.data?.message || 'Failed to update agent'); }
    finally { setSubmitting(false); }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API_BASE_URL}/agents/${deleteTarget.agent_id}`);
      setAgents(p => p.filter(a => a.agent_id !== deleteTarget.agent_id));
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.message || err.response?.data?.detail || err.message
        : 'Delete failed';
      setServerError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setDeleteTarget(null);
    }
  };

  const statusStyle = (status: string | null) => {
    const s = status?.toLowerCase();
    if (s === 'running') return { color: t.green, bg: t.greenBg };
    if (s === 'failed') return { color: t.red, bg: t.redBg };
    if (s === 'cancelled') return { color: t.orange, bg: t.orangeBg ?? `${t.orange}18` };
    return { color: t.textMuted, bg: t.bgBadge };
  };

  const formCard = (title: string, children: React.ReactNode) => (
    <div className={styles.formContainer}>
      <div className={styles.formHeader}>
        <button onClick={() => { setView('list'); setSelectedAgent(null); setServerError(null); }}
          className={styles.backButton}
          style={{ color: t.accent }}>
          ← Back to Agents
        </button>
        <div className={styles.formTitle} style={{ color: t.text }}>{title}</div>
      </div>
      <div style={t.card}>{children}</div>
    </div>
  );

  if (view === 'detail' && selectedAgent) {
    return <AgentDetail agentId={selectedAgent.agent_id} onBack={() => { setView('list'); setSelectedAgent(null); }} />;
  }
  if (view === 'create') {
    return formCard('Create Agent', <AgentForm onSubmit={handleCreate} onCancel={() => { setView('list'); setServerError(null); }} isSubmitting={submitting} serverError={serverError} />);
  }
  if (view === 'edit' && selectedAgent) {
    return formCard('Edit Agent', <AgentForm isEditMode
      initialValues={{ agent_id: selectedAgent.agent_id, email: selectedAgent.email, display_name: selectedAgent.display_name ?? '', phone: selectedAgent.phone ?? '', company_id: selectedAgent.company_id }}
      onSubmit={handleEdit} onCancel={() => { setView('list'); setSelectedAgent(null); setServerError(null); }}
      isSubmitting={submitting} serverError={serverError} />);
  }

  if (loading) return <div className={styles.loadingContainer} style={{ color: t.textFaint }}>Loading…</div>;
  if (error) return <div className={styles.errorContainer} style={{ color: t.red }}>{error}</div>;

  const totalPages = Math.max(1, Math.ceil(agents.length / PAGE_SIZE));
  const pagedAgents = agents.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span style={{ color: t.text }} className={styles.title}>
          Agents <span className={styles.titleCount} style={{ color: t.textMuted }}>({agents.length})</span>
        </span>
        <button onClick={() => { setServerError(null); setView('create'); }} style={t.btnPrimary}>Create Agent</button>
      </div>

      {serverError && (
        <div className={styles.errorAlert} style={{ background: t.redBg, border: `1px solid ${t.red}30` }}>
          <span style={{ color: t.red }}>{serverError}</span>
          <button onClick={() => setServerError(null)} className={styles.errorAlertCloseButton} style={{ color: t.red }}>×</button>
        </div>
      )}

      {agents.length === 0 ? (
        <div style={t.card} className={styles.emptyState}>
          <div className={styles.emptyStateTitle} style={{ color: t.textFaint }}>No agents configured</div>
          <div className={styles.emptyStateSubtitle} style={{ color: t.textFaint }}>Create your first agent to start monitoring Gmail accounts</div>
        </div>
      ) : (
        <>
          <div style={t.card}>
            <table className={styles.table}>
              <thead>
                <tr>
                  {['Agent ID', 'Email', 'Company', 'Status', 'Created', 'Actions'].map(h => (
                    <th key={h} style={{ ...t.th, textAlign: h === 'Actions' ? 'right' : 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pagedAgents.map((agent, i) => {
                  const sc = statusStyle(agent.watcher_status);
                  return (
                    <tr key={agent.id} style={{ borderBottom: i < pagedAgents.length - 1 ? `1px solid ${t.border}` : 'none' }}>
                      <td style={{ ...t.td, fontWeight: 600 }}>{agent.agent_id}</td>
                      <td style={{ ...t.td, color: t.textSecondary }}>{agent.email}</td>
                      <td style={{ ...t.td, color: t.textMuted }}>{agent.company_name || '—'}</td>
                      <td style={t.td}>
                        <span className={styles.statusBadge} style={{ color: sc.color, background: sc.bg }}>
                          {agent.watcher_status === 'cancelled' ? 'Cancelled' : agent.watcher_status || 'Not Started'}
                        </span>
                      </td>
                      <td style={{ ...t.td, color: t.textMuted }}>{new Date(agent.created_at).toLocaleDateString()}</td>
                      <td style={{ ...t.td, textAlign: 'right' }}>
                        <button onClick={() => { setSelectedAgent(agent); setView('detail'); }}
                          className={styles.actionButton} style={t.btnSecondary}>View</button>
                        <button onClick={() => { setSelectedAgent(agent); setServerError(null); setView('edit'); }}
                          className={styles.actionButton} style={t.btnSecondary}>Edit</button>
                        <button onClick={() => setDeleteTarget(agent)}
                          className={styles.actionButtonLast} style={t.btnDanger}>Delete</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className={styles.paginationContainer}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>Previous</button>
              <span className={styles.paginationText} style={{ color: t.textMuted }}>Page {page} of {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                style={{ ...t.btnSecondary, opacity: page === totalPages ? 0.4 : 1 }}>Next</button>
            </div>
          )}
        </>
      )}

      <ConfirmDialog isOpen={deleteTarget !== null} title="Delete Agent"
        message={`Delete agent "${deleteTarget?.agent_id}"? This cannot be undone.`}
        confirmLabel="Delete" isDangerous onConfirm={handleDeleteConfirm} onCancel={() => setDeleteTarget(null)} />
    </div>
  );
};
