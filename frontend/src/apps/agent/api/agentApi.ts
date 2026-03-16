/**
 * Agent API client — axios wrapper with session cookie handling and 401 redirect.
 * All requests go to /api/v1/agent/* with credentials included.
 */

import axios, { AxiosError } from 'axios';

const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const client = axios.create({
  baseURL: BASE,
  withCredentials: true,
});

// 401 → redirect to agent login
client.interceptors.response.use(
  r => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      const current = window.location.pathname;
      if (!current.startsWith('/agent/login') && !current.startsWith('/agent/signup')) {
        window.location.href = '/agent/login';
      }
    }
    return Promise.reject(err);
  }
);

export const agentApi = {
  get: async <T>(path: string, params?: Record<string, unknown>): Promise<T> => {
    const r = await client.get<T>(path, { params });
    return r.data;
  },
  post: async <T>(path: string, body: unknown): Promise<T> => {
    const r = await client.post<T>(path, body);
    return r.data;
  },
  put: async <T>(path: string, body: unknown): Promise<T> => {
    const r = await client.put<T>(path, body);
    return r.data;
  },
  patch: async <T>(path: string, body: unknown): Promise<T> => {
    const r = await client.patch<T>(path, body);
    return r.data;
  },
  delete: async <T>(path: string): Promise<T> => {
    const r = await client.delete<T>(path);
    return r.data;
  },
};

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
