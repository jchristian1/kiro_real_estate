/**
 * BuyerScoringTab — scoring configs, inline rules editor, thresholds, version history.
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
      if (res.data.length > 0) selectConfig(res.data[0]);
    } catch {
      toastError('Failed to load scoring configs');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchConfigs(); }, [fetchConfigs]);

  const selectConfig = async (config: ScoringConfig) => {
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
      }
    } catch {
      toastError('Failed to load scoring versions');
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
      selectConfig(selectedConfig);
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
        <button
          onClick={handlePublish}
          disabled={publishing || !selectedConfig}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
        >
          {publishing ? 'Publishing…' : 'Publish Version'}
        </button>
      </div>

      {/* Config selector */}
      {configs.length > 1 && (
        <div className="flex gap-2">
          {configs.map((c) => (
            <button
              key={c.id}
              onClick={() => selectConfig(c)}
              className={`px-3 py-1.5 text-sm rounded-md border ${
                selectedConfig?.id === c.id
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'border-gray-300 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

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
            {rules.map((rule, i) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="px-4 py-2">
                  <input
                    type="text"
                    value={rule.key}
                    onChange={(e) => updateRule(i, { key: e.target.value })}
                    className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-4 py-2">
                  <input
                    type="text"
                    value={rule.answer_value}
                    onChange={(e) => updateRule(i, { answer_value: e.target.value })}
                    className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-4 py-2">
                  <input
                    type="number"
                    value={rule.points}
                    onChange={(e) => updateRule(i, { points: Number(e.target.value) })}
                    className="w-20 px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-4 py-2">
                  <input
                    type="text"
                    value={rule.reason}
                    onChange={(e) => updateRule(i, { reason: e.target.value })}
                    className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
