/**
 * PipelinesPage — admin pipeline builder with Builder, Built-in Rules,
 * Automations, and Activity tabs.
 * Requirements: 9.1, 9.9
 */

import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { usePipelines, useActivatePipeline, useCreatePipeline } from '@/apps/platform-admin/hooks/usePipelineQueries';
import { BuilderTab } from '@/apps/platform-admin/components/pipelines/BuilderTab';
import { BuiltInRulesTab } from '@/apps/platform-admin/components/pipelines/BuiltInRulesTab';
import { AutomationsTab } from '@/apps/platform-admin/components/pipelines/AutomationsTab';
import { ActivityTab } from '@/apps/platform-admin/components/pipelines/ActivityTab';
import { TemplateChooserModal } from '@/apps/platform-admin/components/pipelines/TemplateChooserModal';
import type { Pipeline } from '@/apps/platform-admin/api/pipelinesApi';
import styles from './index.module.css';

type Tab = 'builder' | 'rules' | 'automations' | 'activity';

const TABS: { id: Tab; label: string }[] = [
  { id: 'builder', label: 'Builder' },
  { id: 'rules', label: 'Built-in Rules' },
  { id: 'automations', label: 'Automations' },
  { id: 'activity', label: 'Activity' },
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

  return (
    return (
      <div className={styles.loadingContainer} style={{ color: t.textFaint }}>
        Loading…
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Header row */}
      <div className={styles.headerRow}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title} style={{ color: t.text }}>Pipelines</h1>
          {currentPipeline?.is_active && (
            <span className={styles.activeBadge} style={{ color: t.green, background: t.greenBg }}>
              Active
            </span>
          )}
        </div>

        <div className={styles.headerRight}>
          {/* Pipeline selector */}
          {pipelines.length > 1 && (
            <select
              value={currentId ?? ''}
              onChange={e => setSelectedPipelineId(Number(e.target.value))}
              className={styles.pipelineSelect}
              style={{
                background: t.bgInput, border: `1px solid ${t.border}`,
                color: t.text,
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
              className={styles.setActiveButton}
              style={{
                background: t.accentBg, border: `1px solid ${t.accent}`,
                color: t.accent,
              }}
            >
              Set Active
            </button>
          )}

          <button
            onClick={() => setShowNewModal(true)}
            className={styles.newPipelineButton}
            style={{
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
      <div className={styles.tabBar} style={{ borderBottom: `1px solid ${t.border}` }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : styles.tabInactive}`}
            style={{
              color: activeTab === tab.id ? t.accent : t.textMuted,
              borderBottom: activeTab === tab.id ? `2px solid ${t.accent}` : '2px solid transparent',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {!currentId ? (
        <div className={styles.emptyState} style={{ background: t.bgCard, border: `1px solid ${t.border}`, color: t.textMuted }}>
          No pipeline selected. Create one to get started.
        </div>
      ) : (
        <>
          {activeTab === 'builder' && <BuilderTab pipelineId={currentId} />}
          {activeTab === 'rules' && <BuiltInRulesTab pipelineId={currentId} />}
          {activeTab === 'automations' && <AutomationsTab pipelineId={currentId} />}
          {activeTab === 'activity' && <ActivityTab pipelineId={currentId} />}
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
    <div className={styles.metricsGrid}>
      {cards.map(c => (
        <div key={c.label} className={styles.metricCard} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
          <div className={styles.metricLabel} style={{ color: t.textFaint }}>
            {c.label}
          </div>
          <div className={styles.metricValue} style={{ color: t.text }}>{c.value}</div>
        </div>
      ))}
    </div>
  );
};
