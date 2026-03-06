import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';
import { useT } from '../../utils/useT';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface ScoringRule { key: string; answer_value: string; points: number; reason: string; }
interface Thresholds { HOT: number; WARM: number; }
interface ScoringVersion { id: number; version_number: number; is_active: boolean; published_at: string | null; rules_json: string; thresholds_json: string; }
interface ScoringConfig { id: number; name: string; intent_type: string; }

export const BuyerScoringTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { success, error: toastError } = useToast();
  const t = useT();

  const [configs, setConfigs] = useState<ScoringConfig[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<ScoringConfig | null>(null);
  const [versions, setVersions] = useState<ScoringVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [editingConfigId, setEditingConfigId] = useState<number | null>(null);
  const [editConfigName, setEditConfigName] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newConfigName, setNewConfigName] = useState('');
  const [creating, setCreating] = useState(false);
  const [rules, setRules] = useState<ScoringRule[]>([]);
  const [thresholds, setThresholds] = useState<Thresholds>({ HOT: 80, WARM: 50 });

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<ScoringConfig[]>(`${API}/buyer-leads/tenants/${tenantId}/scoring`);
      setConfigs(res.data);
      if (res.data.length > 0) await loadConfig(res.data[0]);
    } catch { toastError('Failed to load scoring configs'); } finally { setLoading(false); }
  }, [tenantId]);

  useEffect(() => { fetchConfigs(); }, [fetchConfigs]);

  const loadConfig = async (config: ScoringConfig) => {
    setSelectedConfig(config);
    try {
      const res = await axios.get<ScoringVersion[]>(`${API}/buyer-leads/tenants/${tenantId}/scoring/${config.id}/versions`);
      setVersions(res.data);
      const active = res.data.find((v) => v.is_active);
      if (active) {
        setRules(JSON.parse(active.rules_json) as ScoringRule[]);
        setThresholds(JSON.parse(active.thresholds_json) as Thresholds);
      } else { setRules([]); setThresholds({ HOT: 80, WARM: 50 }); }
    } catch { toastError('Failed to load scoring versions'); }
  };

  const handleCreate = async () => {
    if (!newConfigName.trim()) return;
    setCreating(true);
    try {
      const res = await axios.post<ScoringConfig>(`${API}/buyer-leads/tenants/${tenantId}/scoring`, { name: newConfigName.trim(), intent_type: 'BUY' });
      success('Scoring config created'); setNewConfigName(''); setShowCreate(false);
      await fetchConfigs(); await loadConfig(res.data);
    } catch { toastError('Failed to create scoring config'); } finally { setCreating(false); }
  };

  const handleRename = async (config: ScoringConfig) => {
    if (!editConfigName.trim() || editConfigName === config.name) { setEditingConfigId(null); return; }
    try {
      await axios.put(`${API}/buyer-leads/tenants/${tenantId}/scoring/${config.id}`, { name: editConfigName.trim(), intent_type: config.intent_type });
      success('Renamed'); setEditingConfigId(null); fetchConfigs();
    } catch { toastError('Rename failed'); }
  };

  const handleDelete = async (config: ScoringConfig) => {
    if (!confirm(`Delete scoring config "${config.name}"?`)) return;
    try {
      await axios.delete(`${API}/buyer-leads/tenants/${tenantId}/scoring/${config.id}`);
      success('Deleted'); setSelectedConfig(null); setVersions([]); setRules([]); fetchConfigs();
    } catch { toastError('Delete failed'); }
  };

  const handleRollback = async (vid: number) => {
    if (!selectedConfig) return;
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/scoring/${selectedConfig.id}/versions/${vid}/rollback`);
      success('Rolled back'); loadConfig(selectedConfig);
    } catch { toastError('Rollback failed'); }
  };

  const handlePublish = async () => {
    if (!selectedConfig) return;
    setPublishing(true);
    try {
      await axios.post(`${API}/buyer-leads/tenants/${tenantId}/scoring/${selectedConfig.id}/versions`, { rules, thresholds });
      success('Scoring version published'); loadConfig(selectedConfig);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toastError(msg || 'Failed to publish scoring version');
    } finally { setPublishing(false); }
  };

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>Loading…</div>;

  const inputSm: React.CSSProperties = { ...t.input, padding: '5px 8px', fontSize: 12 };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>Buyer Scoring</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setShowCreate(true)} style={t.btnSecondary}>New Config</button>
          <button onClick={handlePublish} disabled={publishing || !selectedConfig} style={{ ...t.btnPrimary, opacity: publishing || !selectedConfig ? 0.5 : 1 }}>
            {publishing ? 'Publishing…' : 'Publish Version'}
          </button>
        </div>
      </div>

      {showCreate && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ ...t.card, width: '100%', maxWidth: 440, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: t.text, margin: 0 }}>New Scoring Config</h3>
            <input type="text" placeholder="Config name" value={newConfigName} onChange={(e) => setNewConfigName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()} style={t.input} autoFocus />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowCreate(false)} style={t.btnSecondary}>Cancel</button>
              <button onClick={handleCreate} disabled={creating || !newConfigName.trim()} style={{ ...t.btnPrimary, opacity: creating || !newConfigName.trim() ? 0.5 : 1 }}>
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {configs.length > 0 && (
        <div style={t.card}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Config', 'Type', ''].map(h => <th key={h} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {configs.map((c) => (
                <tr key={c.id} onClick={() => { if (editingConfigId !== c.id) loadConfig(c); }}
                  style={{ borderBottom: `1px solid ${t.border}`, cursor: 'pointer', background: selectedConfig?.id === c.id ? t.accentBg : 'transparent' }}>
                  <td style={{ ...t.td, fontWeight: 500 }}>
                    {editingConfigId === c.id ? (
                      <input type="text" value={editConfigName} autoFocus onChange={(e) => setEditConfigName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleRename(c); if (e.key === 'Escape') setEditingConfigId(null); }}
                        onClick={(e) => e.stopPropagation()} style={{ ...t.input, width: 'auto' }} />
                    ) : c.name}
                  </td>
                  <td style={{ ...t.td, color: t.textMuted }}>{c.intent_type}</td>
                  <td style={{ ...t.td, textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10 }}>
                      {editingConfigId === c.id ? (
                        <>
                          <button onClick={(e) => { e.stopPropagation(); handleRename(c); }} style={{ color: t.green, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>Save</button>
                          <button onClick={(e) => { e.stopPropagation(); setEditingConfigId(null); }} style={{ color: t.textMuted, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Cancel</button>
                        </>
                      ) : (
                        <>
                          <button onClick={(e) => { e.stopPropagation(); setEditingConfigId(c.id); setEditConfigName(c.name); }} style={{ color: t.textMuted, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Rename</button>
                          <button onClick={(e) => { e.stopPropagation(); handleDelete(c); }} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>Delete</button>
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
          <div style={t.card}>
            <div style={t.sectionTitle}>Bucket Thresholds</div>
            <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end' }}>
              {(['HOT', 'WARM'] as const).map((bucket) => (
                <div key={bucket}>
                  <label style={t.labelStyle}>{bucket} (≥)</label>
                  <input type="number" value={thresholds[bucket]}
                    onChange={(e) => setThresholds((th) => ({ ...th, [bucket]: Number(e.target.value) }))}
                    style={{ ...t.input, width: 80 }} />
                </div>
              ))}
              <span style={{ fontSize: 12, color: t.textFaint, paddingBottom: 8 }}>NURTURE = below WARM</span>
            </div>
          </div>

          {/* Rules table */}
          <div style={t.card}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={t.sectionTitle}>Scoring Rules</div>
              <button onClick={() => setRules(rs => [...rs, { key: '', answer_value: '', points: 0, reason: '' }])} style={t.btnSecondary}>+ Add Rule</button>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr>
                {['Question Key', 'Answer Value', 'Points', 'Reason', ''].map(h => <th key={h} style={t.th}>{h}</th>)}
              </tr></thead>
              <tbody>
                {rules.length === 0 && (
                  <tr><td colSpan={5} style={{ ...t.td, textAlign: 'center', color: t.textFaint, padding: '24px 0' }}>No rules yet — click + Add Rule</td></tr>
                )}
                {rules.map((rule, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${t.border}` }}>
                    <td style={t.td}><input type="text" value={rule.key} onChange={(e) => setRules(rs => rs.map((r, j) => j === i ? { ...r, key: e.target.value } : r))} style={inputSm} /></td>
                    <td style={t.td}><input type="text" value={rule.answer_value} onChange={(e) => setRules(rs => rs.map((r, j) => j === i ? { ...r, answer_value: e.target.value } : r))} style={inputSm} /></td>
                    <td style={t.td}><input type="number" value={rule.points} onChange={(e) => setRules(rs => rs.map((r, j) => j === i ? { ...r, points: Number(e.target.value) } : r))} style={{ ...inputSm, width: 64 }} /></td>
                    <td style={t.td}><input type="text" value={rule.reason} onChange={(e) => setRules(rs => rs.map((r, j) => j === i ? { ...r, reason: e.target.value } : r))} style={inputSm} /></td>
                    <td style={{ ...t.td, textAlign: 'right' }}><button onClick={() => setRules(rs => rs.filter((_, j) => j !== i))} style={{ color: t.red, background: 'none', border: 'none', cursor: 'pointer', fontSize: 14 }}>✕</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Version history */}
          {versions.length > 0 && (
            <div style={t.card}>
              <div style={{ ...t.sectionTitle, marginBottom: 12 }}>Version History</div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>
                  {['Version', 'Published', 'Active', ''].map(h => <th key={h} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left' }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.id} style={{ borderBottom: `1px solid ${t.border}` }}>
                      <td style={t.td}>v{v.version_number}</td>
                      <td style={{ ...t.td, color: t.textMuted }}>{v.published_at ? new Date(v.published_at).toLocaleDateString() : '—'}</td>
                      <td style={t.td}>{v.is_active && <span style={{ padding: '2px 8px', fontSize: 10, fontWeight: 600, background: t.greenBg, color: t.green, borderRadius: 20 }}>Active</span>}</td>
                      <td style={{ ...t.td, textAlign: 'right' }}>
                        {!v.is_active && <button onClick={() => handleRollback(v.id)} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>Rollback</button>}
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
