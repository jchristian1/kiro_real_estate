/**
 * BuyerScoringTab — scoring configs with rename/delete, inline rules editor, thresholds, version history with rollback.
 * Requirements: 12.1, 12.2, 12.3, 12.4
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface ScoringRule {
  key: string;
  answer_value: string;
  points: number;
  reason: string;
}

interface Thresholds { HOT: number; WARM: number; }

interface ScoringVersion {
  id: number;
  version_number: number;
  is_active: boolean;
  published_at: string | null;
  rules_json: string;
  thresholds_json: string;
}

interface ScoringConfig {
  id: number;
  name: string;
  intent_type: string;
}

export const BuyerScoringTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { success, error: toastError } = useToast();

  const [configs, setConfigs] = useState<ScoringConfig[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<ScoringConfig | null>(null);
  const [versions, setVersions] = useState<ScoringVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);

  // Rename state
  const [editingConfigId, setEditingConfigId] = useState<number | null>(null);
  const [editConfigName, setEditConfigName] = useState('');

  // Create new config
  const [showCreate, setShowCreate] = useState(false);
  const [newConfigName, setNewConfigName] = useState('');
  const [creating, setCreating] = useState(false);

  // Editor state (draft for new version)
  const [rules, setRules] = useState<ScoringRule[]>([]);
  const [thresholds, setThresholds] = useState<Thresholds>({ HOT: 80, WARM: 50 });

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<ScoringConfig[]>(
        `${API}/buyer-leads/tenants/${tenantId}/scoring`
      );
      setConfigs(res.data);
      if (res.data.length > 0) await loadConfig(res.data[0]);
    } catch {
      toastError('Failed to load scoring configs');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchConfigs(); }, [fetchConfigs]);

  const loadConfig = async (config: ScoringConfig) => {
    setSelectedConfig(config);
    try {
      const res = await axios.get<ScoringVersion[]>(
        `${API}/buyer-leads/tenants/${tenantId}/scoring/${config.id}/versions`
      );
      setVersions(res.data);
      const active = res.data.find((v) => v.is_active);
      if (active) {
        setRules(JSON.parse(active.rules_json) as ScoringRule[]);
        setThresholds(JSON.parse(active.thresholds_json) as Thresholds);
      } else {
        setRules([]);
        setThresholds({ HOT: 80, WARM: 50 });
      }
    } catch {
      toastError('Failed to load scoring versions');
    }
  };

  const handleCreate = async () => {
    if (!newConfigName.trim()) return;
    setCreating(true);
    try {
      const res = await axios.post<ScoringConfig>(
        `${API}/buyer-leads/tenants/${tenantId}/scoring`,
        { name: newConfigName.trim(), intent_type: 'BUY' }
      );
      success('Scoring config created');
      setNewConfigName('');
      setShowCreate(false);
      await fetchConfigs();
      await loadConfig(res.data);
    } catch {
      toastError('Failed to create scoring config');
    } finally {
      setCreating(false);
    }
  };

  const handleRename = async (config: ScoringConfig) => {
    if (!editConfigName.trim() || editConfigName === config.name) { setEditingConfigId(null); return; }
    try {
      await axios.put(
        `${API}/buyer-leads/tenants/${tenantId}/scoring/${config.id}`,
        { name: editConfigName.trim(), intent_type: config.intent_type }
      );
      success('Renamed');
      setEditingConfigId(null);
      fetchConfigs();
    } catch {
      toastError('Rename failed');
    }
  };

  const handleDelete = async (config: ScoringConfig) => {
    if (!confirm(`Delete scoring config "${config.name}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API}/buyer-leads/tenants/${tenantId}/scoring/${config.id}`);
      success('Deleted');
      setSelectedConfig(null);
      setVersions([]);
      setRules([]);
      fetchConfigs();
    } catch {
      toastError('Delete failed');
    }
  };

  const handleRollback = async (vid: number) => {
    if (!selectedConfig) return;
    try {
      await axios.post(
        `${API}/buyer-leads/tenants/${tenantId}/scoring/${selectedConfig.id}/versions/${vid}/rollback`
      );
      success('Rolled back');
      loadConfig(selectedConfig);
    } catch {
      toastError('Rollback failed');
    }
  };

  const addRule = () => {
    setRules((rs) => [...rs, { key: '', answer_value: '', points: 0, reason: '' }]);
  };

  const updateRule = (index: number, patch: Partial<ScoringRule>) => {
    setRules((rs) => rs.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  };

  const removeRule = (index: number) => {
    setRules((rs) => rs.filter((_, i) => i !== index));
  };

  const handlePublish = async () => {
    if (!selectedConfig) return;
    setPublishing(true);
    try {
      await axios.post(
        `${API}/buyer-leads/tenants/${tenantId}/scoring/${selectedConfig.id}/versions`,
        { rules, thresholds }
      );
      success('Scoring version published');
      loadConfig(selectedConfig);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Failed to publish scoring version');
    } finally {
      setPublishing(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-700">Buyer Scoring</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-md"
          >
            New Config
          </button>
          <button
            onClick={handlePublish}
            disabled={publishing || !selectedConfig}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
          >
            {publishing ? 'Publishing…' : 'Publish Version'}
          </button>
        </div>
      </div>

      {/* Create config modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-lg font-semibold">New Scoring Config</h3>
            <input
              type="text"
              placeholder="Config name"
              value={newConfigName}
              onChange={(e) => setNewConfigName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
              <button
                onClick={handleCreate}
                disabled={creating || !newConfigName.trim()}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
              >
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Config selector */}
      {configs.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Config</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {configs.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => { if (editingConfigId !== c.id) loadConfig(c); }}
                  className={`cursor-pointer hover:bg-gray-50 ${selectedConfig?.id === c.id ? 'bg-blue-50' : ''}`}
                >
                  <td className="px-4 py-2 text-sm font-medium text-gray-900">
                    {editingConfigId === c.id ? (
                      <input
                        type="text"
                        value={editConfigName}
                        autoFocus
                        onChange={(e) => setEditConfigName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRename(c);
                          if (e.key === 'Escape') setEditingConfigId(null);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full px-2 py-1 border border-blue-400 rounded text-sm focus:outline-none"
                      />
                    ) : c.name}
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">{c.intent_type}</td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {editingConfigId === c.id ? (
                        <>
                          <button onClick={(e) => { e.stopPropagation(); handleRename(c); }} className="text-green-600 hover:text-green-800 text-xs font-medium">Save</button>
                          <button onClick={(e) => { e.stopPropagation(); setEditingConfigId(null); }} className="text-gray-400 hover:text-gray-600 text-xs">Cancel</button>
                        </>
                      ) : (
                        <>
                          <button onClick={(e) => { e.stopPropagation(); setEditingConfigId(c.id); setEditConfigName(c.name); }} className="text-gray-500 hover:text-gray-700 text-xs">Rename</button>
                          <button onClick={(e) => { e.stopPropagation(); handleDelete(c); }} className="text-red-400 hover:text-red-600 text-xs">Delete</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedConfig && (
        <>
          {/* Thresholds */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Bucket Thresholds</h3>
            <div className="flex gap-6">
              <div>
                <label className="block text-xs text-gray-500 mb-1">HOT (≥)</label>
                <input
                  type="number"
                  value={thresholds.HOT}
                  onChange={(e) => setThresholds((t) => ({ ...t, HOT: Number(e.target.value) }))}
                  className="w-24 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">WARM (≥)</label>
                <input
                  type="number"
                  value={thresholds.WARM}
                  onChange={(e) => setThresholds((t) => ({ ...t, WARM: Number(e.target.value) }))}
                  className="w-24 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex items-end">
                <span className="text-xs text-gray-400">NURTURE = below WARM</span>
              </div>
            </div>
          </div>

          {/* Rules table */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Scoring Rules</h3>
              <button onClick={addRule} className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-md">
                + Add Rule
              </button>
            </div>
            <table className="min-w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Question Key</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Answer Value</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Points</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rules.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-400">No rules yet — click + Add Rule</td></tr>
                )}
                {rules.map((rule, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-2">
                      <input type="text" value={rule.key} onChange={(e) => updateRule(i, { key: e.target.value })}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </td>
                    <td className="px-4 py-2">
                      <input type="text" value={rule.answer_value} onChange={(e) => updateRule(i, { answer_value: e.target.value })}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </td>
                    <td className="px-4 py-2">
                      <input type="number" value={rule.points} onChange={(e) => updateRule(i, { points: Number(e.target.value) })}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </td>
                    <td className="px-4 py-2">
                      <input type="text" value={rule.reason} onChange={(e) => updateRule(i, { reason: e.target.value })}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button onClick={() => removeRule(i)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Version history */}
          {versions.length > 0 && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Version History</h3>
              </div>
              <table className="min-w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Version</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Published</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Active</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {versions.map((v) => (
                    <tr key={v.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-sm text-gray-900">v{v.version_number}</td>
                      <td className="px-4 py-2 text-sm text-gray-500">
                        {v.published_at ? new Date(v.published_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-2">
                        {v.is_active && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">Active</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {!v.is_active && (
                          <button onClick={() => handleRollback(v.id)} className="text-blue-600 hover:text-blue-800 text-xs">
                            Rollback
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
};
