import { ActionType, BuiltInEventType, StageCategory } from "@/models/platform-admin/pipeline-api-model";
import { ToastType } from "@/shared/contexts";

export const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/leads': 'Leads',
  '/buyer-leads': 'Buyer Automation',
  '/agents': 'Agents',
  '/companies': 'Companies',
  '/lead-sources': 'Lead Sources',
  '/templates': 'Templates',
  '/audit-logs': 'Audit Logs',
  '/settings': 'Settings',
};

export const TRIGGER_OPTIONS = [
  { value: 'on_stage_enter', label: 'Lead enters a stage', icon: '→' },
  { value: 'on_event', label: 'A platform event fires', icon: '⚡' },
];

export const CONDITION_OPTIONS = [
  { value: 'always', label: 'Always (no condition)', desc: 'Run every time the trigger fires' },
  { value: 'bucket_is', label: 'Lead score bucket is…', desc: 'e.g. HOT, WARM, NURTURE' },
  { value: 'stage_is', label: 'Lead is in stage…', desc: 'Match by stage key' },
];

export const ACTION_OPTIONS: { value: ActionType; label: string; icon: string; desc: string }[] = [
  { value: 'send_email_template', label: 'Send Email Template', icon: '✉️', desc: 'Send a pre-built email template to the lead' },
  { value: 'send_qualification_form', label: 'Send Qualification Form', icon: '📋', desc: 'Send a qualification form to the lead' },
  { value: 'send_bucket_followup_email', label: 'Send Bucket Follow-up', icon: '📨', desc: 'Send a follow-up email based on score bucket' },
  { value: 'move_to_stage', label: 'Move to Stage', icon: '➡️', desc: 'Move the lead to a specific pipeline stage' },
];


export const EVENT_LABELS: Record<BuiltInEventType, string> = {
  lead_created: 'Lead Created',
  response_email_sent: 'Response Email Sent',
  qualification_form_sent: 'Qualification Form Sent',
  qualification_form_submitted: 'Qualification Form Submitted',
  qualification_bucket_hot: 'Qualified as Hot',
  qualification_bucket_warm: 'Qualified as Warm',
  qualification_bucket_nurture: 'Qualified as Nurture',
};

export const ALL_EVENTS = Object.keys(EVENT_LABELS) as BuiltInEventType[];

export const COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
  '#f97316', '#eab308', '#22c55e', '#14b8a6',
  '#3b82f6', '#06b6d4',
];
export const CATEGORIES: { value: StageCategory; label: string; icon: string }[] = [
  { value: 'open', label: 'Open', icon: '○' },
  { value: 'in_progress', label: 'In Progress', icon: '◑' },
  { value: 'waiting', label: 'Waiting', icon: '◷' },
  { value: 'won', label: 'Won', icon: '★' },
  { value: 'lost', label: 'Lost', icon: '✕' },
];

// ── Main drawer ───────────────────────────────────────────────────────────


export const TEMPLATES = [
  { id: 'real_estate', label: 'Real Estate Buyer Pipeline', desc: 'New Lead → Contacted → Appointment Set → Under Contract → Won / Lost' },
  { id: 'law_firm', label: 'Law Firm Pipeline', desc: 'New Inquiry → Consultation Scheduled → Retained → Active Case → Closed' },
  { id: 'blank', label: 'Blank Pipeline', desc: 'Start from scratch with no stages' },
];

export const PLACEHOLDERS = ['{lead_name}', '{agent_name}', '{agent_phone}', '{agent_email}'];

export const TOAST_COLORS: Record<ToastType, { bg: string; border: string; color: string; dot: string }> = {
  success: { bg: 'rgba(52,211,153,0.1)', border: 'rgba(52,211,153,0.3)', color: '#34d399', dot: '#34d399' },
  error: { bg: 'rgba(248,113,113,0.1)', border: 'rgba(248,113,113,0.3)', color: '#f87171', dot: '#f87171' },
  warning: { bg: 'rgba(251,191,36,0.1)', border: 'rgba(251,191,36,0.3)', color: '#fbbf24', dot: '#fbbf24' },
  info: { bg: 'rgba(99,102,241,0.1)', border: 'rgba(99,102,241,0.3)', color: '#818cf8', dot: '#818cf8' },
};