import { PipelineStage, PipelineStageCreate, PipelineStageUpdate } from "@/models/platform-admin";
import { del, get, post, put } from "./helpers";


export const stages = {
  listStages: (pipelineId: number) => get<PipelineStage[]>(`/pipelines/${pipelineId}/stages`),
  createStage: (pipelineId: number, body: PipelineStageCreate) => post<PipelineStage>(`/pipelines/${pipelineId}/stages`, body),
  updateStage: (pipelineId: number, stageId: number, body: PipelineStageUpdate) =>
    put<PipelineStage>(`/pipelines/${pipelineId}/stages/${stageId}`, body),
  deleteStage: (pipelineId: number, stageId: number, reassignTo?: number) =>
    del<void>(`/pipelines/${pipelineId}/stages/${stageId}${reassignTo ? `?reassign_to_stage_id=${reassignTo}` : ''}`),
  reorderStages: (pipelineId: number, orderedIds: number[]) =>
    post<PipelineStage[]>(`/pipelines/${pipelineId}/stages/reorder`, { ordered_ids: orderedIds }),
}