import { z } from 'zod';

export const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return 'Never';
  const utcTimestamp = timestamp.endsWith('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z';
  const date = new Date(utcTimestamp);
  const diffMs = Date.now() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleString();
};

export const EMAIL_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

export const formSchema = z.object({
  agent_id: z.string().min(1, 'Agent ID is required').max(100)
    .regex(/^[a-zA-Z0-9._-]+$/, 'Only letters, numbers, hyphens, underscores, and dots allowed'),
  email: z.string().min(1, 'Email is required').regex(EMAIL_REGEX, 'Invalid email address'),
  app_password: z.string().optional(),
  display_name: z.string().max(255).optional(),
  phone: z.string().max(50).optional(),
  company_id: z.string().optional(),
});