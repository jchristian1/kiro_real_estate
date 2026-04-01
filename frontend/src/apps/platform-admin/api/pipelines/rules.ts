import { PipelineActionRule, RuleCreate, RuleUpdate } from "@/models/platform-admin";
import { del, get, post, put } from "./helpers";


export const rules = {
  listRules: (pipelineId: number) => get<PipelineActionRule[]>(`/pipelines/${pipelineId}/rules`),
  createRule: (pipelineId: number, body: RuleCreate) => post<PipelineActionRule>(`/pipelines/${pipelineId}/rules`, body),
  updateRule: (pipelineId: number, ruleId: number, body: RuleUpdate) =>
    put<PipelineActionRule>(`/pipelines/${pipelineId}/rules/${ruleId}`, body),
  deleteRule: (pipelineId: number, ruleId: number) => del<void>(`/pipelines/${pipelineId}/rules/${ruleId}`),
  reorderRules: (pipelineId: number, orderedIds: number[]) =>
    post<PipelineActionRule[]>(`/pipelines/${pipelineId}/rules/reorder`, { ordered_ids: orderedIds }),
}