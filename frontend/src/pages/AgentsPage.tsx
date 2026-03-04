import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { AgentForm, AgentFormValues, AgentEditFormValues } from '../components/AgentForm';
import { AgentDetail } from '../components/AgentDetail';
import { ConfirmDialog } from '../components/ConfirmDialog';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface Agent {
  id: number;
  agent_id: string;
  email: string;
  display_name: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
  watcher_status: string | null;
}

type View = 'list' | 'create' | 'edit' | 'detail';

export const AgentsPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>('list');
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Agent | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const [agentsRes, watchersRes] = await Promise.all([
        axios.get<{ agents: Agent[] }>(`${API_BASE_URL}/agents`),
        axios.get<{ watchers: { agent_id: string; status: string }[] }>(`${API_BASE_URL}/watchers/status`).catch(() => ({ data: { watchers: [] } })),
      ]);
      const statusMap: Record<string, string> = {};
      for (const w of watchersRes.data.watchers) {
        statusMap[w.agent_id] = w.status;
      }
      setAgents(agentsRes.data.agents.map(a => ({
        ...a,
        watcher_status: statusMap[a.agent_id] ?? a.watcher_status,
      })));
      setError(null);
    } catch {
      setError('Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
    const interval = setInterval(fetchAgents, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleCreate = async (data: AgentFormValues | AgentEditFormValues) => {
    setSubmitting(true);
    setServerError(null);
    try {
      await axios.post(`${API_BASE_URL}/agents`, data);
      await fetchAgents();
      setView('list');
    } catch (err) {
      const e = err as AxiosError<{ message?: string }>;
      setServerError(e.response?.data?.message || 'Failed to create agent');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = async (data: AgentFormValues | AgentEditFormValues) => {
    if (!selectedAgent) return;
    setSubmitting(true);
    setServerError(null);
    try {
      await axios.put(`${API_BASE_URL}/agents/${selectedAgent.agent_id}`, data);
      await fetchAgents();
      setView('list');
      setSelectedAgent(null);
    } catch (err) {
      const e = err as AxiosError<{ message?: string }>;
      setServerError(e.response?.data?.message || 'Failed to update agent');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API_BASE_URL}/agents/${deleteTarget.agent_id}`);
      setAgents((prev) => prev.filter((a) => a.agent_id !== deleteTarget.agent_id));
    } catch {
      // silently fail — could add toast here
    } finally {
      setDeleteTarget(null);
    }
  };

  const getStatusColor = (status: string | null) => {
    switch (status?.toLowerCase()) {
      case 'running': return 'bg-green-100 text-green-800';
      case 'stopped': return 'bg-gray-100 text-gray-800';
      case 'failed':  return 'bg-red-100 text-red-800';
      default:        return 'bg-gray-100 text-gray-800';
    }
  };

  // --- View: Detail ---
  if (view === 'detail' && selectedAgent) {
    return (
      <AgentDetail
        agentId={selectedAgent.agent_id}
        onBack={() => { setView('list'); setSelectedAgent(null); }}
      />
    );
  }

  // --- View: Create ---
  if (view === 'create') {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-800">Create Agent</h1>
        <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
          <AgentForm
            onSubmit={handleCreate}
            onCancel={() => { setView('list'); setServerError(null); }}
            isSubmitting={submitting}
            serverError={serverError}
          />
        </div>
      </div>
    );
  }

  // --- View: Edit ---
  if (view === 'edit' && selectedAgent) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-800">Edit Agent</h1>
        <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
          <AgentForm
            isEditMode
            initialValues={{ agent_id: selectedAgent.agent_id, email: selectedAgent.email, display_name: selectedAgent.display_name ?? '', phone: selectedAgent.phone ?? '' }}
            onSubmit={handleEdit}
            onCancel={() => { setView('list'); setSelectedAgent(null); setServerError(null); }}
            isSubmitting={submitting}
            serverError={serverError}
          />
        </div>
      </div>
    );
  }

  // --- View: List ---
  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-600">Loading agents...</div></div>;
  if (error)   return <div className="flex items-center justify-center h-64"><div className="text-red-600">{error}</div></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Agents</h1>
        <button
          onClick={() => { setServerError(null); setView('create'); }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md transition-colors"
        >
          Create Agent
        </button>
      </div>

      {agents.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="text-gray-500 mb-4">No agents configured</div>
          <div className="text-sm text-gray-400">Create your first agent to start monitoring Gmail accounts</div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Agent ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {agents.map((agent) => (
                <tr key={agent.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{agent.agent_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{agent.email}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(agent.watcher_status)}`}>
                      {agent.watcher_status || 'Not Started'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{new Date(agent.created_at).toLocaleDateString()}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                    <button className="text-blue-600 hover:text-blue-900" onClick={() => { setSelectedAgent(agent); setView('detail'); }}>View / Watcher</button>
                    <button className="text-gray-600 hover:text-gray-900" onClick={() => { setSelectedAgent(agent); setServerError(null); setView('edit'); }}>Edit</button>
                    <button className="text-red-600 hover:text-red-900" onClick={() => setDeleteTarget(agent)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Delete Agent"
        message={`Are you sure you want to delete agent "${deleteTarget?.agent_id}"? This action cannot be undone.`}
        confirmLabel="Delete"
        isDangerous
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
};
