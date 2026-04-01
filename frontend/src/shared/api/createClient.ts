/**
 * createApiClient — shared factory for axios clients.
 * Creates a client with 401 redirect to a configurable login path,
 * plus typed get/post/put/patch/del helpers.
 */

import axios, { AxiosError } from 'axios';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';

export interface ApiClient {
  get:   <T>(path: string, params?: Record<string, unknown>) => Promise<T>;
  post:  <T>(path: string, body: unknown) => Promise<T>;
  put:   <T>(path: string, body: unknown) => Promise<T>;
  patch: <T>(path: string, body: unknown) => Promise<T>;
  delete: <T>(path: string) => Promise<T>;
  /** Raw axios instance — use only when helpers are insufficient */
  _axios: ReturnType<typeof axios.create>;
}

/**
 * @param loginPath  Path prefix to redirect on 401, e.g. '/login' or '/agent/login'.
 *                   Multiple prefixes can be provided (agent has /login AND /signup).
 */
export function createApiClient(loginPath: string | string[]): ApiClient {
  const loginPaths = Array.isArray(loginPath) ? loginPath : [loginPath];

  const instance = axios.create({ baseURL: API_BASE_URL, withCredentials: true });

  instance.interceptors.response.use(
    r => r,
    (err: AxiosError) => {
      if (err.response?.status === 401) {
        const cur = window.location.pathname;
        const alreadyOnLogin = loginPaths.some(p => cur.startsWith(p));
        if (!alreadyOnLogin) window.location.href = loginPaths[0];
      }
      return Promise.reject(err);
    }
  );

  return {
    _axios: instance,
    get:    async <T>(path: string, params?: Record<string, unknown>) =>
      (await instance.get<T>(path, { params })).data,
    post:   async <T>(path: string, body: unknown) =>
      (await instance.post<T>(path, body)).data,
    put:    async <T>(path: string, body: unknown) =>
      (await instance.put<T>(path, body)).data,
    patch:  async <T>(path: string, body: unknown) =>
      (await instance.patch<T>(path, body)).data,
    delete: async <T>(path: string) =>
      (await instance.delete<T>(path)).data,
  };
}
