/**
 * TanStack Query hooks for all agent API endpoints.
 * Typed against the backend response models.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '../api/agentApi';

// ── Types ────────────────────────────────────────────────────────────────────

export interface AgentUser {
  id: number; email: string; full_name: string;
  onboarding_completed: boolean;
}

export interface Lead {
  id: number; name: string; email?: string; phone?: string;
  score?: number; score_bucket?: 'HOT' | 'WARM' | 'NURTURE';
  current_state?: string; agent_user_id?: number;
  // dashboard uses 'source', leads list uses 'lead_source_name' — support both
  source?: string; lead_source_name?: string;
  // dashboard uses 'address', leads list uses 'property_address' — support both
  address?: string; property_address?: string;
  listing_url?: string; created_at: string;
  last_agent_action_at?: string; is_aging?: boolean;
  score_bucket_label?: string;
}

export interface ScoreFactor { label: string; points: number; met: boolean; }

export interface LeadDetail {
  lead: {
    id: number; name: string; phone?: string; email?: string;
    score?: number; score_bucket?: string; current_state?: string;
    source?: string; address?: string; listing_url?: string;
    created_at: string; last_agent_action_at?: string; is_aging: boolean;
  };
  scoring_breakdown?: { total: number; factors: ScoreFactor[] };
  timeline: LeadEvent[];
  rendered_emails: RenderedEmail[];
  notes: NoteItem[];
}

export interface LeadEvent {
  id: number; event_type: string; created_at: string; payload?: Record<string, unknown>;
}

export interface RenderedEmail { type: string; subject: string; body: string; sent_at?: string; }
export interface NoteItem { text: string; created_at: string; }
/** @deprecated use NoteItem */
export interface LeadNote { id: number; content: string; created_at: string; }

export interface LeadsResponse {
  leads: Lead[]; total: number; page: number; pages: number;
}

export interface DashboardData {
  hot_lead_count: number;
  hot_leads: Array<{ id: number; name: string; score?: number; source?: string; address?: string; created_at: string; is_aging?: boolean; lead_source_name?: string; }>;
  aging_lead_count: number;
  aging_leads: Array<{ id: number; name: string; score?: number; minutes_since_created: number; is_aging: true; created_at?: string; lead_source_name?: string; }>;
  response_time_today_minutes?: number;
  watcher_status: string;
}

export interface Template {
  id?: number;
  name?: string;
  type: string; subject: string; body: string;
  tone?: string; version: number; is_active: boolean; is_custom: boolean;
}

export interface ReportsSummary {
  leads_by_source: { source: string; count: number }[];
  bucket_distribution: { HOT: number; WARM: number; NURTURE: number };
  avg_response_time_minutes?: number;
  appointments_set: number;
  period_start: string; period_end: string;
}

// ── Query Keys ───────────────────────────────────────────────────────────────

export const agentKeys = {
  me:         () => ['agent', 'me'] as const,
  dashboard:  () => ['agent', 'dashboard'] as const,
  leads:      (p: Record<string, unknown>) => ['agent', 'leads', p] as const,
  lead:       (id: number) => ['agent', 'lead', id] as const,
  templates:  () => ['agent', 'templates'] as const,
  reports:    (period: string) => ['agent', 'reports', period] as const,
  leadPipeline: (id: number) => ['agent', 'lead', id, 'pipeline'] as const,
};

// ── Queries ──────────────────────────────────────────────────────────────────

export const useAgentMe = () =>
  useQuery({ queryKey: agentKeys.me(), queryFn: () => agentApi.get<AgentUser>('/agent/auth/me') });

export const useAgentDashboard = () =>
  useQuery({ queryKey: agentKeys.dashboard(), queryFn: () => agentApi.get<DashboardData>('/agent/dashboard'), refetchInterval: 30_000 });

export const useAgentLeads = (params: Record<string, unknown>) =>
  useQuery({ queryKey: agentKeys.leads(params), queryFn: () => agentApi.get<LeadsResponse>('/agent/leads', params) });

export const useAgentLead = (id: number) =>
  useQuery({ queryKey: agentKeys.lead(id), queryFn: () => agentApi.get<LeadDetail>(`/agent/leads/${id}`) });

export const useAgentTemplates = () =>
  useQuery({ queryKey: agentKeys.templates(), queryFn: () => agentApi.get<{ templates: Template[] }>('/agent/templates'), staleTime: 0, refetchOnMount: 'always' });

export const useAgentReports = (period: string) =>
  useQuery({ queryKey: agentKeys.reports(period), queryFn: () => agentApi.get<ReportsSummary>('/agent/reports/summary', { period }) });

// ── Pipeline types ────────────────────────────────────────────────────────

export interface AgentPipelineStage {
  id: number; name: string; key: string; color: string;
  category: string; position: number;
  is_default: boolean; is_closed_won: boolean; is_closed_lost: boolean;
}

export interface AgentLeadPipeline {
  pipeline_name: string;
  current_stage?: AgentPipelineStage;
  stage_entered_at?: string;
  stages: AgentPipelineStage[];
  lifecycle: Array<{ event_type: string; occurred_at: string }>;
  stage_history: Array<{
    id: number; lead_id: number;
    from_stage_id?: number; to_stage_id: number;
    change_source: string; change_reason?: string; created_at: string;
  }>;
}

export const useLeadPipeline = (leadId: number) =>
  useQuery({
    queryKey: agentKeys.leadPipeline(leadId),
    queryFn: () => agentApi.get<AgentLeadPipeline>(`/agent/leads/${leadId}/pipeline`),
    enabled: !!leadId,
  });

// ── Mutations ────────────────────────────────────────────────────────────────

export const useUpdateLeadStatus = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      agentApi.patch(`/agent/leads/${id}/status`, { status }),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: agentKeys.lead(id) });
      qc.invalidateQueries({ queryKey: ['agent', 'leads'] });
      qc.invalidateQueries({ queryKey: agentKeys.dashboard() });
    },
  });
};

export const useAddLeadNote = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content }: { id: number; content: string }) =>
      agentApi.post(`/agent/leads/${id}/notes`, { text: content }),
    onSuccess: (_d, { id }) => qc.invalidateQueries({ queryKey: agentKeys.lead(id) }),
  });
};

export const useSaveTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ type, subject, body, tone }: { type: string; subject: string; body: string; tone: string }) =>
      agentApi.put(`/agent/templates/${type}`, { subject, body, tone }),
    onSuccess: () => qc.invalidateQueries({ queryKey: agentKeys.templates() }),
  });
};

export const useCreateTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { template_type: string; name: string; subject: string; body: string; tone?: string; activate?: boolean }) =>
      agentApi.post('/agent/templates', body),
    onSuccess: () => qc.refetchQueries({ queryKey: agentKeys.templates() }),
  });
};

export const useUpdateTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; name?: string; subject?: string; body?: string; tone?: string }) =>
      agentApi.put(`/agent/templates/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: agentKeys.templates() }),
  });
};

export const useActivateTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => agentApi.post(`/agent/templates/${id}/activate`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: agentKeys.templates() }),
  });
};

export const useDeleteTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => agentApi.delete(`/agent/templates/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: agentKeys.templates() }),
  });
};
