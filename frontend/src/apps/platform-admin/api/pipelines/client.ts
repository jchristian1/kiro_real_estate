/**
 * Pipelines axios client — uses shared createApiClient factory.
 * 401s redirect to /login (platform-admin login).
 */

import { createApiClient } from '@/shared/api/client';

const _client = createApiClient('/login');

/** Raw axios instance — exported for edge cases */
export const client = _client._axios;

/** Typed HTTP helpers for use across pipelines/* sub-modules */
export const get   = _client.get;
export const post  = _client.post;
export const put   = _client.put;
export const patch = _client.patch;
export const del   = _client.delete;