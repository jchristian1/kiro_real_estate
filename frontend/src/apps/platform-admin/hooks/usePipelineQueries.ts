/**
 * TanStack Query hooks for all pipeline admin endpoints.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  pipelinesApi,
  PipelineCreate, PipelineUpdate,
  PipelineStageCreate, PipelineStageUpdate,
  EventMappingUpsert, BuiltInEventType,
  RuleCreate, RuleUpdate,
} from '../api/pipelinesApi';

// ── Query Keys ────────────────────────────────────────────────────────────

export const pipelineKeys = {
  all:           ()             => ['pipelines'] as const,
  list:          ()             => ['pipelines', 'list'] as const,
  detail:        (id: number)   => ['pipelines', id] as const,
  stages:        (id: number)   => ['pipelines', id, 'stages'] as const,
  eventMappings: (id: number)   => ['pipelines', id, 'event-mappings'] as const,
  rules:         (id: number)   => ['pipelines', id, 'rules'] as const,
  metrics:       (id: number)   => ['pipelines', id, 'metrics'] as const,
  leadStage:     (lid: number)  => ['pipelines', 'leads', lid, 'stage'] as const,
};

// ── Queries ───────────────────────────────────────────────────────────────

export const usePipelines = () =>
  useQuery({ queryKey: pipelineKeys.list(), queryFn: pipelinesApi.listPipelines });

export const usePipeline = (id: number) =>
  useQuery({ queryKey: pipelineKeys.detail(id), queryFn: () => pipelinesApi.getPipeline(id), enabled: !!id });

export const usePipelineStages = (pipelineId: number) =>
  useQuery({ queryKey: pipelineKeys.stages(pipelineId), queryFn: () => pipelinesApi.listStages(pipelineId), enabled: !!pipelineId });

export const usePipelineEventMappings = (pipelineId: number) =>
  useQuery({ queryKey: pipelineKeys.eventMappings(pipelineId), queryFn: () => pipelinesApi.listEventMappings(pipelineId), enabled: !!pipelineId });

export const usePipelineRules = (pipelineId: number) =>
  useQuery({ queryKey: pipelineKeys.rules(pipelineId), queryFn: () => pipelinesApi.listRules(pipelineId), enabled: !!pipelineId });

export const usePipelineMetrics = (pipelineId: number) =>
  useQuery({ queryKey: pipelineKeys.metrics(pipelineId), queryFn: () => pipelinesApi.getMetrics(pipelineId), enabled: !!pipelineId });

export const useLeadStageHistory = (leadId: number) =>
  useQuery({ queryKey: pipelineKeys.leadStage(leadId), queryFn: () => pipelinesApi.getLeadStage(leadId), enabled: !!leadId });

// ── Pipeline mutations ────────────────────────────────────────────────────

export const useCreatePipeline = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PipelineCreate) => pipelinesApi.createPipeline(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: pipelineKeys.list() }),
  });
};

export const useUpdatePipeline = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & PipelineUpdate) => pipelinesApi.updatePipeline(id, body),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: pipelineKeys.detail(id) });
      qc.invalidateQueries({ queryKey: pipelineKeys.list() });
    },
  });
};

export const useActivatePipeline = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => pipelinesApi.activatePipeline(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: pipelineKeys.list() }),
  });
};

// ── Stage mutations ───────────────────────────────────────────────────────

export const useCreateStage = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, ...body }: { pipelineId: number } & PipelineStageCreate) =>
      pipelinesApi.createStage(pipelineId, body),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.stages(pipelineId) }),
  });
};

export const useUpdateStage = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, stageId, ...body }: { pipelineId: number; stageId: number } & PipelineStageUpdate) =>
      pipelinesApi.updateStage(pipelineId, stageId, body),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.stages(pipelineId) }),
  });
};

export const useDeleteStage = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, stageId, reassignTo }: { pipelineId: number; stageId: number; reassignTo?: number }) =>
      pipelinesApi.deleteStage(pipelineId, stageId, reassignTo),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.stages(pipelineId) }),
  });
};

export const useReorderStages = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, orderedIds }: { pipelineId: number; orderedIds: number[] }) =>
      pipelinesApi.reorderStages(pipelineId, orderedIds),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.stages(pipelineId) }),
  });
};

// ── Event mapping mutations ───────────────────────────────────────────────

export const useUpsertEventMapping = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, eventType, ...body }: { pipelineId: number; eventType: BuiltInEventType } & EventMappingUpsert) =>
      pipelinesApi.upsertEventMapping(pipelineId, eventType, body),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.eventMappings(pipelineId) }),
  });
};

// ── Rule mutations ────────────────────────────────────────────────────────

export const useCreateRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, ...body }: { pipelineId: number } & RuleCreate) =>
      pipelinesApi.createRule(pipelineId, body),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.rules(pipelineId) }),
  });
};

export const useUpdateRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, ruleId, ...body }: { pipelineId: number; ruleId: number } & RuleUpdate) =>
      pipelinesApi.updateRule(pipelineId, ruleId, body),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.rules(pipelineId) }),
  });
};

export const useDeleteRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, ruleId }: { pipelineId: number; ruleId: number }) =>
      pipelinesApi.deleteRule(pipelineId, ruleId),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.rules(pipelineId) }),
  });
};

export const useReorderRules = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineId, orderedIds }: { pipelineId: number; orderedIds: number[] }) =>
      pipelinesApi.reorderRules(pipelineId, orderedIds),
    onSuccess: (_d, { pipelineId }) => qc.invalidateQueries({ queryKey: pipelineKeys.rules(pipelineId) }),
  });
};

// ── Lead stage mutation ───────────────────────────────────────────────────

export const useMoveLeadStage = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, stageId, reason }: { leadId: number; stageId: number; reason?: string }) =>
      pipelinesApi.moveLeadStage(leadId, stageId, reason),
    onSuccess: (_d, { leadId }) => qc.invalidateQueries({ queryKey: pipelineKeys.leadStage(leadId) }),
  });
};
