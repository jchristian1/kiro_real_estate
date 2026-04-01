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
export type ActionType = 'send_email_template' | 'send_qualification_form' | 'send_bucket_followup_email' | 'move_to_stage';

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