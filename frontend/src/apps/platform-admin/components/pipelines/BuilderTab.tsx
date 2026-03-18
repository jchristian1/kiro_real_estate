/**
 * BuilderTab — horizontal stage flow with drag-and-drop reordering.
 * Uses @dnd-kit/core and @dnd-kit/sortable.
 * Requirements: 9.2, 9.3, 9.4
 */

import React, { useState } from 'react';
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext, horizontalListSortingStrategy,
  useSortable, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import {
  usePipelineStages, useReorderStages, useCreateStage, usePipelineRules,
} from '../../hooks/usePipelineQueries';
import { StageDrawer } from './StageDrawer.tsx';
import type { PipelineStage, PipelineStageCreate } from '../../api/pipelinesApi';

interface Props { pipelineId: number; }

export const BuilderTab: React.FC<Props> = ({ pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: stages = [], isLoading } = usePipelineStages(pipelineId);
  const reorderStages = useReorderStages();
  const createStage = useCreateStage();
  const { data: allRules = [] } = usePipelineRules(pipelineId);
  const [drawerStage, setDrawerStage] = useState<PipelineStage | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const sorted = [...stages].sort((a, b) => a.position - b.position);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = sorted.findIndex(s => s.id === active.id);
    const newIdx = sorted.findIndex(s => s.id === over.id);
    const reordered = arrayMove(sorted, oldIdx, newIdx);
    reorderStages.mutate({ pipelineId, orderedIds: reordered.map(s => s.id) });
  };

  const handleAddStage = async (data: PipelineStageCreate) => {
    await createStage.mutateAsync({ pipelineId, ...data });
    setShowAddForm(false);
  };

  if (isLoading) {
    return <div style={{ color: getTokens(theme).textFaint, fontSize: 14, padding: 24 }}>Loading stages…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* How-to guide */}
      {sorted.length === 0 && (
        <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '20px 24px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: t.text, marginBottom: 14 }}>How to set up your pipeline</div>
          <div style={{ display: 'flex', gap: 0, flexWrap: 'wrap' }}>
            {[
              { step: '1', icon: '🏗️', title: 'Add stages',       desc: 'Create the stages a lead moves through, e.g. New → Contacted → Won' },
              { step: '2', icon: '🔌', title: 'Map events',        desc: 'Go to Built-in Rules to auto-move leads when platform events fire' },
              { step: '3', icon: '⚡', title: 'Add automations',   desc: 'Go to Automations to trigger emails or actions when leads change stage' },
              { step: '4', icon: '✅', title: 'Activate',          desc: 'Click "Set Active" to make this the live pipeline for your company' },
            ].map((item, idx, arr) => (
              <div key={item.step} style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 160, padding: '0 8px' }}>
                  <div style={{ width: 36, height: 36, borderRadius: '50%', background: t.accentBg, border: `2px solid ${t.accent}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, marginBottom: 8 }}>
                    {item.icon}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: t.text, marginBottom: 4, textAlign: 'center' }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: t.textFaint, textAlign: 'center', lineHeight: 1.4 }}>{item.desc}</div>
                </div>
                {idx < arr.length - 1 && (
                  <div style={{ color: t.textFaint, fontSize: 20, paddingTop: 8, flexShrink: 0 }}>→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stage flow */}
      <div style={{
        background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16,
        padding: '24px 20px', overflowX: 'auto',
      }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: t.textMuted, marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Stage Flow — drag to reorder · click to edit
        </div>

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={sorted.map(s => s.id)} strategy={horizontalListSortingStrategy}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 0, minWidth: 'max-content' }}>
              {sorted.map((stage, idx) => (
                <React.Fragment key={stage.id}>
                  <SortableStage
                    stage={stage}
                    onClick={() => setDrawerStage(stage)}
                    ruleCount={allRules.filter(r => r.trigger_type === 'on_stage_enter' && r.trigger_stage_id === stage.id).length}
                  />
                  {idx < sorted.length - 1 && (
                    <div style={{ color: t.textFaint, fontSize: 16, padding: '0 4px', flexShrink: 0 }}>→</div>
                  )}
                </React.Fragment>
              ))}

              {/* Add stage button */}
              {sorted.length > 0 && (
                <div style={{ color: t.textFaint, fontSize: 16, padding: '0 4px', flexShrink: 0 }}>→</div>
              )}
              <button
                onClick={() => setShowAddForm(true)}
                style={{
                  background: t.bgCardHover, border: `1.5px dashed ${t.border}`,
                  borderRadius: 12, padding: '10px 18px', cursor: 'pointer',
                  color: t.textMuted, fontSize: 13, fontWeight: 500,
                  display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0,
                  transition: 'all 0.15s',
                }}
              >
                + Add Stage
              </button>
            </div>
          </SortableContext>
        </DndContext>

        {sorted.length === 0 && !showAddForm && (
          <div style={{ color: t.textFaint, fontSize: 13, padding: '12px 0' }}>
            No stages yet. Add your first stage to get started.
          </div>
        )}
      </div>

      {/* Quick add form */}
      {showAddForm && (
        <QuickAddStageForm
          nextPosition={sorted.length + 1}
          onAdd={handleAddStage}
          onCancel={() => setShowAddForm(false)}
          loading={createStage.isPending}
        />
      )}

      {/* Stage drawer */}
      {drawerStage && (
        <StageDrawer
          stage={drawerStage}
          pipelineId={pipelineId}
          stages={sorted}
          onClose={() => setDrawerStage(null)}
        />
      )}
    </div>
  );
};

// ── Sortable stage card ───────────────────────────────────────────────────

const SortableStage: React.FC<{ stage: PipelineStage; onClick: () => void; ruleCount: number }> = ({ stage, onClick, ruleCount }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const isDark = theme === 'dark';
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: stage.id });
  const [hovered, setHovered] = React.useState(false);

  const categoryLabel: Record<string, string> = {
    open: 'Open', in_progress: 'In Progress', waiting: 'Waiting', won: 'Won', lost: 'Lost',
  };

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1, flexShrink: 0 }}
      {...attributes}
      {...listeners}
    >
      <button
        onClick={onClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          background: hovered
            ? (isDark ? `${stage.color}18` : `${stage.color}12`)
            : (isDark ? 'rgba(255,255,255,0.04)' : '#ffffff'),
          border: `1.5px solid ${hovered ? stage.color + '88' : (isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.09)')}`,
          borderRadius: 14,
          padding: '14px 16px',
          cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10,
          minWidth: 148, maxWidth: 180,
          transition: 'all 0.18s',
          boxShadow: hovered
            ? `0 4px 20px ${stage.color}22, 0 0 0 1px ${stage.color}33`
            : (isDark ? '0 2px 8px rgba(0,0,0,0.3)' : '0 2px 8px rgba(0,0,0,0.06)'),
          textAlign: 'left',
        }}
      >
        {/* Top row: color dot + badges */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%', background: stage.color, flexShrink: 0,
            boxShadow: `0 0 8px ${stage.color}88`,
          }} />
          <div style={{ display: 'flex', gap: 4 }}>
            {stage.is_default && (
              <span style={{ fontSize: 9, fontWeight: 700, color: t.accent, background: t.accentBg, padding: '2px 6px', borderRadius: 6, letterSpacing: '0.3px' }}>DEFAULT</span>
            )}
            {stage.is_closed_won && (
              <span style={{ fontSize: 9, fontWeight: 700, color: t.green, background: t.greenBg, padding: '2px 6px', borderRadius: 6 }}>WON</span>
            )}
            {stage.is_closed_lost && (
              <span style={{ fontSize: 9, fontWeight: 700, color: t.red, background: t.redBg, padding: '2px 6px', borderRadius: 6 }}>LOST</span>
            )}
          </div>
        </div>

        {/* Stage name */}
        <div style={{ fontSize: 14, fontWeight: 700, color: t.text, letterSpacing: '-0.2px', lineHeight: 1.2 }}>
          {stage.name}
        </div>

        {/* Bottom row: category + action count */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <span style={{
            fontSize: 10, fontWeight: 600, color: t.textFaint,
            textTransform: 'uppercase', letterSpacing: '0.5px',
          }}>
            {categoryLabel[stage.category] ?? stage.category}
          </span>
          {ruleCount > 0 && (
            <span style={{
              fontSize: 10, fontWeight: 700,
              color: t.accent, background: t.accentBg,
              padding: '2px 7px', borderRadius: 20,
              letterSpacing: '0.2px',
            }}>
              {ruleCount} {ruleCount === 1 ? 'action' : 'actions'}
            </span>
          )}
        </div>
      </button>
    </div>
  );
};

// ── Quick add form ────────────────────────────────────────────────────────

const COLORS = ['#6366f1', '#34d399', '#f87171', '#fb923c', '#fbbf24', '#60a5fa', '#a78bfa', '#f472b6'];

const QuickAddStageForm: React.FC<{
  nextPosition: number;
  onAdd: (data: PipelineStageCreate) => void;
  onCancel: () => void;
  loading: boolean;
}> = ({ nextPosition, onAdd, onCancel, loading }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [name, setName] = useState('');
  const [color, setColor] = useState(COLORS[0]);

  const slugify = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onAdd({ name: name.trim(), key: slugify(name), color, category: 'open', position: nextPosition });
  };

  return (
    <form onSubmit={handleSubmit} style={{
      background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14,
      padding: '20px 20px', marginTop: 12, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
    }}>
      <input
        autoFocus
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Stage name"
        style={{
          background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 8,
          color: t.text, fontSize: 13, padding: '8px 12px', flex: 1, minWidth: 160,
        }}
      />
      <div style={{ display: 'flex', gap: 6 }}>
        {COLORS.map(c => (
          <button
            key={c} type="button" onClick={() => setColor(c)}
            style={{
              width: 22, height: 22, borderRadius: '50%', background: c, border: 'none',
              cursor: 'pointer', outline: color === c ? `2px solid ${t.text}` : 'none',
              outlineOffset: 2,
            }}
          />
        ))}
      </div>
      <button type="submit" disabled={!name.trim() || loading} style={{
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none',
        borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600,
        padding: '8px 16px', cursor: 'pointer',
      }}>
        {loading ? 'Adding…' : 'Add'}
      </button>
      <button type="button" onClick={onCancel} style={{
        background: 'none', border: `1px solid ${t.border}`, borderRadius: 8,
        color: t.textMuted, fontSize: 13, padding: '8px 14px', cursor: 'pointer',
      }}>
        Cancel
      </button>
    </form>
  );
};
