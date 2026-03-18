/**
 * PipelinesPage — admin pipeline builder with Builder, Built-in Rules,
 * Automations, and Activity tabs.
 * Requirements: 9.1, 9.9
 */

import React, { useState } from 'react';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { usePipelines, useActivatePipeline, useCreatePipeline } from '../hooks/usePipelineQueries';
import { BuilderTab } from '../components/pipelines/BuilderTab';
import { BuiltInRulesTab } from '../components/pipelines/BuiltInRulesTab';
import { AutomationsTab } from '../components/pipelines/AutomationsTab';
import { ActivityTab } from '../components/pipelines/ActivityTab';
import { TemplateChooserModal } from '../components/pipelines/TemplateChooserModal';
import type { Pipeline } from '../api/pipelinesApi';

type Tab = 'builder' | 'rules' | 'automations' | 'activity';

const TABS: { id: Tab; label: string }[] = [
  { id: 'builder',     label: 'Builder' },
  { id: 'rules',       label: 'Built-in Rules' },
  { id: 'automations', label: 'Automations' },
  { id: 'activity',    label: 'Activity' },
];

export const PipelinesPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [activeTab, setActiveTab] = useState<Tab>('builder');
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);

  const { data: pipelines = [], isLoading } = usePipelines();
  const activatePipeline = useActivatePipeline();
  const createPipeline = useCreatePipeline();

  // Auto-select active pipeline or first available
  const activePipeline = pipelines.find(p => p.is_active) ?? pipelines[0] ?? null;
  const currentId = selectedPipelineId ?? activePipeline?.id ?? null;
  const currentPipeline: Pipeline | undefined = pipelines.find(p => p.id === currentId);

  // Show template chooser when no pipelines exist
  const showTemplateChooser = !isLoading && pipelines.length === 0;

  const card: React.CSSProperties = {
    background: t.bgCard,
    border: `1px solid ${t.border}`,
    borderRadius: 16,
    padding: '20px 24px',
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: t.textFaint, fontSize: 14 }}>
        Loading…
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Pipelines</h1>
          {currentPipeline?.is_active && (
            <span style={{ fontSize: 11, fontWeight: 600, color: t.green, background: t.greenBg, padding: '3px 10px', borderRadius: 20 }}>
              Active
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Pipeline selector */}
          {pipelines.length > 1 && (
            <select
              value={currentId ?? ''}
              onChange={e => setSelectedPipelineId(Number(e.target.value))}
              style={{
                background: t.bgInput, border: `1px solid ${t.border}`, borderRadius: 9,
                color: t.text, fontSize: 13, padding: '7px 12px', cursor: 'pointer',
              }}
            >
              {pipelines.map(p => (
                <option key={p.id} value={p.id}>{p.name}{p.is_active ? ' ✓' : ''}</option>
              ))}
            </select>
          )}

          {currentPipeline && !currentPipeline.is_active && (
            <button
              onClick={() => activatePipeline.mutate(currentPipeline.id)}
              disabled={activatePipeline.isPending}
              style={{
                background: t.accentBg, border: `1px solid ${t.accent}`, borderRadius: 9,
                color: t.accent, fontSize: 13, fontWeight: 600, padding: '7px 14px', cursor: 'pointer',
              }}
            >
              Set Active
            </button>
          )}

          <button
            onClick={() => setShowNewModal(true)}
            style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 9, color: '#fff',
              fontSize: 13, fontWeight: 600, padding: '7px 14px', cursor: 'pointer',
              boxShadow: `0 4px 14px ${t.accentGlow}`,
            }}
          >
            + New Pipeline
          </button>
        </div>
      </div>

      {/* Metrics row */}
      {currentId && <PipelineMetricsRow pipelineId={currentId} />}

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 2, borderBottom: `1px solid ${t.border}`, paddingBottom: 0 }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '10px 18px', fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? t.accent : t.textMuted,
              borderBottom: activeTab === tab.id ? `2px solid ${t.accent}` : '2px solid transparent',
              marginBottom: -1, transition: 'all 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {!currentId ? (
        <div style={{ ...card, textAlign: 'center', padding: '48px 24px', color: t.textMuted }}>
          No pipeline selected. Create one to get started.
        </div>
      ) : (
        <>
          {activeTab === 'builder'     && <BuilderTab pipelineId={currentId} />}
          {activeTab === 'rules'       && <BuiltInRulesTab pipelineId={currentId} />}
          {activeTab === 'automations' && <AutomationsTab pipelineId={currentId} />}
          {activeTab === 'activity'    && <ActivityTab pipelineId={currentId} />}
        </>
      )}

      {/* Template chooser modal (first run) */}
      {(showTemplateChooser || showNewModal) && (
        <TemplateChooserModal
          onClose={() => setShowNewModal(false)}
          onCreate={async (name) => {
            const p = await createPipeline.mutateAsync({ name });
            setSelectedPipelineId(p.id);
            setShowNewModal(false);
          }}
        />
      )}
    </div>
  );
};

// ── Metrics row sub-component ─────────────────────────────────────────────

import { usePipelineMetrics } from '../hooks/usePipelineQueries';

const PipelineMetricsRow: React.FC<{ pipelineId: number }> = ({ pipelineId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const { data: metrics } = usePipelineMetrics(pipelineId);

  const cards = [
    { label: 'Leads in Pipeline', value: metrics ? String(metrics.total_leads) : '—' },
    { label: 'Avg Time in Stage', value: metrics ? `${Math.round(Object.values(metrics.avg_time_per_stage).reduce((a, b) => a + b, 0) / Math.max(Object.keys(metrics.avg_time_per_stage).length, 1))}h` : '—' },
    { label: 'Conversion to Won', value: metrics ? `${(metrics.conversion_to_won * 100).toFixed(1)}%` : '—' },
    { label: 'Stuck Leads', value: metrics ? String(metrics.stuck_leads_count) : '—' },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
      {cards.map(c => (
        <div key={c.label} style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '16px 20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 8 }}>
            {c.label}
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: t.text, letterSpacing: '-0.5px' }}>{c.value}</div>
        </div>
      ))}
    </div>
  );
};
