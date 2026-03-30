/**
 * Task API — HTTP calls only. No business logic.
 * All requests go through the shared agentApi client (withCredentials).
 */

import { agentApi } from './agentApi';

export interface Task {
  id: number;
  lead_id: number;
  agent_user_id: number;
  title: string;
  description?: string;
  status: 'open' | 'done';
  source: 'manual' | 'pipeline';
  due_at?: string;
  created_at: string;
  updated_at?: string;
  completed_at?: string;
}

export interface TaskListResponse {
  tasks: Task[];
  total: number;
}

export interface TaskCreateResponse {
  ok: boolean;
  task: Task;
}

export interface CreateTaskPayload {
  title: string;
  description?: string;
  due_at?: string;
}

export interface UpdateTaskPayload {
  title?: string;
  description?: string;
  due_at?: string;
  status?: 'open' | 'done';
}

export const tasksApi = {
  list: (leadId: number, status?: 'open' | 'done') =>
    agentApi.get<TaskListResponse>(`/agent/leads/${leadId}/tasks`, status ? { status } : undefined),

  create: (leadId: number, payload: CreateTaskPayload) =>
    agentApi.post<TaskCreateResponse>(`/agent/leads/${leadId}/tasks`, payload),

  update: (taskId: number, payload: UpdateTaskPayload) =>
    agentApi.patch<Task>(`/agent/tasks/${taskId}`, payload),

  delete: (taskId: number) =>
    agentApi.delete<void>(`/agent/tasks/${taskId}`),
};
