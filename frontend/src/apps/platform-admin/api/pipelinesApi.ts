// ── Re-exports (types + named exports) ───────────────────────────────────
export * from './pipelines/client';
export * from './pipelines/error';
export * from './pipelines/pipelines';
export * from './pipelines/stage';
export * from './pipelines/evenmappings';
export * from './pipelines/rules';
export * from './pipelines/lead-stage';
export * from './pipelines/metrics';

// ── Combined API object (preserves original pipelinesApi surface) ─────────
import { pipelines } from './pipelines/pipelines';
import { stages } from './pipelines/stage';
import { eventMappings } from './pipelines/evenmappings';
import { rules } from './pipelines/rules';
import { leadStage } from './pipelines/lead-stage';
import { metrics } from './pipelines/metrics';

export const pipelinesApi = {
  ...pipelines,
  ...stages,
  ...eventMappings,
  ...rules,
  ...leadStage,
  getMetrics: metrics.getPipelineMetrics,
};
