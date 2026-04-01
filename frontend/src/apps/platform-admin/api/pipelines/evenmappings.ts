import { BuiltInEventType, EventMappingUpsert, PipelineEventMapping } from "@/models/platform-admin";
import { get, put } from "./helpers";


export const eventMappings = {
  listEventMappings: (pipelineId: number) => get<PipelineEventMapping[]>(`/pipelines/${pipelineId}/event-mappings`),
  upsertEventMapping: (pipelineId: number, eventType: BuiltInEventType, body: EventMappingUpsert) =>
    put<PipelineEventMapping>(`/pipelines/${pipelineId}/event-mappings/${eventType}`, body),
}