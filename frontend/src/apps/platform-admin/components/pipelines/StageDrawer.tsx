/**
 * StageDrawer — side drawer for editing a pipeline stage.
 * Requirements: 9.4, 2.10
 */

import React, { useState, useEffect } from 'react';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { useUpdateStage, useDeleteStage } from '../../hooks/usePipelineQueries';
import type { PipelineStage, StageCategory } from '../../api/pipelinesApi';

interface Props {
  stage: PipelineStage;
  pipelineId: number;
  stages: PipelineStage[];
  onClose: () => void;
}

const COLORS = ['#6366f1', '#34d399', '#f87171', '#fb923c', '#fbbf24', '#60a5fa', '#a78bfa', '#f472b6', '#2dd4bf', '#e879f9'];
const CATEGORIES: StageCategory[] = ['active', 'won', 'lost', 'nurture'];

export const StageDrawer: React.FC<Props> = ({ stage, pipelineId, stages, onClose }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const updateStage = useUpdateStage();
  const deleteStage = useDeleteStage();

  const [name, setName] = useState(stage.name);
  const [key, setKey] = useState(stage.key);
  const [color, setColor] = useState(stage.color);
  const [category, setCategory] = useState<StageCategory>(stage.category);
  const [isDefault, setIsDefault] = useState(stage.is_default);
  const [isClosedWon, setIsClosedWon] = useState(stage.is_closed_won);
  const [isClosedLost, setIsClosedLost] = useState(stage.is_closed_lost);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [reassignTo, setReassignTo] = useState<number | ''>('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Auto-slugify name → key
  useEffect(() => {
    setKey(name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''));
  }, [name]);

  const handleSave = async () => {
    await updateStage.mutateAsync({
      pipelineId, stageId: stage.id,
      name, key, color, category,
      is_default: isDefault,
      is_closed_won: isClosedWon,
      is_closed_lost: isClosedLost,
    });
    onClose();
  };

  const handleDelete = async () => {
    setDeleteError(null);
    try {
      await deleteStage.mutateAsync({
        pipelineId, stageId: stage.id,
        reassignTo: reassignTo ? Number(reassignTo) : undefined,
      });
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setDeleteError(msg || 'Failed to delete stage.');
    }
  };

  const otherStages = stages.filter(s => s.id !== stage.id);

  const inputStyle: React.CSSProperties = {
    background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
    color: t.text, fontSize: 13, padding: '8px 12px', width: '100%', boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: t.textFaint,
    textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6, display: 'block',
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, zIndex: 900, background: 'rgba(0,0,0,0.3)' }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 901,
        width: 360, background: theme === 'dark' ? '#16161e' : '#fff',
        border: `1px solid ${t.border}`, borderRight: 'none',
        boxShadow: '-8px 0 32px rgba(0,0,0,0.2)',
        display: 'flex', flexDirection: 'column',
        overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{ padding: '20px 20px 16px', borderBottom: `1px solid ${t.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: t.text }}>Edit Stage</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textMuted, fontSize: 20, lineHeight: 1 }}>×</button>
        </div>

        {/* Form */}
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 18, flex: 1 }}>
          <div>
            <label style={labelStyle}>Name</label>
            <input value={name} onChange={e => setName(e.target.value)} style={inputStyle} />
          </div>

          <div>
            <label style={labelStyle}>Key (auto-generated)</label>
            <input value={key} onChange={e => setKey(e.target.value)} style={{ ...inputStyle, color: t.textMuted }} />
          </div>

          <div>
            <label style={labelStyle}>Color</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {COLORS.map(c => (
                <button
                  key={c} type="button" onClick={() => setColor(c)}
                  style={{
                    width: 26, height: 26, borderRadius: '50%', background: c, border: 'none',
                    cursor: 'pointer', outline: color === c ? `2.5px solid ${t.text}` : 'none',
                    outlineOffset: 2,
                  }}
                />
              ))}
              <input
                type="color" value={color} onChange={e => setColor(e.target.value)}
                style={{ width: 26, height: 26, borderRadius: '50%', border: 'none', cursor: 'pointer', padding: 0 }}
              />
            </div>
          </div>

          <div>
            <label style={labelStyle}>Category</label>
            <select value={category} onChange={e => setCategory(e.target.value as StageCategory)} style={inputStyle}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { label: 'Default stage (new leads start here)', val: isDefault, set: setIsDefault },
              { label: 'Closed Won', val: isClosedWon, set: (v: boolean) => { setIsClosedWon(v); if (v) setIsClosedLost(false); } },
              { label: 'Closed Lost', val: isClosedLost, set: (v: boolean) => { setIsClosedLost(v); if (v) setIsClosedWon(false); } },
            ].map(({ label, val, set }) => (
              <label key={label} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                <input type="checkbox" checked={val} onChange={e => set(e.target.checked)} style={{ width: 16, height: 16, cursor: 'pointer' }} />
                <span style={{ fontSize: 13, color: t.text }}>{label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 20px', borderTop: `1px solid ${t.border}`, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={handleSave}
              disabled={updateStage.isPending}
              style={{
                flex: 1, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                border: 'none', borderRadius: 9, color: '#fff',
                fontSize: 13, fontWeight: 600, padding: '10px', cursor: 'pointer',
              }}
            >
              {updateStage.isPending ? 'Saving…' : 'Save Changes'}
            </button>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              style={{
                background: t.redBg, border: `1px solid ${t.red}`, borderRadius: 9,
                color: t.red, fontSize: 13, fontWeight: 600, padding: '10px 16px', cursor: 'pointer',
              }}
            >
              Delete
            </button>
          </div>

          {/* Delete confirmation */}
          {showDeleteConfirm && (
            <div style={{ background: t.redBg, border: `1px solid ${t.red}`, borderRadius: 10, padding: '14px' }}>
              <div style={{ fontSize: 13, color: t.text, marginBottom: 10 }}>
                Delete this stage? Leads in this stage will need to be reassigned.
              </div>
              {otherStages.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <label style={{ ...labelStyle, color: t.textMuted }}>Reassign leads to</label>
                  <select value={reassignTo} onChange={e => setReassignTo(e.target.value ? Number(e.target.value) : '')} style={inputStyle}>
                    <option value="">— none (fail if leads exist) —</option>
                    {otherStages.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
              )}
              {deleteError && <div style={{ fontSize: 12, color: t.red, marginBottom: 8 }}>{deleteError}</div>}
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={handleDelete} disabled={deleteStage.isPending} style={{ flex: 1, background: t.red, border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600, padding: '8px', cursor: 'pointer' }}>
                  {deleteStage.isPending ? 'Deleting…' : 'Confirm Delete'}
                </button>
                <button onClick={() => { setShowDeleteConfirm(false); setDeleteError(null); }} style={{ background: 'none', border: `1px solid ${t.border}`, borderRadius: 8, color: t.textMuted, fontSize: 13, padding: '8px 12px', cursor: 'pointer' }}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
