import { get, post, put } from "./helpers";
import { Pipeline, PipelineCreate, PipelineUpdate } from "@/models/platform-admin";

export const pipelines = {
  listPipelines: () => get<Pipeline[]>('/pipelines'),
  getPipeline: (id: number) => get<Pipeline>(`/pipelines/${id}`),
  createPipeline: (body: PipelineCreate) => post<Pipeline>('/pipelines', body),
  updatePipeline: (id: number, body: PipelineUpdate) => put<Pipeline>(`/pipelines/${id}`, body),
  activatePipeline: (id: number) => post<Pipeline>(`/pipelines/${id}/activate`, {}),
}