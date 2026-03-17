/**
 * Pipeline Admin API client — typed wrappers for all pipeline endpoints.
 * Follows the same axios pattern as agentApi.ts.
 */

import axios, { AxiosError } from 'axios';

const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const client = axios.create({ baseURL: BASE, withCredentials: true });

client.interceptors.response.use(
  r => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      const cur = window.location.pathname;
      if (!cur.startsWith('/login')) window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ── Enums (mirror backend) ────────────────────────────────────────────────

export type StageCategory = 'open' | 'in_progress' | 'waiting' | 'won' | 'lost';
export type ChangeSource = 'event' | 'manual' | 'rule' | 'import';
export type BuiltInEventType =
  | 'lead_created'
  | 'response_email_sent'
  | 'qualification_form_sent'
  | 'qualification_form_submitted'
  | 'qualification_bucket_hot'
  | 'qualification_bucket_warm'
  | 'qualification_bucket_nurture';
export type ActionType = 'send_email' | 'send_form' | 'update_score' | 'add_tag' | 'webhook';

// ── Response types ────────────────────────────────────────────────────────

export interface Pipeline {
  id: number;
  company_id: number;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PipelineStage {
  id: number;
  pipeline_id: number;
  name: string;
  key: string;
  color: string;
  category: StageCategory;
  position: number;
  is_default: boolean;
  is_closed_won: boolean;
  is_closed_lost: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeadStageHistoryEntry {
  id: number;
  lead_id: number;
  from_stage_id?: number;
  to_stage_id: number;
  change_source: ChangeSource;
  change_reason?: string;
  changed_by_user_id?: number;
  created_at: string;
}

export interface LeadStageResponse {
  lead_id: number;
  current_stage?: PipelineStage;
  stage_entered_at?: string;
  history: LeadStageHistoryEntry[];
}

export interface PipelineEventMapping {
  id: number;
  pipeline_id: number;
  event_type: BuiltInEventType;
  target_stage_id: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface PipelineActionRuleStep {
  id: number;
  rule_id: number;
  action_type: ActionType;
  action_config_json: string;
  position: number;
  created_at: string;
}

export interface PipelineActionRule {
  id: number;
  pipeline_id: number;
  name: string;
  trigger_type: string;
  trigger_stage_id?: number;
  trigger_event_type?: string;
  condition_type: string;
  condition_value?: string;
  is_enabled: boolean;
  position: number;
  steps: PipelineActionRuleStep[];
  created_at: string;
  updated_at: string;
}

export interface PipelineMetrics {
  total_leads: number;
  avg_time_per_stage: Record<string, number>;
  conversion_to_won: number;
  stuck_leads_count: number;
}

// ── Request types ─────────────────────────────────────────────────────────

export interface PipelineCreate { name: string; description?: string; }
export interface PipelineUpdate { name?: string; description?: string; is_active?: boolean; }

export interface PipelineStageCreate {
  name: string; key: string; color: string;
  category: StageCategory; position: number;
  is_default?: boolean; is_closed_won?: boolean; is_closed_lost?: boolean;
}
export interface PipelineStageUpdate {
  name?: string; key?: string; color?: string;
  category?: StageCategory; position?: number;
  is_default?: boolean; is_closed_won?: boolean; is_closed_lost?: boolean;
}

export interface EventMappingUpsert { target_stage_id: number; is_enabled: boolean; }

export interface RuleStepCreate { action_type: ActionType; action_config_json: string; position: number; }
export interface RuleCreate {
  name: string; trigger_type: string; trigger_stage_id?: number;
  trigger_event_type?: string; condition_type: string; condition_value?: string;
  is_enabled?: boolean; position: number; steps?: RuleStepCreate[];
}
export interface RuleUpdate {
  name?: string; trigger_type?: string; trigger_stage_id?: number;
  trigger_event_type?: string; condition_type?: string; condition_value?: string;
  is_enabled?: boolean; position?: number; steps?: RuleStepCreate[];
}

// ── API helpers ───────────────────────────────────────────────────────────

const get  = async <T>(path: string, params?: Record<string, unknown>): Promise<T> =>
  (await client.get<T>(path, { params })).data;
const post = async <T>(path: string, body: unknown): Promise<T> =>
  (await client.post<T>(path, body)).data;
const put  = async <T>(path: string, body: unknown): Promise<T> =>
  (await client.put<T>(path, body)).data;
const patch = async <T>(path: string, body: unknown): Promise<T> =>
  (await client.patch<T>(path, body)).data;
const del  = async <T>(path: string): Promise<T> =>
  (await client.delete<T>(path)).data;

// ── Pipeline endpoints ────────────────────────────────────────────────────

export const pipelinesApi = {
  // Pipelines
  listPipelines:    ()                          => get<Pipeline[]>('/pipelines'),
  getPipeline:      (id: number)                => get<Pipeline>(`/pipelines/${id}`),
  createPipeline:   (body: PipelineCreate)      => post<Pipeline>('/pipelines', body),
  updatePipeline:   (id: number, body: PipelineUpdate) => put<Pipeline>(`/pipelines/${id}`, body),
  activatePipeline: (id: number)                => post<Pipeline>(`/pipelines/${id}/activate`, {}),

  // Stages
  listStages:    (pipelineId: number)                              => get<PipelineStage[]>(`/pipelines/${pipelineId}/stages`),
  createStage:   (pipelineId: number, body: PipelineStageCreate)  => post<PipelineStage>(`/pipelines/${pipelineId}/stages`, body),
  updateStage:   (pipelineId: number, stageId: number, body: PipelineStageUpdate) =>
    put<PipelineStage>(`/pipelines/${pipelineId}/stages/${stageId}`, body),
  deleteStage:   (pipelineId: number, stageId: number, reassignTo?: number) =>
    del<void>(`/pipelines/${pipelineId}/stages/${stageId}${reassignTo ? `?reassign_to_stage_id=${reassignTo}` : ''}`),
  reorderStages: (pipelineId: number, orderedIds: number[])        =>
    post<PipelineStage[]>(`/pipelines/${pipelineId}/stages/reorder`, { ordered_ids: orderedIds }),

  // Event mappings
  listEventMappings:  (pipelineId: number)                                    => get<PipelineEventMapping[]>(`/pipelines/${pipelineId}/event-mappings`),
  upsertEventMapping: (pipelineId: number, eventType: BuiltInEventType, body: EventMappingUpsert) =>
    put<PipelineEventMapping>(`/pipelines/${pipelineId}/event-mappings/${eventType}`, body),

  // Rules
  listRules:    (pipelineId: number)                          => get<PipelineActionRule[]>(`/pipelines/${pipelineId}/rules`),
  createRule:   (pipelineId: number, body: RuleCreate)        => post<PipelineActionRule>(`/pipelines/${pipelineId}/rules`, body),
  updateRule:   (pipelineId: number, ruleId: number, body: RuleUpdate) =>
    put<PipelineActionRule>(`/pipelines/${pipelineId}/rules/${ruleId}`, body),
  deleteRule:   (pipelineId: number, ruleId: number)          => del<void>(`/pipelines/${pipelineId}/rules/${ruleId}`),
  reorderRules: (pipelineId: number, orderedIds: number[])    =>
    post<PipelineActionRule[]>(`/pipelines/${pipelineId}/rules/reorder`, { ordered_ids: orderedIds }),

  // Lead stage
  getLeadStage:  (leadId: number)                                    => get<LeadStageResponse>(`/pipelines/leads/${leadId}/stage`),
  moveLeadStage: (leadId: number, stageId: number, reason?: string)  =>
    patch<LeadStageResponse>(`/pipelines/leads/${leadId}/stage`, { stage_id: stageId, reason }),

  // Metrics
  getMetrics: (pipelineId: number) => get<PipelineMetrics>(`/pipelines/${pipelineId}/metrics`),
};

export const getPipelineErrorMessage = (err: unknown): string => {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data?.detail || err.response?.data?.error;
    if (typeof d === 'string') return d;
    const s = err.response?.status;
    if (s === 409) return err.response?.data?.detail || 'Conflict — check for active leads in this stage.';
    if (s === 403) return 'Access denied.';
    if (s === 404) return 'Not found.';
  }
  if (err instanceof Error) return err.message;
  return 'An unexpected error occurred.';
};
