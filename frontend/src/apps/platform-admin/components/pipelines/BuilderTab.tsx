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
  usePipelineStages, useReorderStages, useCreateStage,
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
                  <SortableStage stage={stage} onClick={() => setDrawerStage(stage)} />
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

// ── Sortable stage pill ───────────────────────────────────────────────────

const SortableStage: React.FC<{ stage: PipelineStage; onClick: () => void }> = ({ stage, onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: stage.id });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        flexShrink: 0,
      }}
      {...attributes}
      {...listeners}
    >
      <button
        onClick={onClick}
        style={{
          background: stage.color + '22',
          border: `1.5px solid ${stage.color}`,
          borderRadius: 12, padding: '10px 18px', cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4,
          minWidth: 120, transition: 'all 0.15s',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: stage.color, flexShrink: 0 }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{stage.name}</span>
          {stage.is_default && (
            <span style={{ fontSize: 9, fontWeight: 700, color: t.accent, background: t.accentBg, padding: '1px 5px', borderRadius: 6 }}>DEFAULT</span>
          )}
        </div>
        <div style={{ fontSize: 10, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
          {stage.category}{stage.is_closed_won ? ' · Won' : stage.is_closed_lost ? ' · Lost' : ''}
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
    onAdd({ name: name.trim(), key: slugify(name), color, category: 'active', position: nextPosition });
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
