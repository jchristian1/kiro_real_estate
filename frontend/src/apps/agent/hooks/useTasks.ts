/**
 * TanStack Query hooks for the Tasks domain.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { tasksApi, CreateTaskPayload, UpdateTaskPayload } from '../api/tasks';

// ── Query Keys ───────────────────────────────────────────────────────────────

export const taskKeys = {
  list: (leadId: number, status?: string) =>
    ['agent', 'tasks', leadId, status ?? 'all'] as const,
};

// ── Queries ──────────────────────────────────────────────────────────────────

export function useTasks(leadId: number, status?: 'open' | 'done') {
  return useQuery({
    queryKey: taskKeys.list(leadId, status),
    queryFn: () => tasksApi.list(leadId, status),
    enabled: leadId > 0,
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useCreateTask(leadId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateTaskPayload) => tasksApi.create(leadId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: taskKeys.list(leadId) });
    },
  });
}

export function useUpdateTask(leadId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: number; payload: UpdateTaskPayload }) =>
      tasksApi.update(taskId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: taskKeys.list(leadId) });
    },
  });
}

export function useDeleteTask(leadId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: number) => tasksApi.delete(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: taskKeys.list(leadId) });
    },
  });
}
