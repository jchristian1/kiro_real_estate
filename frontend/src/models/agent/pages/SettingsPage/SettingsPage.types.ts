export interface PipelineStep {
  type: string;
  step: number;
  emoji: string;
  title: string;
  trigger: string;
  description: string;
  color: string;
  colorBg: string;
}

export const PIPELINE_STEPS: PipelineStep[] = [
  {
    type: 'INITIAL_INVITE',
    step: 1,
    emoji: '👋',
    title: 'First Contact',
    trigger: 'Sent automatically when a new lead comes in',
    description: 'This is the very first email your lead receives. It introduces you and invites them to fill out a short form so you can understand their needs.',
    color: '#6366f1',
    colorBg: 'rgba(99,102,241,0.1)',
  },
  {
    type: 'POST_HOT',
    step: 2,
    emoji: '🔥',
    title: 'Hot Lead Follow-up',
    trigger: 'Sent after the form is submitted — for high-scoring leads',
    description: 'This lead is ready to move fast. They scored high on your criteria (pre-approved, short timeline, wants a tour). Send an urgent, personal response.',
    color: '#ef4444',
    colorBg: 'rgba(239,68,68,0.1)',
  },
  {
    type: 'POST_WARM',
    step: 3,
    emoji: '🌤️',
    title: 'Warm Lead Follow-up',
    trigger: 'Sent after the form is submitted — for mid-scoring leads',
    description: 'This lead is interested but not in a rush. They have some qualifying factors. Send a helpful, informative response with next steps.',
    color: '#f59e0b',
    colorBg: 'rgba(245,158,11,0.1)',
  },
  {
    type: 'POST_NURTURE',
    step: 4,
    emoji: '🌱',
    title: 'Nurture Follow-up',
    trigger: 'Sent after the form is submitted — for lower-scoring leads',
    description: 'This lead is early in their journey. Keep the door open with a friendly, low-pressure message. They may convert later.',
    color: '#10b981',
    colorBg: 'rgba(16,185,129,0.1)',
  },
];

export const PLACEHOLDERS = [
  { key: '{lead_name}',   label: 'Lead Name' },
  { key: '{agent_name}',  label: 'Your Name' },
  { key: '{agent_phone}', label: 'Your Phone' },
  { key: '{agent_email}', label: 'Your Email' },
  { key: '{form_link}',   label: 'Form Link' },
];
