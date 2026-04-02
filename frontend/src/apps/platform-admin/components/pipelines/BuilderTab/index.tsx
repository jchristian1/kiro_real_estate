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
import { useTheme } from '@/shared/contexts';
import { getTokens } from '@/shared/utils';
import {
  usePipelineStages, useReorderStages, useCreateStage, usePipelineRules,
} from '@/apps/platform-admin/hooks/usePipelineQueries';
import { StageDrawer } from '../StageDrawer';
import type { PipelineStage, PipelineStageCreate } from '@/apps/platform-admin/api/pipelinesApi';
import styles from './index.module.css';

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
    return <div className={styles.loadingText} style={{ color: getTokens(theme).textFaint }}>Loading stages…</div>;
  }

  return (
    <div className={styles.container}>
      {/* How-to guide */}
      {sorted.length === 0 && (
        <div className={styles.guideBox} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
          <div className={styles.guideTitle} style={{ color: t.text }}>How to set up your pipeline</div>
          <div className={styles.guideSteps}>
            {[
              { step: '1', icon: '🏗️', title: 'Add stages', desc: 'Create the stages a lead moves through, e.g. New → Contacted → Won' },
              { step: '2', icon: '🔌', title: 'Map events', desc: 'Go to Built-in Rules to auto-move leads when platform events fire' },
              { step: '3', icon: '⚡', title: 'Add automations', desc: 'Go to Automations to trigger emails or actions when leads change stage' },
              { step: '4', icon: '✅', title: 'Activate', desc: 'Click "Set Active" to make this the live pipeline for your company' },
            ].map((item, idx, arr) => (
              <div key={item.step} className={styles.guideStepWrapper}>
                <div className={styles.guideStep}>
                  <div className={styles.guideStepIcon} style={{ background: t.accentBg, border: `2px solid ${t.accent}` }}>
                    {item.icon}
                  </div>
                  <div className={styles.guideStepTitle} style={{ color: t.text }}>{item.title}</div>
                  <div className={styles.guideStepDesc} style={{ color: t.textFaint }}>{item.desc}</div>
                </div>
                {idx < arr.length - 1 && (
                  <div className={styles.guideArrow} style={{ color: t.textFaint }}>→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stage flow */}
      <div className={styles.stageFlowBox} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
        <div className={styles.stageFlowLabel} style={{ color: t.textMuted }}>
          Stage Flow — drag to reorder · click to edit
        </div>

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={sorted.map(s => s.id)} strategy={horizontalListSortingStrategy}>
            <div className={styles.stageFlowRow}>
              {sorted.map((stage, idx) => (
                <React.Fragment key={stage.id}>
                  <SortableStage
                    stage={stage}
                    onClick={() => setDrawerStage(stage)}
                    ruleCount={allRules.filter(r => r.trigger_type === 'on_stage_enter' && r.trigger_stage_id === stage.id).length}
                  />
                  {idx < sorted.length - 1 && (
                    <div className={styles.stageArrow} style={{ color: t.textFaint }}>→</div>
                  )}
                </React.Fragment>
              ))}

              {/* Add stage button */}
              {sorted.length > 0 && (
                <div className={styles.stageArrow} style={{ color: t.textFaint }}>→</div>
              )}
              <button
                onClick={() => setShowAddForm(true)}
                className={styles.addStageBtn}
                style={{
                  background: t.bgCardHover, border: `1.5px dashed ${t.border}`,
                  color: t.textMuted,
                }}
              >
                + Add Stage
              </button>
            </div>
          </SortableContext>
        </DndContext>

        {sorted.length === 0 && !showAddForm && (
          <div className={styles.emptyStagesText} style={{ color: t.textFaint }}>
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
      className={styles.sortableOuter}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 }}
      {...attributes}
      {...listeners}
    >
      <button
        onClick={onClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className={styles.stageCard}
        style={{
          background: hovered
            ? (isDark ? `${stage.color}18` : `${stage.color}12`)
            : (isDark ? 'rgba(255,255,255,0.04)' : '#ffffff'),
          border: `1.5px solid ${hovered ? stage.color + '88' : (isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.09)')}`,
          boxShadow: hovered
            ? `0 4px 20px ${stage.color}22, 0 0 0 1px ${stage.color}33`
            : (isDark ? '0 2px 8px rgba(0,0,0,0.3)' : '0 2px 8px rgba(0,0,0,0.06)'),
        }}
      >
        {/* Top row: color dot + badges */}
        <div className={styles.stageTopRow}>
          <div className={styles.stageColorDot} style={{
            background: stage.color,
            boxShadow: `0 0 8px ${stage.color}88`,
          }} />
          <div className={styles.stageBadges}>
            {stage.is_default && (
              <span className={`${styles.stageBadge} ${styles.stageBadgeLetterSpacing}`} style={{ color: t.accent, background: t.accentBg }}>DEFAULT</span>
            )}
            {stage.is_closed_won && (
              <span className={styles.stageBadge} style={{ color: t.green, background: t.greenBg }}>WON</span>
            )}
            {stage.is_closed_lost && (
              <span className={styles.stageBadge} style={{ color: t.red, background: t.redBg }}>LOST</span>
            )}
          </div>
        </div>

        {/* Stage name */}
        <div className={styles.stageName} style={{ color: t.text }}>
          {stage.name}
        </div>

        {/* Bottom row: category + action count */}
        <div className={styles.stageBottomRow}>
          <span className={styles.stageCategory} style={{ color: t.textFaint }}>
            {categoryLabel[stage.category] ?? stage.category}
          </span>
          {ruleCount > 0 && (
            <span className={styles.stageRuleCount} style={{ color: t.accent, background: t.accentBg }}>
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
    <form onSubmit={handleSubmit} className={styles.addForm} style={{
      background: t.bgCard, border: `1px solid ${t.border}`,
    }}>
      <input
        autoFocus
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Stage name"
        className={styles.addFormInput}
        style={{ background: t.bgInput, border: `1px solid ${t.border}`, color: t.text }}
      />
      <div className={styles.colorPicker}>
        {COLORS.map(c => (
          <button
            key={c} type="button" onClick={() => setColor(c)}
            className={styles.colorBtn}
            style={{
              background: c,
              outline: color === c ? `2px solid ${t.text}` : 'none',
              outlineOffset: 2,
            }}
          />
        ))}
      </div>
      <button type="submit" disabled={!name.trim() || loading} className={styles.addFormSubmit}>
        {loading ? 'Adding…' : 'Add'}
      </button>
      <button type="button" onClick={onCancel} className={styles.addFormCancel} style={{
        border: `1px solid ${t.border}`, color: t.textMuted,
      }}>
        Cancel
      </button>
    </form>
  );
};
