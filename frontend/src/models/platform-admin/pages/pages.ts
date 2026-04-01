export interface WatcherStatus {
  agent_id: string;
  status: string;
  last_heartbeat: string | null;
  last_sync: string | null;
  error: string | null;
}

export interface HealthData {
  status: string;
  database: string;           // "connected" | "error"
  db_dialect: string;
  active_watchers: number;
  errors_last_24h: number;
  watchers: Record<string, { status: string; last_heartbeat: string | null }>;
}