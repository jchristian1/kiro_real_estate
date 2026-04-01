import { LeadStageResponse } from "@/models/platform-admin";
import { get, patch } from "./helpers";


export const leadStage = {
  getLeadStage: (leadId: number) => get<LeadStageResponse>(`/pipelines/leads/${leadId}/stage`),
  moveLeadStage: (leadId: number, stageId: number, reason?: string) =>
    patch<LeadStageResponse>(`/pipelines/leads/${leadId}/stage`, { stage_id: stageId, reason }),
}