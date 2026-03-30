export interface WatcherStatus {
  agent_id: string;
  status: string;
  last_heartbeat: string | null;
  last_sync: string | null;
  error: string | null;
}

export interface HealthData {
  status: string;
  timestamp: string;
  database: { connected: boolean; message: string };
  watchers: { active_count: number; heartbeats: Record<string, unknown> };
  errors: { count_24h: number; recent_errors: unknown[] };
}