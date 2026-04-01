import { SAMPLE_LEAD_DATA } from '../../shared-agent';

export interface OnboardingStep {
  path: string;
  label: string;
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  { path: 'account', label: 'Account' },
  { path: 'profile', label: 'Profile' },
  { path: 'gmail', label: 'Gmail' },
  { path: 'sources', label: 'Sources' },
  { path: 'automation', label: 'Automation' },
  { path: 'templates', label: 'Templates' },
  { path: 'go-live', label: 'Go Live' },
];

export const SAMPLE_LEAD = SAMPLE_LEAD_DATA;

export const GMAIL_ERROR_MESSAGES: Record<string, string> = {
  IMAP_DISABLED: 'IMAP is disabled in your Gmail settings. Enable it under Settings → See all settings → Forwarding → IMAP.',
  TWO_FACTOR_REQUIRED: '2-Step Verification is required. Enable it in your Google Account security settings first.',
  INVALID_PASSWORD: 'Invalid App Password. Make sure you copied it correctly (no spaces).',
  RATE_LIMITED: 'Too many attempts. Please wait 15 minutes and try again.',
  CONNECTION_FAILED: 'Could not connect to Gmail. Check your internet connection and try again.',
};

export const TEMPLATE_TYPES = [
  { type: 'INITIAL_INVITE', label: 'Initial Outreach', desc: 'First email sent when a new lead is detected' },
  { type: 'POST_HOT', label: 'Follow Up (Hot)', desc: 'Sent to hot leads after scoring' },
  { type: 'POST_WARM', label: 'Follow Up (Warm)', desc: 'Sent to warm leads after scoring' },
  { type: 'POST_NURTURE', label: 'Nurture', desc: 'Sent to nurture leads over time' },
];

export const DEFAULT_TEMPLATES: Record<string, { subject: string; body: string }> = {
  INITIAL_INVITE: {
    subject: 'Hi {lead_name}, I saw your inquiry',
    body: 'Hi {lead_name},\n\nI noticed your interest and would love to help. I\'m {agent_name} and I specialize in this area.\n\nFeel free to reach me at {agent_phone} or reply to this email.\n\nBest,\n{agent_name}',
  },
  POST_HOT: {
    subject: 'Following up — {lead_name}',
    body: 'Hi {lead_name},\n\nJust checking in to see if you had any questions. I\'m here to help!\n\n{agent_name}\n{agent_phone}',
  },
  POST_WARM: {
    subject: 'Thanks for completing the form, {lead_name}!',
    body: 'Hi {lead_name},\n\nThank you for filling out the qualification form. I\'ll review your answers and be in touch shortly.\n\n{agent_name}',
  },
  POST_NURTURE: {
    subject: 'Let\'s schedule a tour, {lead_name}',
    body: 'Hi {lead_name},\n\nI\'d love to show you around. Please use this link to pick a time: {form_link}\n\nLooking forward to meeting you!\n{agent_name}',
  },
};
