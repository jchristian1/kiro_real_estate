/**
 * Agent API client — uses shared createApiClient factory.
 * 401s redirect to /agent/login (or /agent/signup if already there).
 */

import axios from 'axios';
import { createApiClient } from '@/shared/api/client';

export const agentApi = createApiClient(['/agent/login', '/agent/signup']);

/** Extract a user-friendly error message from an axios error */
export const getAgentErrorMessage = (err: unknown): string => {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail || err.response?.data?.error || err.response?.data?.message;
    if (typeof detail === 'string') return detail;
    if (typeof detail === 'object' && detail?.error) return detail.error;
    const status = err.response?.status;
    if (status === 429) return 'Too many attempts. Please wait and try again.';
    if (status === 403) return 'Access denied.';
    if (status === 404) return 'Not found.';
  }
  if (err instanceof Error) return err.message;
  return 'An unexpected error occurred.';
};
