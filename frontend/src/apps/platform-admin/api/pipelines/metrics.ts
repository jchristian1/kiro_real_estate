import { PipelineMetrics } from "@/models/platform-admin";
import { get } from "./helpers";


export const metrics = {
  getPipelineMetrics: (pipelineId: number) => get<PipelineMetrics>(`/pipelines/${pipelineId}/metrics`),
}